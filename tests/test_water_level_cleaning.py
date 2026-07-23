import numpy as np
import pandas as pd
import pytest
import sys

sys.path.insert(0, './')

from fangreport.data_loading.water_level import clean_water_level


@pytest.fixture
def sample_river_data():
    """Generates a 5-day simulated time series with 15-minute intervals."""
    timestamps = pd.date_range(start="2026-01-01", periods=480, freq="15min")

    base_level = 150.0
    data = [base_level] * 480

    # Inject Outlier 1: Extreme global outlier at index 100 (sensor failure to 9999)
    data[100] = 9999.0

    # Inject Outlier 2: Single large isolated spike at index 300 (sudden jump to 450)
    data[300] = 450.0

    df = pd.DataFrame(data, index=timestamps, columns=["water_level"])
    return df, base_level



# 3. THE TESTS
def test_should_remove_single_large_outliers(sample_river_data):
    """Tests if single extreme spikes and global outliers are removed and interpolated."""
    df, base_level = sample_river_data

    df_cleaned = clean_water_level(df)

    assert not df_cleaned["water_level"].isna().any()

    # Verify indices using standard positional integer lookups
    assert df_cleaned["water_level"].iloc[100] != 9999.0

    assert df_cleaned["water_level"].iloc[300] != 450.0
    assert (
        np.all(
            [
                pytest.approx(df_cleaned["water_level"].iloc[i], abs=0.1) == base_level for i in range(df_cleaned.size)
            ]
        )
    )

    print(df_cleaned.min(), df_cleaned.max())


def test_should_keep_natural_flood_wave():
    """Tests that a steep but natural river level rise is NOT falsely removed."""
    timestamps = pd.date_range(start="2026-01-01", periods=100, freq="15min")

    # Simulate a steady river that experiences a rapid, realistic flood wave
    # Rising continuously from 100cm to 300cm (10cm increments)
    data = [100.0] * 40
    for i in range(1, 21):
        data.append(100.0 + (i * 10))
    data.extend([300.0] * 40)

    df_flood = pd.DataFrame(data, index=timestamps, columns=["water_level"])

    df_cleaned = clean_water_level(df_flood)

    # The peak of the flood (300.0) must remain completely untouched
    assert df_cleaned["water_level"].max() == 300.0

    # The frames must match perfectly now because no points were cleared
    pd.testing.assert_frame_equal(
        df_cleaned, df_flood[["water_level"]], check_dtype=False, atol=0.1
    )
