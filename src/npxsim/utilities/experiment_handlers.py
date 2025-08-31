# Custom functions for simulation parameters configuration
# M. G. Castrellon | 8 June 2025

import pandas as pd
from dataclasses import dataclass

@dataclass
class SimulationParameters:
    """
    Data class for configuring simulation inputs for different experiments based on a template DataFrame.
    Attributes:
        template_df (pd.DataFrame): The template DataFrame to be used for generating lock operation parameters.
    Methods:
        create(): Generates a new DataFrame based on the template and the selected test_name.
    """

    ALLOWED_TEST_NAMES = ("all_wsbs", "no_wsbs", "wsbs_up", "wsbs_down")
    template_df: pd.DataFrame
    gate_opening_times: dict

    def create(self, test_name: str, volume_displaced: float = None, adjust_open_times: bool = False,
               boundary_conditions: dict = None, reverse_traffic_direction: bool = False) -> pd.DataFrame:
        """
        Creates and returns a modified DataFrame based on the specified test scenario.
        Parameters:
            test_name (str): The name of the test scenario to apply. Must be one of the allowed test names
                             specified in `self.ALLOWED_TEST_NAMES`.
        Raises:
            ValueError: If `test_name` is not in `self.ALLOWED_TEST_NAMES`.
        Returns:
            pandas.DataFrame: A DataFrame with the 'WSBasins', 'UCWSBs', 'MCWSBs', and 'LCWSBs' columns
                              modified according to the selected test scenario:
                - "all_wsbs": All 'WSBasins' set to 1.
                - "no_wsbs": All 'WSBasins' set to 0.
                - "wsbs_up": 'WSBasins' set to 1 where 'Direction' is 'Uplockage', 0 where 'Downlockage'.
                - "wsbs_down": 'WSBasins' set to 0 where 'Direction' is 'Uplockage', 1 where 'Downlockage'.
            The 'UCWSBs', 'MCWSBs', and 'LCWSBs' columns are set to match 'WSBasins'.
        """
        
        if test_name not in self.ALLOWED_TEST_NAMES:
            raise ValueError(
                f"Invalid test_name '{self.test_name}'. "
                f"Allowed options are: {self.ALLOWED_TEST_NAMES}"
            )
        
        df = self.template_df.copy()

        if reverse_traffic_direction:
            df['Direction'] = df['Direction'].replace({
                'Uplockage': 'Downlockage',
                'Downlockage': 'Uplockage'
            })
        
        match test_name:
            case "all_wsbs":
                df['WSBasins'] = 1
            case "no_wsbs":
                df['WSBasins'] = 0
            case "wsbs_up":
                df.loc[df['Direction'] == 'Uplockage', 'WSBasins'] = 1
                df.loc[df['Direction'] == 'Downlockage', 'WSBasins'] = 0
            case "wsbs_down":
                df.loc[df['Direction'] == 'Uplockage', 'WSBasins'] = 0
                df.loc[df['Direction'] == 'Downlockage', 'WSBasins'] = 1

        for col in ['UCWSBs', 'MCWSBs', 'LCWSBs']:
            df[col] = df['WSBasins']
        
        if volume_displaced is not None:
            df['Ship_Vol_Disp'] = volume_displaced
        
        if boundary_conditions is not None:
            for key, value in boundary_conditions.items():
                if key in df.columns:
                    df[key] = value
        
        if adjust_open_times:
            for direction, values in self.gate_opening_times.items():
                for i, time in enumerate(values):
                    col_name = f'transitTimeLH{i+1}'
                    df.loc[df['Direction'] == direction, col_name] = time


        return df