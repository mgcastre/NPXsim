# Script for Panama Canal's Lock Model
# M. G. Castrellon | 30 May 2024

# Required Libraries
import numpy as np
from utilities import hydrodynamics as hd

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
    
    def __init__(self, length, width, h_sill, H0, S0):
        self.length = length
        self.width = width
        self.sill = h_sill
        self.area = length*width
        V0 = (H0 - h_sill)*self.area
        self.water_volume = [V0]
        self.water_level = [H0]
        self.salinity = [S0]
    
    def add_ship(self, V_ship):
        self.V_ship = V_ship
    
    def get_current_salinity(self):
        return self.salinity[-1]
    
    def get_current_volume(self):
        return self.water_volume[-1]
    
    def get_current_level(self):
        return self.water_level[-1]
    
    def get_current_status(self):
        V = self.get_current_volume()
        S = self.get_current_salinity()
        return V, S

    def update_status(self, V, S):
        H = (V/self.area) + self.sill
        self.water_level.append(H)
        self.water_volume.append(V)
        self.salinity.append(S)
    
    def drain_chamber(self, h_drain):
        S_final = self.salinity[-1]
        V_init = self.get_current_volume()
        V_drain = h_drain*self.area
        if h_drain > 0:
            V_final = V_init - V_drain
            self.update_status(V=V_final, S=S_final)
    
    def ship_enters(self, E_lhs, S_lhs):

        V_init, S_init = self.get_current_status()
        V_final = V_init - self.V_ship
        V_lhs = E_lhs*V_final
        S_final = (S_init*(V_init - V_lhs - self.V_ship) + V_lhs*S_lhs) / V_final
        self.update_status(V=V_final, S=S_final)
    
    def fill_chamber(self, h_lift, S_lift):
        V_lift = h_lift*self.area
        V_init, S_init = self.get_current_status()
        V_final = V_init + V_lift
        S_final = (V_lift*S_lift + V_init*S_init) / V_final
        self.update_status(V=V_final, S=S_final)
    
    def ship_leaves(self, E_rhs, S_rhs):
        V_init, S_init = self.get_current_status()
        V_final = V_init + self.V_ship
        V_rhs = E_rhs*(V_init - self.V_ship)
        S_final = (S_init*(V_init - V_rhs) + S_rhs*(V_rhs + self.V_ship)) / V_final
        self.update_status(V=V_final, S=S_final)

    def full_lock_cycle(
            self, h_lift, S_lift, S_lhs, S_rhs, 
            E_lhs=0.3, E_rhs=0.3
        ):
        self.ship_enters(E_lhs, S_lhs)
        self.fill_chamber(h_lift, S_lift)
        self.ship_leaves(E_rhs, S_rhs)
    
    def partial_lock_cycle(
            self, h_lift, S_lift, S_lhs, E_lhs=0.3
        ):
        self.ship_enters(E_lhs, S_lhs)
        self.fill_chamber(h_lift, S_lift)



