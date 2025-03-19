# NeoPanamaxLock class for Panama Canal's lock model
# M. G. Castrellon | 18 March 2025

# Required Libraries
import numpy as np
import pandas as pd
import hydrodynamics as hd
from datetime import datetime
from lock_elements import *
from three_steps_lock import *

# Define class
class NeoPanamaxLock(ThreeStepsLock):

    def __init__(self, lock_bottom_elevs, lock_head_sills, 
                 wsb_dims, wsb_bottom_elevs):
        
        # Initialize parent class
        super().__init__(lock_length=430, lock_width=55, 
                         lock_bottom_elevs=lock_bottom_elevs, 
                         lock_head_sills=lock_head_sills)

        # Initialize water saving basin objects
        self.basins = {'LC': {}, 'MC': {}, 'UC': {}}
        for cham in self.basins.keys():
            for basin in ['Top', 'Int', 'Btm']:
                self.basins[cham][basin] = WaterSavingBasin(
                    length=wsb_dims['L'], width=wsb_dims['W'],
                    z_bottom=wsb_bottom_elevs[cham][basin],
                    S0=None, H0=None
                )
    
    @staticmethod
    def calc_wsb_operational_levels(chamber_levels):
        wsb_levels = {}
        fractions = {'Top': (3, 4), 'Int': (2, 3), 'Btm': (1, 2)}
        for chamber, (c_low, c_high) in chamber_levels.items():
            wsb_levels[chamber] = {}
            for basin, (n_low, n_high) in fractions.items():
                level_low = c_low + (n_low/5)*(c_high - c_low)
                level_high = c_low + (n_high/5)*(c_high - c_low)
                wsb_levels[chamber][basin] = (level_low, level_high)
        return wsb_levels
    
    def calc_operational_levels(self, H_lake, H_ocean):
        cham_op_levels = super().calc_operational_levels(H_lake, H_ocean)
        wsb_op_levels = self.calc_wsb_operational_levels(cham_op_levels)
        return cham_op_levels, wsb_op_levels
    