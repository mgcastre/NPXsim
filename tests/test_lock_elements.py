"""Tests for the basic reservoir/chamber/basin methods in lock_elements.py."""

import pytest


class TestControlVolume:

    def test_init_computes_area(self, control_volume):
        assert control_volume.area == control_volume.length * control_volume.width

    def test_initial_conditions_set_state(self, control_volume):
        assert control_volume.water_level == [10]
        assert control_volume.salinity == [2.0]
        assert control_volume.time == [0]
        assert control_volume.water_volume == [(10 - 0) * control_volume.area]

    def test_get_operating_limits(self, control_volume):
        assert control_volume.get_operating_limits() == (5, 15)

    def test_get_current_status(self, control_volume):
        V, S = control_volume.get_current_status()
        assert V == control_volume.water_volume[-1]
        assert S == control_volume.salinity[-1]
        assert control_volume.get_current_volume() == V
        assert control_volume.get_current_salinity() == S
        assert control_volume.get_current_level() == control_volume.water_level[-1]

    def test_update_status_appends_to_history(self, control_volume):
        control_volume.update_status(V=123, S=4.5, H=11, ts=10)
        assert control_volume.time[-1] == 10
        assert control_volume.water_level[-1] == 11
        assert control_volume.water_volume[-1] == 123
        assert control_volume.salinity[-1] == 4.5

    def test_record_current_status_repeats_latest_values(self, control_volume):
        before = control_volume.get_current_status()
        control_volume.record_current_status(ts=5)
        assert control_volume.time[-1] == 5
        assert control_volume.get_current_status() == before

    def test_drain_keeps_salinity_constant(self, control_volume):
        initial_salinity = control_volume.get_current_salinity()
        control_volume._drain(H_final=8, ts=20)
        assert control_volume.get_current_level() == 8
        assert control_volume.get_current_salinity() == initial_salinity
        assert control_volume.get_current_volume() == (8 - control_volume.z_bottom) * control_volume.area

    def test_fill_mixes_salinity(self, control_volume):
        V_init, S_init = control_volume.get_current_status()
        control_volume._fill(H_final=12, S_lift=5.0, ts=30)
        assert control_volume.get_current_level() == 12
        # New salinity should be a volume-weighted mix between the lifted and initial salinity
        assert S_init < control_volume.get_current_salinity() < 5.0

    def test_get_results_dictionary_has_expected_keys(self, control_volume):
        results = control_volume.get_results_dictionary()
        assert set(results.keys()) == {'Time', 'Volume', 'Level', 'Salinity'}
        assert results['Level'] == control_volume.water_level


class TestLockChamber:

    def test_change_length_updates_attribute(self, lock_chamber):
        lock_chamber.change_length(250)
        assert lock_chamber.length == 250

    def test_add_ship_sets_volume(self, lock_chamber):
        lock_chamber.add_ship(V_ship=2000)
        assert lock_chamber.V_ship == 2000

    def test_drain_and_fill_chamber_delegate_to_control_volume(self, lock_chamber):
        lock_chamber.drain_chamber(H_final=8, ts=10)
        assert lock_chamber.get_current_level() == 8
        lock_chamber.fill_chamber(H_final=11, S_lift=3.0, ts=20)
        assert lock_chamber.get_current_level() == 11

    def test_ship_enters_keeps_level_constant_and_mixes_salinity(self, lock_chamber):
        H_before = lock_chamber.get_current_level()
        V_before, S_before = lock_chamber.get_current_status()
        lock_chamber.ship_enters(V_lhs=500, S_lhs=10.0, ts=15)
        assert lock_chamber.get_current_level() == H_before
        assert lock_chamber.get_current_volume() == V_before - lock_chamber.V_ship
        assert lock_chamber.get_current_salinity() != S_before

    def test_ship_leaves_keeps_level_constant_and_mixes_salinity(self, lock_chamber):
        H_before = lock_chamber.get_current_level()
        V_before, S_before = lock_chamber.get_current_status()
        lock_chamber.ship_leaves(V_rhs=500, S_rhs=1.0, ts=25)
        assert lock_chamber.get_current_level() == H_before
        assert lock_chamber.get_current_volume() == V_before + lock_chamber.V_ship
        assert lock_chamber.get_current_salinity() != S_before


class TestWaterSavingBasin:

    def test_basin_starts_without_state_until_initialized(self, water_saving_basin):
        assert not hasattr(water_saving_basin, 'water_level')

    def test_add_initial_conditions_then_drain_and_fill(self, water_saving_basin):
        water_saving_basin.add_initial_conditions(H0=6, S0=1.5)
        water_saving_basin.drain_basin(H_final=5, ts=10)
        assert water_saving_basin.get_current_level() == 5
        assert water_saving_basin.get_current_salinity() == 1.5

        water_saving_basin.fill_basin(H_final=7, S_lift=4.0, ts=20)
        assert water_saving_basin.get_current_level() == 7
        assert 1.5 < water_saving_basin.get_current_salinity() < 4.0
