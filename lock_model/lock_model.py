# Script for Panama Canal's Lock Model
# M. G. Castrellon | 30 May 2024

# Required Libraries
import numpy as np
import hydrodynamics as hd

# Define classes

class WaterSavingBasin:

    def __init__(self, length, width, H0, S0):
        self.length = length
        self.width = width
        self.area = length * width
        self.water_level = [H0]
        self.salinity = [S0]
        self.water_volume = self.calculate_volume()
    
    def calculate_volume(self):
        self.water_volume = self.area * self.water_level
    
    def calc_simple_mass_balance(self, V_in, V_out, S_in):
        V0 = self.water_volumne[:-1]
        V1 = V0 + V_in - V_out
        S0 = self.salinity[:-1]
        S1 = (S0*(V0 - V_out) + S_in*V_in) / V1
        self.salinity.append(S1)
        self.water_volume.append(V1)

class LockChamber:
    
    def __init__(self, length, width, H0, S0):
        self.length = length
        self.width = width
        self.area = length * width
        self.water_volumne = [H0 * self.area]
        self.water_level = [H0]
        self.salinity = [S0]
    
    def lock_step_1(self, V0, S0, E_lhs, S_lhs):
        V_lhs = E_lhs*V1
        V1 = V0 - self.V_ship
        S1 = (S0*(V0 - V_lhs - self.V_ship) + V_lhs*S_lhs) / V1
        return V1, S1
    
    def lock_step_2(V1, S1, V_lift, S_lift):
        V2 = V1 + V_lift
        S2 = (V_lift*S_lift + V1*S1) / V2
        return V2, S2
    
    def lock_step_3(self, V2, S2, E_rhs, S_rhs):
        V3 = V2 + self.V_ship
        V_rhs = E_rhs*(V2 - self.V_ship)
        S3 = (S2*(V2 - V_rhs) + S_rhs*(V_rhs + self.V_ship)) / V3
        return V3, S3
    
    def lock_cycle(self, V_ship, E_lhs, E_rhs, S_lhs, S_rhs, V_lift, S_lift):
        self.V_ship = V_ship
        V0 = self.water_volume[:-1]
        S0 = self.salinity[:-1]
        V1, S1 = self.lock_step_1(V0, S0, E_lhs, S_lhs)
        V2, S2 = self.lock_step_2(V1, S1, V_lift, S_lift)
        V3, S3 = self.lock_step_3(V2, S2, E_rhs, S_rhs)
        self.water_level.append(V3 / self.area)
        self.water_volume.append(V3)
        self.salinity.append(S3)


class NeoPanamaxLock(LockChamber, WaterSavingBasin):

    def __init__(self, lock_length, lock_width, initial_conditions):
        
        self.lower_chamber = LockChamber(length=lock_length, width=lock_width, 
                                         H0=initial_conditions['H0']['LC'], 
                                         S0=initial_conditions['S0']['LC'])
        
        self.middle_chamber = LockChamber(length=lock_length, width=lock_width, 
                                         H0=initial_conditions['H0']['MC'], 
                                         S0=initial_conditions['S0']['MC'])
        
        self.upper_chamber = LockChamber(length=lock_length, width=lock_width, 
                                         H0=initial_conditions['H0']['UC'], 
                                         S0=initial_conditions['S0']['UC'])


    def transit_up(self, V_ship, V_eq_lc, V_eq_mc, V_eq_uc, S_ocean, S_lake):
        
        S_lift_lc = self.middle_chamber.salinity[:-1]
        S_rhs_lc = self.middle_chamber.salinity[:-1]
        self.lower_chamber.lock_cycle(V_ship=V_ship, E_lhs=0.3, E_rhs=0.3, 
                                      S_lhs=S_ocean, S_rhs=S_rhs_lc, 
                                      V_lift=V_eq_lc, S_lift=S_lift_lc)
        
        self.middle_chamber.lock_cycle(V_ship=V_ship, E_lhs=0.3, E_rhs=0.3, 
                                       S_lhs=S_ocean, S_rhs=S_rhs_lc, 
                                      V_lift=V_eq_lc, S_lift=S_lift_lc)
    
    def transit_down