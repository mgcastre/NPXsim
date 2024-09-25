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
    
    def ship_enters(self, V_lhs, S_lhs):
        V_init, S_init = self.get_current_status()
        V_final = V_init - self.V_ship
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
    
    def ship_leaves(self, V_rhs, S_rhs):
        V_init, S_init = self.get_current_status()
        V_final = V_init + self.V_ship
        S_final = (S_init*(V_init - V_rhs) + S_rhs*(V_rhs + self.V_ship)) / V_final
        # Although volume of water gets exchanged, the water level remains constant
        self.update_status(V=V_final, S=S_final, H=self.water_level[-1])


class ThreeStepLock:

    def __init__(self, lock_length, lock_width, 
                 lock_bottom_elevs, lock_head_sills):
        # Initialize lock chamber objects
        self.chambers = {}
        for cham in ['LC', 'MC', 'UC']:
            self.chambers[cham] = LockChamber(
                length=lock_length, width=lock_width,
                z_bottom=lock_bottom_elevs[cham],
                S0=None, H0=None
            )
        # Create attributes for lock heads
        self.lock_heads = {'Z': lock_head_sills}
        self.lock_heads['Chambers'] = {
            'LH1': ['UC'], 
            'LH2': ['MC', 'UC'],
            'LH3': ['LC', 'MC'], 
            'LH4': ['LC']
        }
    
    def calc_operational_levels(self, H_lake, H_ocean):
        # Extract chamber areas
        Au = self.chambers['UC'].area
        Am = self.chambers['MC'].area
        Al = self.chambers['LC'].area
        # Calculate operational levels
        denominator = ((Am + Al)*(Au + Am)/Am) - Am
        numerator = H_ocean*Al + (Am + Al)*H_lake*Au/Am
        uc_high = H_lake
        uc_low = numerator/denominator
        mc_high = uc_low
        mc_low = ((Au + Am)/Am)*mc_high - H_lake*Au/Am
        lc_high = mc_low
        lc_low = H_ocean
        # Store operational levels in a dictionary
        operational_levels = {}
        operational_levels['UC'] = (uc_low, uc_high)
        operational_levels['MC'] = (mc_low, mc_high)
        operational_levels['LC'] = (lc_low, lc_high)
        # Return operational levels
        return operational_levels
    
    def initialize(self, boundary_conditions, salinities, direction):
        cham_levels = {}
        H_lake = boundary_conditions['H_lake']
        H_ocean = boundary_conditions['H_ocean']
        op_levels = self.calc_operational_levels(H_lake, H_ocean)
        if direction == 'up':
            # For uplockage, the lower chamber is at the level of the ocean
            # and the rest of the chambers are at their higher operational levels.
            cham_levels['LC'] = H_ocean
            cham_levels['MC'] = op_levels['MC'][1]
            cham_levels['UC'] = op_levels['UC'][1]
        if direction == 'down':
            # For downlockage, the upper chamber is at the level of the lake
            # and the rest of the chambers are at their lower operational levels.
            cham_levels['UC'] = H_lake
            cham_levels['MC'] = op_levels['MC'][0]
            cham_levels['LC'] = op_levels['LC'][0]
        # Add initial conditions to the lock chambers.
        for cham in ['LC', 'MC', 'UC']:
            self.chambers[cham].add_initial_conditions(
                H0=cham_levels[cham], S0=salinities[cham]
            )
        # Initialize dict to store salt mass load to the lake
        self.salt_mass_load = {'DC': [], 'VD': [], 'Eff': [], 'V_ex': []}
    
    def turnaround(self, H_lake, H_ocean, direction):
        cham_levels = {}
        op_levels = self.calc_operational_levels(H_lake, H_ocean)
        if direction == 'up':
            cham_levels['UC'] = H_lake
            cham_levels['MC'] = op_levels['MC'][1]
            cham_levels['LC'] = op_levels['LC'][1]
        if direction == 'down':
            cham_levels['UC'] = op_levels['UC'][1]
            cham_levels['MC'] = op_levels['MC'][0]
            cham_levels['LC'] = op_levels['LC'][0]
        # TODO: Figure out how to properly do the salinity mass balance 
        #       and water balance calculations for the turnaround process.
    
    def extract_properties(self, cham):
        W = self.chambers[cham].width
        L = self.chambers[cham].length
        H = self.chambers[cham].get_current_level()
        return W, L, H
    
    def lock_exchange_factor(self, lock_head, S_boundary=None):
        # Extract salinity and water levels
        if lock_head == 'LH1':
            _, L, H = self.extract_properties('UC')
            S_lhs = self.chambers['UC'].get_current_salinity()
            S_rhs = S_boundary
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
            S_lhs = S_boundary
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
    
    def calc_equalization_level(self, cham1, cham2):
        A1 = self.chambers[cham1].area
        A2 = self.chambers[cham2].area
        H1 = self.chambers[cham1].get_current_level()
        H2 = self.chambers[cham2].get_current_level()
        Hf = (A1*H1 + A2*H2) / (A1 + A2)
        return Hf
    
    def equalize_levels(self, lower_cham, upper_cham, return_level=False):
        Hf = self.calc_equalization_level(lower_cham, upper_cham)
        self.chambers[upper_cham].drain_chamber(H_final=Hf)
        S_next_cham = self.chambers[upper_cham].get_current_salinity()
        self.chambers[lower_cham].fill_chamber(H_final=Hf, S_lift=S_next_cham)
        if return_level:
            return Hf
    
    def equalize_and_cross(self, lock_head, direction):
        # 1. Equalize levels between chambers
        ## 1.1 Calculate final level for equalization
        lower_cham, upper_cham = self.lock_heads['Chambers'][lock_head]
        Hf = self.calc_equalization_level(lower_cham, upper_cham)
        ## 1.2. Drain upper chamber to equalization level
        self.chambers[upper_cham].drain_chamber(H_final=Hf)
        ## 1.3. Fill lower chamber to equalization level
        S_upper_cham = self.chambers[upper_cham].get_current_salinity()
        self.chambers[lower_cham].fill_chamber(H_final=Hf, S_lift=S_upper_cham)
        # 2. Open lock gates and move ship between chambers
        ## 2.1 Assign order of chambers depending on direction
        if direction == 'up':
            cham1 = lower_cham
            cham2 = upper_cham
        elif direction == 'down':
            cham1 = upper_cham
            cham2 = lower_cham
        ## 2.2. Calculate volume of water to be exchanged
        Eff = self.lock_exchange_factor(lock_head)
        V_ex = self.calc_volume_exchanged(Eff=Eff, cham=upper_cham)
        ## 2.3 Move ship between chambers
        S_cham1 = self.chambers[cham1].get_current_salinity()
        S_cham2 = self.chambers[cham2].get_current_salinity()
        self.chambers[cham1].ship_leaves(V_rhs=V_ex, S_rhs=S_cham2)
        self.chambers[cham2].ship_enters(V_lhs=V_ex, S_lhs=S_cham1)
    
    def calc_salt_mass_load(self, S_lake, V_ex_lake, S_chamber, direction, T=28):
        rho_chamber = hd.Rho_from_PSU(S_chamber, Temp=T)
        rho_lake = hd.Rho_from_PSU(S_lake, Temp=T)
        m_dc = V_ex_lake*(rho_chamber - rho_lake)
        if direction == 'up':
            m_vd = (rho_lake - rho_chamber)*self.V_ship
        elif direction == 'down':
            m_vd = (rho_chamber - rho_lake)*self.V_ship
        self.salt_mass_load['DC'].append(m_dc)
        self.salt_mass_load['VD'].append(m_vd)
    
    def calc_volume_exchanged(self, Eff, cham):
        Hf = self.chambers[cham].get_current_level()
        if cham == 'UC':
            h = Hf - self.lock_heads['Z']['LH1']
        else:
            h = Hf - self.chambers[cham].z_bottom
        A = self.chambers[cham].area
        V_ex = Eff*(A*h - self.V_ship)
        return V_ex
    
    def exchange_with_lake(self, S_lake,  direction):
        # Calculate volume of water to be exchanged
        Eff = self.lock_exchange_factor(lock_head='LH1', S_boundary=S_lake)
        V_ex_lake = self.calc_volume_exchanged(Eff=Eff, cham='UC')
        # Calculate salt mass load to the lake
        S_chamber = self.chambers['UC'].get_current_salinity()
        self.calc_salt_mass_load(S_lake, V_ex_lake, S_chamber, direction)
        # Return and append values
        self.salt_mass_load['V_ex'].append(V_ex_lake)
        self.salt_mass_load['Eff'].append(Eff)
        return V_ex_lake
    
    def exchange_with_ocean(self, S_ocean):
        Eff = self.lock_exchange_factor(lock_head='LH4', S_boundary=S_ocean)
        V_ex_ocean = self.calc_volume_exchanged(Eff=Eff, cham='LC')
        return V_ex_ocean
    
    def transit(self, V_ship, t_open_dict, boundary_conditions, direction):
        
        # Extract boundary conditions
        S_ocean = boundary_conditions['S_ocean']
        H_ocean = boundary_conditions['H_ocean']
        S_lake = boundary_conditions['S_lake']
        H_lake = boundary_conditions['H_lake']

        # Add volumne of the ship transiting the lock
        self.V_ship = V_ship
        for cham in ['LC', 'MC', 'UC']:
            self.chambers[cham].add_ship(V_ship)
        
        # Add gate opening times to lock heads dictionary
        self.lock_heads['tOpen'] = t_open_dict
        
        # Provess for uplockage
        if direction == 'up':
            ## 1) Drain the lock chamber to the level of the ocean
            self.chambers['LC'].drain_chamber(H_final=H_ocean)
            ## 2) Gates at LH4 open, salinity enters from the ocean and ship enters the lock
            V_ex_ocean = self.exchange_with_ocean(S_ocean=S_ocean)
            self.chambers['LC'].ship_enters(V_lhs=V_ex_ocean, S_lhs=S_ocean)
            ## 3) Equalization and transit between LC and MC
            self.equalize_and_cross(lock_head='LH3', direction='up')
            ## 4) Equalization and transit between MC and UC
            self.equalize_and_cross(lock_head='LH2', direction='up')
            ## 5) Lift the ship to the level of the lake
            self.chambers['UC'].fill_chamber(H_final=H_lake, S_lift=S_lake)
            ## 6) Gates at LH1 open, salt mass enters the lake and ship leaves the lock
            V_ex_lake = self.exchange_with_lake(S_lake=S_lake, direction='up')
            self.chambers['UC'].ship_leaves(V_rhs=V_ex_lake, S_rhs=S_lake)
        
        # Process for downlocakge
        elif direction == 'down':
            ## 1) Lift upper chamber to level of the lake
            self.chambers['UC'].fill_chamber(H_final=H_lake, S_lift=S_lake)
            ## 2) Gates at LH1 open, salt mass enters the lake and ship enters the lock
            V_ex_lake = self.exchange_with_lake(S_lake=S_lake, direction='down')
            self.chambers['UC'].ship_enters(V_lhs=V_ex_lake, S_lhs=S_lake)
            ## 3) Equalization and transit between UC and MC
            self.equalize_and_cross(lock_head='LH2', direction='down')
            ## 4) Equalization and transit between MC and LC
            self.equalize_and_cross(lock_head='LH3', direction='down')
            ## 5) Drain to the level of the ocean
            self.chambers['LC'].drain_chamber(H_final=H_ocean)
            ## 6) Gates at LH4 open, salinity enters from the ocean and ship leaves the lock
            V_ex_ocean = self.exchange_with_ocean(S_ocean=S_ocean)  
            self.chambers['LC'].ship_leaves(V_rhs=V_ex_ocean, S_rhs=S_ocean)
        
        # Raise an error if the direction is not valid
        else:
            raise ValueError("Direction must be either 'up' or 'down'.")

    
    def get_salt_load(self, Units='ton', Dictionary=True):
        """
        Returns the salt mass load etering the lake from the upper chamber.
        By default it returns a dictionary with the keys 'DC', 'VD', and 'Total'.
        If Dictionary is set to False, it returns the values in a tuple.
        By default, it returns the mass in tonnes, but it can also be returned in 
        kilogram by setting Units to 'kg'.
        """	
        sm_dc = np.array(self.salt_mass_load['DC'])
        sm_vd = np.array(self.salt_mass_load['VD'])
        if Units == 'ton':
            sm_dc = sm_dc/1000
            sm_vd = sm_vd/1000
        m_total = sm_dc + sm_vd
        if Dictionary:
            return {'DC': sm_dc, 'VD': sm_vd, 'Total': m_total}
        else:
            return sm_dc, sm_vd, m_total
    
    def get_salinities(self):
        """
        Returns the salinity of each chamber in the lock model.
        """
        salinities = {}
        for chamber in ['LC', 'MC', 'UC']:
            salinities[chamber] = self.chambers[chamber].salinity
        return salinities
    
    # TODO: Implement the transit_down method.

