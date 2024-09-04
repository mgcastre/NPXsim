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
    
    def __init__(self, length, width, z_bottom, H0=None, S0=None):
        self.length = length
        self.width = width
        self.z_bottom = z_bottom
        self.area = length*width
        if H0 is not None and S0 is not None:
            self.add_initial_conditions(H0, S0)
    
    def add_initial_conditions(self, H0, S0):
        V0 = (H0 - self.z_bottom)*self.area
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

    def update_status(self, V, S, H):
        self.water_level.append(H)
        self.water_volume.append(V)
        self.salinity.append(S)
    
    def drain_chamber(self, h_drain):
        V_drain = h_drain*self.area
        V_init = self.water_volume[-1]
        V_final = V_init - V_drain
        H_final = (V_final/self.area) + self.z_bottom
        # Although water level changes, salinity remains constant
        self.update_status(V=V_final, S=self.salinity[-1], H=H_final)
    
    def ship_enters(self, E_lhs, S_lhs):
        V_init, S_init = self.get_current_status()
        V_final = V_init - self.V_ship
        V_lhs = E_lhs*V_final
        S_final = (S_init*(V_init - V_lhs - self.V_ship) + V_lhs*S_lhs) / V_final
        # Although volume of water gets exchanged, the water level remains constant
        self.update_status(V=V_final, S=S_final, H=self.water_level[-1])
    
    def fill_chamber(self, h_lift, S_lift):
        V_lift = h_lift*self.area
        V_init, S_init = self.get_current_status()
        V_final = V_init + V_lift
        S_final = (V_lift*S_lift + V_init*S_init) / V_final
        H_final = (V_final/self.area) + self.z_bottom
        self.update_status(V=V_final, S=S_final, H=H_final)
    
    def ship_leaves(self, E_rhs, S_rhs):
        V_init, S_init = self.get_current_status()
        V_final = V_init + self.V_ship
        V_rhs = E_rhs*(V_init - self.V_ship)
        S_final = (S_init*(V_init - V_rhs) + S_rhs*(V_rhs + self.V_ship)) / V_final
        # Although volume of water gets exchanged, the water level remains constant
        self.update_status(V=V_final, S=S_final, H=self.water_level[-1])


