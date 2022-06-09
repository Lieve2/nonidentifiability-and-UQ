import numpy as np
from tqdm import tqdm

# function for PPO calculation
def PPO(arr1, arr2, nbins):

    # Determine the integration range
    min_value = np.min((arr1.min(), arr2.min()))
    max_value = np.min((arr1.max(), arr2.max()))

    # Determine the bin width
    bin_width = (max_value - min_value) / nbins

    # For each bin, find minimum frequency
    lower_bound = min_value  # Lower bound of the first bin is the min_value of both arrays
    lower = np.empty(nbins)  # Array that will collect the min frequency in each bin

    for b in tqdm(range(nbins)):
        higher_bound = lower_bound + bin_width  # Set the higher bound for the bin

        # Determine the share of samples in the interval
        freq1 = np.ma.masked_where((arr1 < lower_bound) | (arr1 >= higher_bound), arr1).count() / len(arr1)
        freq2 = np.ma.masked_where((arr2 < lower_bound) | (arr2 >= higher_bound), arr2).count() / len(arr2)

        # Conserve the lower frequency
        lower[b] = np.min((freq1, freq2))
        lower_bound = higher_bound  # proceed to next range
        pass

    return lower.sum()
