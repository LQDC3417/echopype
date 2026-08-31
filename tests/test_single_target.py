import numpy as np
import pytest
import xarray as xr

from src.core import sed


def test_real_sed_preserves_nonzero_echo_range_origin(monkeypatch):
    beam_group = xr.Dataset(
        {
            "backscatter_r": (("ping_time", "range_sample", "beam"), np.ones((1, 3, 4))),
            "backscatter_i": (("ping_time", "range_sample", "beam"), np.zeros((1, 3, 4))),
        }
    )
    echodata = {"Sonar/Beam_group1": beam_group}
    ds_ts = xr.Dataset(
        {"TS": (("ping_time", "range_sample"), [[-80.0, -40.0, -80.0]])},
        coords={"echo_range": ("range_sample", [10.0, 11.0, 12.0])},
    )
    monkeypatch.setattr(
        sed,
        "_detect_ping_candidates",
        lambda *_args: [{"peak_idx": 1, "left": 0, "right": 2, "peak_ts": -40.0, "pulse_len": 3, "norm_pulse": 1.0}],
    )
    monkeypatch.setattr(
        sed,
        "compute_split_beam_angles",
        lambda window, *_args: (np.zeros(len(window)), np.zeros(len(window))),
    )

    result = sed.detect_single_targets_real(echodata, ds_ts, {})

    assert result.loc[0, "range_m"] == pytest.approx(11.0)
