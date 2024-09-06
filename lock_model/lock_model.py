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
    
    def drain_chamber(self, H_final):
        V_final = (H_final - self.z_bottom)*self.area
        # Although water level changes, salinity remains constant
        self.update_status(V=V_final, S=self.salinity[-1], H=H_final)
    
    def ship_enters(self, E_lhs, S_lhs):
        V_init, S_init = self.get_current_status()
        V_final = V_init - self.V_ship
        V_lhs = E_lhs*V_final
        S_final = (S_init*(V_init - V_lhs - self.V_ship) + V_lhs*S_lhs) / V_final
        # Although volume of water gets exchanged, the water level remains constant
        self.update_status(V=V_final, S=S_final, H=self.water_level[-1])
    
    def fill_chamber(self, H_final, S_lift):
        V_init, S_init = self.get_current_status()
        dH = H_final - self.water_level[-1]
        V_lift = dH*self.area
        V_final = V_init + V_lift
        S_final = (V_lift*S_lift + V_init*S_init) / V_final
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
        # Initialize dict to store salt mass load to the lake
        self.salt_mass_load = {'DC': [], 'VD': []}
    
    def add_initial_conditions(self, initial_conditions):
        for cham in ['LC', 'MC', 'UC']:
            self.chambers[cham].add_initial_conditions(
                H0=initial_conditions['H0'][cham], 
                S0=initial_conditions['S0'][cham]
            )

    def calc_equalization_level(self, cham1, cham2):
        A1 = self.chambers[cham1].area
        A2 = self.chambers[cham2].area
        H1 = self.chambers[cham1].get_current_level()
        H2 = self.chambers[cham2].get_current_level()
        Hf = (A1*H1 + A2*H2) / (A1 + A2)
        return Hf
    
    def equalize_levels(self, cham1, cham2):
        Hf = self.calc_equalization_level(cham1, cham2)
        self.chambers[cham2].drain_chamber(H_final=Hf)
        S_next_cham = self.chambers[cham2].get_current_salinity()
        self.chambers[cham1].fill_chamber(H_final=Hf, S_lift=S_next_cham)
        return Hf
    
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
        return Eff
    
    def eq_and_cross(self, lock_head, direction):
        lower_cham, upper_cham = self.lock_heads['Chambers'][lock_head]
        if direction == 'up':
            cham1 = lower_cham
            cham2 = upper_cham
        elif direction == 'down':
            cham1 = upper_cham
            cham2 = lower_cham
        Hf = self.equalize_levels(cham1, cham2)
        Eff = self.cross_lock_head(cham1, cham2, lock_head)
        return Hf, Eff
    
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
        self.chambers['LC'].drain_chamber(H_final=H_ocean)

        ## 2) Transit from ocean to lower chamber
        E_lh4 = self.lock_exchange_factor(lock_head='LH4', S_ocean=S_ocean)
        self.chambers['LC'].ship_enters(E_lhs=E_lh4, S_lhs=S_ocean)

        ## 3) Equalization and transit between LC and MC
        H_lh3, E_lh3 = self.eq_and_cross(lock_head='LH3', direction='up')
 
        ## 4) Equalization and transit between MC and UC
        H_lh2, E_lh2 = self.eq_and_cross(lock_head='LH2', direction='up')

        ## 5) Lift the ship to the level of the lake
        self.chambers['UC'].fill_chamber(H_final=H_lake, S_lift=S_lake)

        ## 6) Ship leaves the upper chamber of the lock
        E_lh1 = self.lock_exchange_factor(lock_head='LH1', S_lake=S_lake)
        self.chambers['UC'].ship_leaves(E_rhs=E_lh1, S_rhs=S_lake)

        # Calculate salt mass load to the lake
        S_chamber = self.chambers['UC'].get_current_salinity()
        V_chamber = self.chambers['UC'].get_current_volume()
        V_ex = E_lh1*V_chamber # Ship is already in chamber
        rho_chamber = hd.Rho_from_PSU(S_chamber, Temp=28)
        rho_lake = hd.Rho_from_PSU(S_lake, Temp=28)
        m_dc = V_ex*(rho_chamber - rho_lake)
        m_vd = (rho_lake - rho_chamber)*V_ship
        self.salt_mass_load['DC'].append(m_dc)
        self.salt_mass_load['VD'].append(m_vd)
    
    def get_salt_load(self, Total=False, Units='kg'):
        """
        Returns the salt mass load etering the lake from the upper chamber.
        By default it returns a tupple with two elements: The first is the 
        salt mass load due to density current (DC) and the second is the salt
        mass load due to vessel displacement (VD). If Total is set to True, it
        returns the sum of both. Optionally, the units of the salt mass load 
        can be specified. By default, it returns the mass in kilograms, but
        it can also be returned in tonnes by setting Units to 'ton'.
        """	
        sm_dc = np.array(self.salt_mass_load['DC'])
        sm_vd = np.array(self.salt_mass_load['VD'])
        if Units == 'ton':
            sm_dc = sm_dc/1000
            sm_vd = sm_vd/1000
        if Total:
            return sm_dc + sm_vd
        else:
            return sm_dc, sm_vd
    
    # TODO: Implement the transit_down method.

    # TODO: Figure out a way to keep track of salinity in time. 
    #       For instance, salinity in the middle chamber only starts
    #       changing after the ship leaves the lower chamber, and for the
    #       previous time steps, it remains constant.

    # TODO: Check equalization method. Last level of a chamber should be the
    #       same as the initial level of the next chamber and currently this
    #       is not the case.