class ThreeStepLock:

    def __init__(self, lock_length, lock_width, 
                 lock_sills, initial_conditions):
        self.chambers = {}
        for xc in ['LC', 'MC', 'UC']:
            self.chambers[xc] = LockChamber(
                length=lock_length, width=lock_width,
                H0=initial_conditions['H0'][xc], 
                S0=initial_conditions['S0'][xc],
                h_sill=lock_sills[xc],
            )
    
    # TODO: Check if the level of water in the lock chamber is 
    #       enough to transit the ship (h > (draft + safety_margin)).
    #       If not, return an error message.
    
    def calc_lockage_water(self, xc1=None, xc2=None,
                           h_ocean=0, h_lake=26,
                           option='chambers'):
        if option == 'chambers':
            H1 = self.chambers[xc1].get_current_level()
            H2 = self.chambers[xc2].get_current_level()
            hld = (H2 - H1)/2
            return hld
        elif option == 'ocean':
            H2 = self.chambers['LC'].get_current_level()
            return H2 - h_ocean
        elif option == 'lake':
            H1 = self.chambers['UC'].get_current_level()
            return h_lake - H1 
        return hld
    
    def equalize_levels(self, xc1, xc2):
        hld = self.calc_lockage_water(xc1, xc2)
        self.chambers[xc2].drain_chamber(h_drain=hld)
        S_next_cham = self.chambers[xc2].get_current_salinity()
        self.chambers[xc1].fill_chamber(h_lift=hld, S_lift=S_next_cham)
        print(f'Water Exchanged between {xc1} and {xc2}: {hld}')
    
    def extract_dimensions(self, xc):
        W = self.chambers[xc].width
        L = self.chambers[xc].length
        H = self.chambers[xc].get_current_level()
        return W, L, H
    
    def lock_exchange_factor(self, ch_lhs, ch_rhs, tOpen, T=28):
        # Extract salinity and calculate density values
        S_lhs = self.chambers[ch_lhs].get_current_salinity()
        S_rhs = self.chambers[ch_rhs].get_current_salinity()
        rho_lhs = hd.Rho_from_PSU(S_lhs, Temp=T)
        rho_rhs = hd.Rho_from_PSU(S_rhs, Temp=T)
        # Extract the water level and length of the lock chambers
        if rho_lhs > rho_rhs:
            _, L, H = self.extract_dimensions(ch_lhs)
            rho1 = rho_rhs
            rho2 = rho_lhs
        else:
            _, L, H = self.extract_dimensions(ch_rhs)
            rho1 = rho_lhs
            rho2 = rho_rhs
        # Calculate the exchange coefficient
        Eff = hd.exchange_coefficient(rho1, rho2, H, L, tOpen, eta=0.8)
        return Eff
    
    def ocean_exchange_factor(self, S_ocean, tOpen, T=28):
        _, L, H = self.extract_dimensions('LC')
        S_lc = self.chambers['LC'].get_current_salinity()
        rho_lc = hd.Rho_from_PSU(S_lc, Temp=T)
        rho_ocean = hd.Rho_from_PSU(S_ocean, Temp=T)
        Eff = hd.exchange_coefficient(
            rho1=rho_lc, rho2=rho_ocean, 
            H=H, L=L, tOpen, eta=0.8)
        return Eff
    
    def lake_exchange_factor(self, S_lake, tOpen, T=28):
        _, L, H = self.extract_dimensions('UC')
        S_uc = self.chambers['UC'].get_current_salinity()
        rho_uc = hd.Rho_from_PSU(S_uc, Temp=T)
        rho_lake = hd.Rho_from_PSU(S_lake, Temp=T)
        Eff = hd.exchange_coefficient(
            rho1=rho_lake, rho2=rho_uc, 
            H=H, L=L, tOpen, eta=0.8)
        return Eff
    
    def cross_lock_head(self, cham1, cham2, tOpen):
        Eff = self.calc_exchange_factor(cham1, cham2, tOpen)
        S_prev_cham = self.chambers[cham1].get_current_salinity()
        S_next_cham = self.chambers[cham2].get_current_salinity()
        self.chambers[cham1].ship_leaves(E_rhs=Eff, S_rhs=S_next_cham)
        self.chambers[cham2].ship_enters(E_lhs=Eff, S_lhs=S_prev_cham)

    def transit_up(self, V_ship, S_ocean, S_lake, Eff=None):

        # Define the volume of the ship transiting the lock
        for xc in ['LC', 'MC', 'UC']:
            self.chambers[xc].add_ship(V_ship)
        
        # Lockage process

        ## 1) Drain the lock chamber to the level of the ocean
        h_drain_ocean = self.calc_lockage_water(option='ocean')
        self.chambers['LC'].drain_chamber(h_drain_ocean)

        ## 2) Transit from ocean to lower chamber
        Eff = self.ocean_exchange_factor(S_ocean, tOpen=25*60)
        self.chambers['LC'].ship_enters(E_lhs=Eff, S_lhs=S_ocean)

        ## 3) Equalization and transit between LC and MC
        self.equalize_levels('LC', 'MC')
        self.cross_lock_head('LC', 'MC', tOpen=25*60)
 
        ## 5) Equalization and transit between MC and UC
        self.equalize_levels('MC', 'UC')
        self.cross_lock_head('MC', 'UC', tOpen=25*60)

        ## 7) Lift the ship to the level of the lake
        h_lift_lake = self.calc_lockage_water(option='lake')
        self.chambers['UC'].fill_chamber(h_lift=h_lift_lake, S_lift=S_lake)

        ## 8) Ship leaves the upper chamber of the lock
        Eff = self.lake_exchange_factor(S_lake, tOpen=25*60)
        self.chambers['UC'].ship_leaves(E_rhs=Eff, S_rhs=S_lake)