"""Shared fixtures for the NPXsim test suite."""

import pytest

from npxsim.model.lock_elements import ControlVolume, LockChamber, WaterSavingBasin
from npxsim.model.three_steps_lock import ThreeStepsLock


@pytest.fixture
def control_volume():
    """A generic reservoir with initial conditions already set."""
    return ControlVolume(
        length=100, width=50, z_bottom=0, z_top=20,
        H_min=5, H_max=15, H0=10, S0=2.0,
    )


@pytest.fixture
def lock_chamber():
    """A lock chamber with initial conditions and a ship already loaded."""
    chamber = LockChamber(
        length=100, width=50, z_bottom=0, z_top=20,
        H_min=5, H_max=15, H0=10, S0=2.0,
    )
    chamber.add_ship(V_ship=1000)
    return chamber


@pytest.fixture
def water_saving_basin():
    """A water saving basin without initial conditions (matches real usage)."""
    return WaterSavingBasin(
        length=80, width=40, z_bottom=0, z_top=20,
        H_min=4, H_max=16,
    )


@pytest.fixture
def three_steps_lock():
    """A minimal three-steps lock with three chambers (LC, MC, UC)."""
    cham_elevs = {'LC': (0, 30), 'MC': (10, 40), 'UC': (20, 50)}
    lock_head_sills = {'LH1': 20, 'LH2': 15, 'LH3': 10, 'LH4': 0}
    operating_limits = {'LC': (5, 25), 'MC': (15, 35), 'UC': (25, 45)}
    return ThreeStepsLock(
        lock_length=300, lock_width=55,
        cham_elevs=cham_elevs, lock_head_sills=lock_head_sills,
        operating_limits=operating_limits,
    )
