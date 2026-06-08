"""Tests for the basic data-wrangling helpers in helper_functions.py."""

import pandas as pd
import pytest

import npxsim.utilities.helper_functions as hf


@pytest.fixture
def lock_operations_df():
    return pd.DataFrame({
        'Date_Time': [
            '2026-01-01 00:00:00',
            '2026-01-02 00:00:00',
            '2026-01-03 00:00:00',
            '2026-01-04 00:00:00',
        ],
        'Ocean_Salinity': [35.0, 35.5, 36.0, 36.5],
        'Ocean_Level': [0.0, 0.1, 0.2, 0.3],
        'Lake_Salinity': [0.5, 0.5, 0.5, 0.5],
        'Lake_Level': [25.0, 25.1, 25.2, 25.3],
    })


def test_filter_date_range_keeps_only_rows_inside_bounds(lock_operations_df):
    filtered = hf.filter_date_range(
        lock_operations_df.copy(),
        start_date='2026-01-02', end_date='2026-01-03',
    )
    assert len(filtered) == 2
    assert filtered['Date_Time'].min() == pd.Timestamp('2026-01-02')
    assert filtered['Date_Time'].max() == pd.Timestamp('2026-01-03')


def test_prepare_boundary_conditions_renames_and_selects_columns(lock_operations_df):
    boundary_conditions = hf.prepare_boundary_conditions(lock_operations_df)
    assert isinstance(boundary_conditions, list)
    assert len(boundary_conditions) == len(lock_operations_df)
    first = boundary_conditions[0]
    assert set(first.keys()) == {'S_ocean', 'H_ocean', 'S_lake', 'H_lake'}
    assert first['S_ocean'] == lock_operations_df.loc[0, 'Ocean_Salinity']
    assert first['H_lake'] == lock_operations_df.loc[0, 'Lake_Level']
