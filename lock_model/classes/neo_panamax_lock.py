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
    
    @staticmethod
    def calc_initial_levels(cham_op_levels, wsb_op_levels, direction):
        cham_init_levels = {}
        wsb_init_levels = {}
        # For uplockage, the lower chamber is at the level of the ocean (low level)
        # and the rest of the chambers are at their higher operational levels.
        # For downlockage, the upper chamber is at the level of the lake (high level)
        # and the rest of the chambers are at their lower operational levels.
        levels_dict = {'up': {'LC': 0, 'MC': 1, 'UC': 1}, 
                       'down': {'LC': 0, 'MC': 0, 'UC': 1}}
        for cham, op_level in levels_dict[direction].items():
            cham_init_levels[cham] = cham_op_levels[cham][op_level]
            b_level = 1 - op_level # Level of WSB is opposite of related chamber.
            wsb_init_levels[cham] = {} # Create dictionary for each chamber.
            for basin in ['Top', 'Int', 'Btm']:
                wsb_init_levels[cham][basin] = wsb_op_levels[cham][basin][b_level]
        return cham_init_levels, wsb_init_levels
    
    def set_initial_conditions(self, boundary_conditions, salinities, 
                               direction, operation_start_dt, 
                               water_temperature=28):
        # Calculate initial operational water levels
        H_lake = boundary_conditions['H_lake']
        H_ocean = boundary_conditions['H_ocean']
        cham_op_levels, wsb_op_levels = self.calc_operational_levels(H_lake, H_ocean)
        cham_init_levels, wsb_init_levels = \
            self.calc_initial_levels(cham_op_levels, wsb_op_levels, direction)
        # Add initial conditions to the lock chambers
        for cham in ['LC', 'MC', 'UC']:
            self.chambers[cham].add_initial_conditions(
                H0=cham_init_levels[cham], S0=salinities['CHAM'][cham]
            )
            for basin in ['Top', 'Int', 'Btm']:
                self.basins[cham][basin].add_initial_conditions(
                H0=wsb_init_levels[cham][basin], S0=salinities['WSB'][cham]
            )
        # Pass the temperature to the class attribute
        self.T = water_temperature
        # Add master initial operation start time
        self.operation_start_dt = operation_start_dt
        
    # def turaround():
    # TODO: Develop the logic of the turnaround, taking into account that 
    #       the basins should be in the opposite state as the locks.
    #    pass

"""     
    def uplockage():
        pass

    def downlockage():
        pass

    def transit():
        pass

    def operate():
        pass 
"""