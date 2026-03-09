# Class to generate a synthetic lockage sequence
# M. G. Castrellon | 4 March 2026

# Load libraries
import numpy as np
import pandas as pd

class TransitScheduleGenerator:
    def __init__(self, mode):
        self.mode = mode

    def _make_schedule(self) -> pd.DataFrame:
        schedule = pd.DataFrame()
        return schedule

    def _generate_simple(self, volume):
        pass

    def _generate_fixed_volume(self):
        pass

    def _generate_data_driven(self, data):
        pass

    def generate(self, mode=""):
        pass


    def sample_vessel(category_stats):
        """Sample one value based on category frequency and its normal distribution."""
        names = list(category_stats.keys())
        freqs = [category_stats[c]["freq"] for c in names]

        chosen = np.random.choice(names, p=freqs)
        cat = category_stats[chosen]
        value = np.random.normal(loc=cat["mean"], scale=cat["std"])

        return chosen, value

def analyze_categories(df, category_col, value_col) -> dict:
    """
    Calculates frequency and fits a normal distribution
    for each category in the dataframe.
    """
    category_stats = {}
    freq = df[category_col].value_counts(normalize=True)

    for category, frequency in freq.items():
        values = df[df[category_col] == category][value_col].dropna()
        category_stats[category] = {
            "freq": frequency,
            "mean": values.mean(),
            "std": values.std()
        }

    return category_stats


