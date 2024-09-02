# Script for Panama Canal's Lock Model
# M. G. Castrellon | 30 May 2024

# Required Libraries
import numpy as np
import hydrodynamics as hd

# Define classes

class WaterSavingBasin:

    def __init__(self, length, width, H0, S0, Hf):
        self.length = length
        self.width = width
        self.area = length * width
        self.water_level = [H0 - Hf]
        self.floor_level = Hf
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
    
    def add_ship(self, V_ship):
        self.V_ship = V_ship
    
    def get_current_salinity(self):
        return self.salinity[:-1]
    
    def get_current_volume(self):
        return self.water_volume[:-1]
    
    def get_current_level(self):
        return self.water_level[:-1]
    
    def get_current_status(self):
        V = self.get_current_volume()
        S = self.get_current_salinity()
        return V, S

    def update_status(self, V=None, S=None):
        if V is not None:
            H = V/self.area
            self.water_level.append(H)
            self.water_volume.append(V)
        if S is not None:
            self.salinity.append(S)
    
    def lock_step_1(self, E_lhs, S_lhs):
        V0, S0 = self.get_current_status()
        V_lhs = E_lhs*V1
        V1 = V0 - self.V_ship
        S1 = (S0*(V0 - V_lhs - self.V_ship) + V_lhs*S_lhs) / V1
        self.update_status(V=V1, S=S1)
    
    def lock_step_2(self, V_lift, S_lift):
        V1, S1 = self.get_current_status()
        V2 = V1 + V_lift
        S2 = (V_lift*S_lift + V1*S1) / V2
        self.update_status(V=V2, S=S2)
    
    def lock_step_3(self, E_rhs, S_rhs):
        V2, S2 = self.get_current_status()
        V3 = V2 + self.V_ship
        V_rhs = E_rhs*(V2 - self.V_ship)
        S3 = (S2*(V2 - V_rhs) + S_rhs*(V_rhs + self.V_ship)) / V3
        self.update_status(V=V3, S=S3)
    
    def drain_lift_volume(self, V_drain):
        V_init = self.get_current_volume()
        if V_drain > 0:
            V_final = V_init - V_drain
            self.water_volume.append(V_final)
    
    def full_lock_cycle(self, E_lhs, E_rhs, S_lhs, S_rhs, S_lift, V_lift, V_drain):
        self.drain_lift_volume(V_drain)
        self.lock_step_1(E_lhs, S_lhs)
        self.lock_step_2(V_lift, S_lift)
        self.lock_step_3(E_rhs, S_rhs)
    
    def partial_lock_cycle(self, E_lhs, S_lhs, S_lift, V_lift, V_drain):
        self.drain_lift_volume(V_drain)
        self.lock_step_1(E_lhs, S_lhs)
        self.lock_step_2(V_lift, S_lift)



class ThreeStepLock:

    def __init__(self, lock_length, lock_width, initial_conditions):
        self.chambers = {}
        for xc in ['LC', 'MC', 'UC']:
            self.chambers[xc] = LockChamber(
                length=lock_length, width=lock_width, 
                H0=initial_conditions['H0'][xc], 
                S0=initial_conditions['S0'][xc]
            )
    
    def to_volume(self, H, xc='LC'):
        A = self.chambers[xc].area
        return H*A

    def transit_up(self, V_ship, H_lh1, H_lh2, H_lh3, H_lh4, S_ocean, S_lake, Eff):

        # Define the volume of the ship transiting the lock
        for xc in ['LC', 'MC', 'UC']:
            self.chambers[xc].add_ship(V_ship)
        
        # Transit from ocean to lower chamber
        S_next_cham = self.chambers['MC'].get_current_salinity()
        self.chambers['LC'].partial_lock_cycle(
            E_lhs=Eff, 
            S_lhs=S_ocean, 
            S_lift=S_next_cham,
            V_lift=self.to_volume(H_lh2),
            V_drain=self.to_volume(H_lh1)
        )

        # Transit from lower chamber to middle chamber
        S_prev_cham = self.chambers['LC'].get_current_salinity()
        S_next_cham = self.chambers['UC'].get_current_salinity()
        self.chambers['MC'].partial_lock_cycle(
            E_lhs=Eff, 
            S_lhs=S_prev_cham,
            S_lift=S_next_cham,
            V_lift=self.to_volume(H_lh3),
            V_drain=self.to_volume(H_lh2)
        )

        # Transit from middle chamber to lake
        S_prev_cham = self.chambers['MC'].get_current_salinity()
        self.chambers['UC'].full_lock_cycle(
            S_lhs=S_prev_cham,
            E_lhs=Eff, E_rhs=Eff,
            S_lift=S_lake, S_rhs=S_lake,
            V_lift=self.to_volume(H_lh4),
            V_drain=self.to_volume(H_lh3)
        )