import numpy as np

np.set_printoptions(precision=4, suppress=True)
np.random.seed(5)

def sigma2fwhm(sigma):
    return sigma * np.sqrt(8 * np.log(2))
def fwhm2sigma(fwhm):
    return fwhm / np.sqrt(8 * np.log(2))


FWHM = 4
sigma = fwhm2sigma(FWHM)