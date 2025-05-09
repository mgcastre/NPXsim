# Helper functions functions for NPX lock model
# M. G. Castrellon | 9 May 2025

import pandas as pd

def extract_boundary_conditions(df, time_stamp, location):
    """
    Extracts the boundary conditions (salinity and water elevation) at a given time,
    at a specified location (lake or ocean).
    """
    time_stamp = pd.to_datetime(time_stamp)
    columns = [f"{p}_{location}" for p in ['H', 'S']]
    H, S = df.loc[time_stamp, columns].values
    return H, S