import numpy as np
from scipy.ndimage.filters import gaussian_filter
from scipy.ndimage.interpolation import map_coordinates

from .base import Transform


class ElasticTransform(Transform):
    """Random Elastic Transformation."""
    NATIVE_DTYPES = {'float32', 'float64'}
    PREFERRED_DTYPE = 'float32'

    def __init__(self, alpha, sigma, order=1, invert=False, **super_kwargs):
        self._initial_dtype = None
        super(ElasticTransform, self).__init__(**super_kwargs)
        self.alpha = alpha
        self.sigma = sigma
        self.order = order
        self.invert = invert

    def build_random_variables(self, **kwargs):
        np.random.seed()
        self.set_random_variable('random_field_x', np.random.uniform(-1, 1, kwargs.get('imshape')))
        self.set_random_variable('random_field_y', np.random.uniform(-1, 1, kwargs.get('imshape')))

    def cast(self, image):
        if image.dtype not in self.NATIVE_DTYPES:
            self._initial_dtype = image.dtype
            image = image.astype(self.PREFERRED_DTYPE)
        return image

    def uncast(self, image):
        if self._initial_dtype is not None:
            image = image.astype(self._initial_dtype)
        self._initial_dtype = None
        return image

    def image_function(self, image):
        # Cast image to one of the native dtypes (one which that is supported by scipy)
        image = self.cast(image)
        # Take measurements
        imshape = image.shape
        # Make random fields
        dx = self.get_random_variable('random_field_x', imshape=imshape) * self.alpha
        dy = self.get_random_variable('random_field_y', imshape=imshape) * self.alpha
        # Smooth dx and dy
        sdx = gaussian_filter(dx, sigma=self.sigma, mode='reflect')
        sdy = gaussian_filter(dy, sigma=self.sigma, mode='reflect')
        # Make meshgrid
        x, y = np.meshgrid(np.arange(imshape[1]), np.arange(imshape[0]))
        # Make inversion coefficient
        _inverter = 1. if not self.invert else -1.
        # Distort meshgrid indices (invert if required)
        distinds = (y + _inverter * sdy).reshape(-1, 1), (x + _inverter * sdx).reshape(-1, 1)
        # Map cooordinates from image to distorted index set
        transformed_image = map_coordinates(image, distinds,
                                            mode='reflect', order=self.order).reshape(imshape)
        # Uncast image to the original dtype
        transformed_image = self.uncast(transformed_image)
        return transformed_image


class AdditiveGaussianNoise(Transform):
    """Add gaussian noise to the input."""
    def __init__(self, sigma, **super_kwargs):
        super(AdditiveGaussianNoise, self).__init__(**super_kwargs)
        self.sigma = sigma

    def build_random_variables(self, **kwargs):
        np.random.seed()
        self.set_random_variable('noise', np.random.normal(loc=0, scale=self.sigma,
                                                           size=kwargs.get('imshape')))

    def image_function(self, image):
        image = image + self.get_random_variable('noise', imshape=image.shape)
        return image


class RandomRotate(Transform):
    """Random 90-degree rotations."""
    def __init__(self, **super_kwargs):
        super(RandomRotate, self).__init__(**super_kwargs)

    def build_random_variables(self, **kwargs):
        np.random.seed()
        self.set_random_variable('k', np.random.randint(0, 4))

    def image_function(self, image):
        return np.rot90(image, k=self.get_random_variable('k'))


class RandomFlip(Transform):
    """Random left-right or up-down flips."""
    def __init__(self, **super_kwargs):
        super(RandomFlip, self).__init__(**super_kwargs)

    def build_random_variables(self, **kwargs):
        np.random.seed()
        self.set_random_variable('flip_lr', np.random.uniform() > 0.5)
        self.set_random_variable('flip_ud', np.random.uniform() > 0.5)

    def image_function(self, image):
        if self.get_random_variable('flip_lr'):
            image = np.fliplr(image)
        if self.get_random_variable('flip_ud'):
            image = np.flipud(image)
        return image


class CenterCrop(Transform):
    """ Crop patch of size `size` from the center of the image """
    def __init__(self, size, **super_kwargs):
        super(CenterCrop, self).__init__(**super_kwargs)
        assert isinstance(size, (int, tuple))
        self.size = (size, size) if isinstance(size, int) else size

    def image_function(self, image):
        h,  w  = image.shape
        th, tw = self.size
        x1 = int(round((w - tw) / 2.))
        y1 = int(round((h - th) / 2.))
        return image[x1:x1+tw, y1:y1+th]