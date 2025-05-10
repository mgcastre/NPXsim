# Data classes for NPX lock model
# M. G. Castrellon | 8 May 2025

# Required libraries
import pandas as pd
from pydantic import BaseModel,ConfigDict
from typing import List, NamedTuple, Optional


# Data class for lock design specification

class LockDesignSpecifications(BaseModel):
    z_lock_head_sills: dict
    chamber_dimensions: dict
    chamber_z_elevations: dict
    chamber_operating_limits: dict
    wsb_dimensions: Optional[dict] = None
    wsb_z_elevations: Optional[dict] = None
    wsb_operating_limits: Optional[dict] = None


# Data classes for simulation input

class TransitTimes(NamedTuple):
    lock_head_1: int  # minutes
    lock_head_2: int  # minutes
    lock_head_3: int  # minutes
    lock_head_4: int  # minutes


class EqualizationTimes(NamedTuple):
    lower_chamber: int  # minutes
    middle_chamber: int  # minutes
    upper_chamber: int  # minutes


class WaterSavingBasinUse(BaseModel):
    """
    example_wsb_use_dict = {
        'lock_head_1': {'Top': 0, 'Int': 0, 'Bot': 0}, # UC basins
        'lock_head_2': {'UC': {'Top': 0, 'Int': 0, 'Bot': 0}, 'MC': {'Top': 0, 'Int': 0, 'Bot': 0}},
        'lock_head_3': {'MC': {'Top': 0, 'Int': 0, 'Bot': 0}, 'LC': {'Top': 0, 'Int': 0, 'Bot': 0}},
        'lock_head_4': {'Top': 0, 'Int': 0, 'Bot': 0}, # LC basins
    }
    """
    lock_head_1: dict
    lock_head_2: dict
    lock_head_3: dict
    lock_head_4: dict


class OperationParameters(BaseModel):
    lockage_id: int
    direction: str
    ship_volume: float
    dt_lockage_starts: str # string formated as a date '%Y-%m-%d %H:%M:%S'
    equalization_times: EqualizationTimes
    gate_open_times: TransitTimes
    wsb_use: WaterSavingBasinUse
    wsb_flag: bool


# Data class for model output

class OperationOutputs(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    lockage_id: Optional[List[int]] = None
    date_time: Optional[List[pd.Timestamp]] = None
    salt_load_vd: Optional[List[float]] = None
    salt_load_dc: Optional[List[float]] = None
    freshwater_used: Optional[List[float]] = None


if __name__ == '__main__':
    equalization_time = EqualizationTimes(10, 12, 10)
    print(equalization_time.lower_chamber)