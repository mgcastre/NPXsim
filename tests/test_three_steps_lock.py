"""Tests for the basic methods in ThreeStepsLock."""

import pytest

from npxsim.model.custom_exceptions import WaterLevelError
from npxsim.model.three_steps_lock import ThreeStepsLock


def test_init_creates_lock_chambers_and_lock_heads(three_steps_lock):
    assert set(three_steps_lock.chambers.keys()) == {'LC', 'MC', 'UC'}
    assert three_steps_lock.lock_heads['Chambers']['LH1'] == ['UC']
    assert three_steps_lock.lock_heads['Chambers'][next(iter(three_steps_lock.lock_heads['Chambers']))]


def test_calc_cham_operational_levels_orders_chambers_top_to_bottom(three_steps_lock):
    levels = three_steps_lock.calc_cham_operational_levels(H_lake=27, H_ocean=0)
    assert levels['UC'][1] == 27  # Upper chamber's high level matches the lake
    assert levels['LC'][0] == 0   # Lower chamber's low level matches the ocean
    # Each chamber's low level should not exceed its high level
    for low, high in levels.values():
        assert low <= high
    # Chambers should be stacked: LC <= MC <= UC
    assert levels['LC'][1] == pytest.approx(levels['MC'][0])
    assert levels['MC'][1] == pytest.approx(levels['UC'][0])


def test_calc_initial_levels_depends_on_direction(three_steps_lock):
    up_levels = three_steps_lock.calc_initial_levels(H_lake=27, H_ocean=0, direction='up')
    down_levels = three_steps_lock.calc_initial_levels(H_lake=27, H_ocean=0, direction='down')
    op_levels = three_steps_lock.calc_cham_operational_levels(H_lake=27, H_ocean=0)
    assert up_levels['MC'] == op_levels['MC'][1]
    assert down_levels['MC'] == op_levels['MC'][0]
    # LC and UC initial levels do not depend on direction
    assert up_levels['LC'] == down_levels['LC'] == op_levels['LC'][0]
    assert up_levels['UC'] == down_levels['UC'] == op_levels['UC'][1]


def test_set_initial_conditions_populates_chambers(three_steps_lock):
    boundary_conditions = {'H_lake': 27, 'H_ocean': 0}
    salinities = {'LC': 30.0, 'MC': 15.0, 'UC': 1.0}
    three_steps_lock.set_initial_conditions(
        boundary_conditions=boundary_conditions, salinities=salinities,
        direction='up', operation_start_dt='2026-01-01 00:00:00',
    )
    assert three_steps_lock.operation_start_dt == '2026-01-01 00:00:00'
    assert three_steps_lock.T == 28
    for cham, salinity in salinities.items():
        assert three_steps_lock.chambers[cham].get_current_salinity() == salinity
    assert three_steps_lock.salt_mass_load == {'Num': [], 'TS': [], 'DC': [], 'VD': []}


def test_calc_elapsed_minutes(three_steps_lock):
    three_steps_lock.operation_start_dt = '2026-01-01 00:00:00'
    elapsed = three_steps_lock.calc_elapsed_minutes('2026-01-01 02:30:00')
    assert elapsed == pytest.approx(150)


def test_equalize_and_cross_raises_when_outside_operating_limits():
    # Build a lock whose MC and LC operating ranges do not overlap, so the
    # equalization level between them is guaranteed to fall outside one of them.
    cham_elevs = {'LC': (0, 30), 'MC': (10, 40), 'UC': (20, 50)}
    lock_head_sills = {'LH1': 20, 'LH2': 15, 'LH3': 10, 'LH4': 0}
    operating_limits = {'LC': (5, 15), 'MC': (25, 35), 'UC': (35, 45)}
    lock = ThreeStepsLock(
        lock_length=300, lock_width=55,
        cham_elevs=cham_elevs, lock_head_sills=lock_head_sills,
        operating_limits=operating_limits,
    )
    lock.chambers['LC'].add_initial_conditions(H0=10, S0=30.0)
    lock.chambers['MC'].add_initial_conditions(H0=30, S0=15.0)
    lock.chambers['UC'].add_initial_conditions(H0=40, S0=1.0)
    lock.operation_start_dt = '2026-01-01 00:00:00'
    lock.T = 28
    lock.eqTime = {'UC': 10, 'MC': 10, 'LC': 10}
    with pytest.raises(WaterLevelError):
        lock.equalize_and_cross(lock_head='LH3', direction='up', init_time=0)