class ThreeStepLock:

    def __init__(self, lock_length, lock_width, 
                 lock_bottom_elevs, lock_head_sills,
                 initial_conditions=None):
        # Initialize lock chamber objects
        self.chambers = {}
        for cham in ['LC', 'MC', 'UC']:
            self.chambers[cham] = LockChamber(
                length=lock_length, width=lock_width,
                z_bottom=lock_bottom_elevs[cham],
                S0=None, H0=None
            )
        # Add initial conditions if provided
        if initial_conditions is not None:
            self.add_initial_conditions(initial_conditions)
        # Create attributes for lock heads
        self.lock_heads = {'Z': lock_head_sills}
        self.lock_heads['Chambers'] = {
            'LH1': ['UC'], 
            'LH2': ['MC', 'UC'],
            'LH3': ['LC', 'MC'], 
            'LH4': ['LC']
        }
    
    def add_initial_conditions(self, initial_conditions):
        for cham in ['LC', 'MC', 'UC']:
            self.chambers[cham].add_initial_conditions(
                H0=initial_conditions['H0'][cham], 
                S0=initial_conditions['S0'][cham]
            )

    def calc_drain_lift_water(self, cham1, cham2):
        H1 = self.chambers[cham1].get_current_level()
        H2 = self.chambers[cham2].get_current_level()
        hld = np.abs(H2 - H1)/2
        return hld
    
    def equalize_levels(self, cham1, cham2):
        hld = self.calc_drain_lift_water(cham1, cham2)
        self.chambers[cham2].drain_chamber(h_drain=hld)
        S_next_cham = self.chambers[cham2].get_current_salinity()
        self.chambers[cham1].fill_chamber(h_lift=hld, S_lift=S_next_cham)
        print(f'Water Exchanged between {cham1} and {cham2}: {hld}')
    
    def extract_properties(self, cham):
        W = self.chambers[cham].width
        L = self.chambers[cham].length
        H = self.chambers[cham].get_current_level()
        return W, L, H
    
    def lock_exchange_factor(self, lock_head, S_ocean=None, S_lake=None):
        # Extract salinity and water levels
        if lock_head == 'LH1':
            _, L, H = self.extract_properties('UC')
            S_lhs = self.chambers['UC'].get_current_salinity()
            S_rhs = S_lake
        elif lock_head == 'LH2':
            _, L, H = self.extract_properties('MC')
            S_lhs = self.chambers['MC'].get_current_salinity()
            S_rhs = self.chambers['UC'].get_current_salinity()
        elif lock_head == 'LH3':
            _, L, H = self.extract_properties('LC')
            S_lhs = self.chambers['LC'].get_current_salinity()
            S_rhs = self.chambers['MC'].get_current_salinity()
        elif lock_head == 'LH4':
            _, L, H = self.extract_properties('LC')
            S_rhs = self.chambers['LC'].get_current_salinity()
            S_lhs = S_ocean
        # Calculate density of water in the lock chambers
        rho_lhs = hd.Rho_from_PSU(S_lhs, Temp=28)
        rho_rhs = hd.Rho_from_PSU(S_rhs, Temp=28)
        # Sort densities
        if rho_lhs > rho_rhs:
            rho1 = rho_rhs
            rho2 = rho_lhs
        else:
            rho1 = rho_lhs
            rho2 = rho_rhs
        # Calculate the exchange coefficient
        tOpen = self.lock_heads['tOpen'][lock_head]
        head = H - self.lock_heads['Z'][lock_head]
        Eff = hd.exchange_coefficient(
            rho1=rho1, rho2=rho2, H=head, 
            L=L, tOpen=tOpen, eta=0.8)
        # Return the exchange coefficient
        return Eff
    
    def cross_lock_head(self, cham1, cham2, lock_head):
        Eff = self.lock_exchange_factor(lock_head)
        S_prev_cham = self.chambers[cham1].get_current_salinity()
        S_next_cham = self.chambers[cham2].get_current_salinity()
        self.chambers[cham1].ship_leaves(E_rhs=Eff, S_rhs=S_next_cham)
        self.chambers[cham2].ship_enters(E_lhs=Eff, S_lhs=S_prev_cham)
        print(f'{cham1}-{cham2} Eff: {Eff}')
    
    def eq_and_cross(self, lock_head, direction):
        lower_cham, upper_cham = self.lock_heads['Chambers'][lock_head]
        if direction == 'up':
            cham1 = lower_cham
            cham2 = upper_cham
        elif direction == 'down':
            cham1 = upper_cham
            cham2 = lower_cham
        self.equalize_levels(cham1, cham2)
        self.cross_lock_head(cham1, cham2, lock_head)
    
    def transit_up(self, V_ship, t_open_dict, boundary_conditions,
                   initial_conditions=None):
        
        # Extract boundary conditions
        S_ocean = boundary_conditions['S_ocean']
        H_ocean = boundary_conditions['H_ocean']
        S_lake = boundary_conditions['S_lake']
        H_lake = boundary_conditions['H_lake']
        
        # Overwrite chamber initial conditions if provided
        if initial_conditions is not None:
            self.add_initial_conditions(initial_conditions)

        # Add volumne of the ship transiting the lock
        for cham in ['LC', 'MC', 'UC']:
            self.chambers[cham].add_ship(V_ship)
        
        # Add gate opening times to lock heads dictionary
        self.lock_heads['tOpen'] = t_open_dict
        
        # Lockage process

        ## 1) Drain the lock chamber to the level of the ocean
        h_drain_ocean = self.chambers['LC'].get_current_level() - H_ocean
        self.chambers['LC'].drain_chamber(h_drain=h_drain_ocean)

        ## 2) Transit from ocean to lower chamber
        Eff = self.lock_exchange_factor(lock_head='LH4', S_ocean=S_ocean)
        self.chambers['LC'].ship_enters(E_lhs=Eff, S_lhs=S_ocean)
        print(f'Ocean-LC Eff: {Eff}')

        ## 3) Equalization and transit between LC and MC
        self.eq_and_cross(lock_head='LH3', direction='up')
 
        ## 4) Equalization and transit between MC and UC
        self.eq_and_cross(lock_head='LH2', direction='up')

        ## 5) Lift the ship to the level of the lake
        h_lift_lake = H_lake - self.chambers['UC'].get_current_level()
        self.chambers['UC'].fill_chamber(h_lift=h_lift_lake, S_lift=S_lake)

        ## 6) Ship leaves the upper chamber of the lock
        Eff = self.lock_exchange_factor(lock_head='LH1', S_lake=S_lake)
        self.chambers['UC'].ship_leaves(E_rhs=Eff, S_rhs=S_lake)
        print(f'UC-Lake Eff: {Eff}')
    
    # TODO: Implement the transit_down method.

    # TODO: Figure out a way to keep track of salinity in time. 
    #       For instance, salinity in the middle chamber only starts
    #       changing after the ship leaves the lower chamber, and for the
    #       previous time steps, it remains constant.

    # TODO: Check equalization method. Last level of a chamber should be the
    #       same as the initial level of the next chamber and currently this
    #       is not the case.

