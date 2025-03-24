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
    
    def equalize_and_cross(self, lock_head, direction, wsb_use, init_time):
        # 1. Drain and fill chambers with water saving basins
        lower_cham, upper_cham = self.lock_heads['Chambers'][lock_head]
        # TODO: Figure out how to handle the time in here!
        if wsb_use[upper_cham] & wsb_use[lower_cham]:
            # Drain the upper chamber to the water saving basin
            # Time to drain the chamber ts = init_time + t_eq
            pass
        if wsb_use[lower_cham]:
            # Fill the middle chamber with water from the water saving basin
            # Time to fill the chamber ts = init_time + t_eq
            pass
        # 2. Finish chamber equalization (if needed) and cross between chambers
        time_stamp = super().equalize_and_cross(lock_head, direction, ts)
        return time_stamp

    def operate(self, operation_params, boundary_conditions):
        for i in range(len(operation_params)):
            this_transit = operation_params[i]
            self.transit(this_transit, boundary_conditions[i])
            try:
                next_transit = operation_params[i+1]
            except IndexError:
                break
            if this_transit['Direction'] != next_transit['Direction']:
                ts = self.calc_elapsed_minutes(next_transit['TS_LocksReady']) - 30
                self.turnaround(boundary_conditions[i+1], next_transit['Direction'], tinit=ts)
    
    def transit(self, operation_params, boundary_conditions):
        # Extract volume of the ship transiting the lock
        self.V_ship = operation_params['V_ship']
        # Extract boundary conditions
        S_ocean = boundary_conditions['S_ocean']
        H_ocean = boundary_conditions['H_ocean']
        S_lake = boundary_conditions['S_lake']
        H_lake = boundary_conditions['H_lake']
        # Add chamber's length and ship's volume to lock chamber
        for cham in ['LC', 'MC', 'UC']:
            L = operation_params['Chamber_Length']
            self.chambers[cham].add_ship(self.V_ship)
            self.chambers[cham].change_length(L)
        # Extract lock operation parameters
        self.tGateOpen = operation_params['tGateOpen']
        self.eqTime = operation_params['eqTime']
        # Extract lockage direction and wsb use
        direction = operation_params['Direction']
        wsb_use = operation_params['WSBs']
        # Calculate initial lockage time stamp in minutes
        lockage_start_dt = operation_params['TS_LockageStarts']
        initial_time = self.calc_elapsed_minutes(lockage_start_dt)
        # Perform transit based on the direction
        if direction == 'up':
            self.uplockage(initial_time, wsb_use, S_ocean, H_ocean, S_lake, H_lake)
        elif direction == 'down':
            self.downlockage(initial_time, wsb_use, S_ocean, H_ocean, S_lake, H_lake)
        else:
            raise ValueError("Direction must be either 'up' or 'down'.")
    
    def uplockage(self, initial_time_stamp, wsb_use, S_ocean, H_ocean, S_lake, H_lake):
        ## 1) Drain the lock chamber to the level of the ocean (LH4)
        if self.chambers['LC'].get_current_level() > H_ocean:
            self.chambers['LC'].drain_chamber(H_final=H_ocean, ts=initial_time_stamp)
        ## 2) Gates at LH4 open, salinity enters from the ocean and ship enters the lock
        t_transit = self.tGateOpen['LH4'] # minutes
        time_stamp = initial_time_stamp + t_transit # minutes
        V_ex_ocean = self.exchange_with_boundary(S_ocean=S_ocean)
        self.chambers['LC'].ship_enters(V_lhs=V_ex_ocean, S_lhs=S_ocean, ts=time_stamp)
        ## 3) Equalization and transit between LC and MC
        time_stamp = self.equalize_and_cross(lock_head='LH3', direction='up', init_time=time_stamp)
        ## 4) Equalization and transit between MC and UC
        time_stamp = self.equalize_and_cross(lock_head='LH2', direction='up', init_time=time_stamp)
        ## 5) Lift the ship to the level of the lake (LH1)
        time_stamp = time_stamp + self.eqTime['UC'] # minutes to fill chamber
        self.chambers['UC'].fill_chamber(H_final=H_lake, S_lift=S_lake, ts=time_stamp)
        self.record_freshwater_consumed(end_luc=H_lake, ts=time_stamp)
        ## 6) Gates at LH1 open, salt mass enters the lake and ship leaves the lock
        t_transit = self.tGateOpen['LH1'] # minutes
        time_stamp = time_stamp + t_transit # minutes
        S_chamber = self.chambers['UC'].salinity[-1]
        V_ex_lake = self.exchange_with_boundary(S_lake=S_lake)
        self.chambers['UC'].ship_leaves(V_rhs=V_ex_lake, S_rhs=S_lake, ts=time_stamp)
        self.calc_salt_mass_load(S_lake, V_ex_lake, S_chamber, direction='up', ts=time_stamp)

    def downlockage(self, initial_time_stamp, wsb_use, S_ocean, H_ocean, S_lake, H_lake):
        ## 1) Lift upper chamber to level of the lake (LH1)
        if self.chambers['UC'].get_current_level() < H_lake:
            if wsb_use['UC']:
                # Fill the upper chamber with water from the water saving basin
                pass
            self.chambers['UC'].fill_chamber(H_final=H_lake, S_lift=S_lake, ts=initial_time_stamp)
            super().record_freshwater_consumed(end_luc=H_lake, ts=initial_time_stamp)
        ## 2) Gates at LH1 open, salt mass enters the lake and ship enters the lock
        t_transit = self.tGateOpen['LH1'] # minutes
        time_stamp = initial_time_stamp + t_transit # minutes
        S_chamber = self.chambers['UC'].salinity[-1]
        V_ex_lake = super().exchange_with_boundary(S_lake=S_lake)
        self.chambers['UC'].ship_enters(V_lhs=V_ex_lake, S_lhs=S_lake, ts=time_stamp)
        super().calc_salt_mass_load(S_lake, V_ex_lake, S_chamber, direction='down', ts=time_stamp)
        ## 3) Equalization and transit between UC and MC
        time_stamp = self.equalize_and_cross(
            lock_head='LH2', wsb_use=wsb_use, direction='down', init_time=time_stamp)
        ## 4) Equalization and transit between MC and LC
        time_stamp = self.equalize_and_cross(
            lock_head='LH3', wsb_use=wsb_use, direction='down', init_time=time_stamp)
        ## 5) Drain to the level of the ocean (LH4)
        time_stamp = time_stamp + self.eqTime['LC'] # minutes to drain chamber
        self.chambers['LC'].drain_chamber(H_final=H_ocean, ts=time_stamp)
        ## 6) Gates at LH4 open, salinity enters from the ocean and ship leaves the lock
        t_transit = self.tGateOpen['LH4'] # minutes
        time_stamp = time_stamp + t_transit # minutes
        V_ex_ocean = super().exchange_with_boundary(S_ocean=S_ocean) 
        self.chambers['LC'].ship_leaves(V_rhs=V_ex_ocean, S_rhs=S_ocean, ts=time_stamp)

"""     
    def turnaround():
        pass 
"""