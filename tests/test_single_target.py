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

    ds_ts["depth"] = ds_ts.echo_range + 5
    result = sed.detect_single_targets_real(
        echodata, ds_ts, {"single_target_real": {"min_depth_m": 15}}
    )
    assert len(result) == 1
    assert result.loc[0, "range_m"] == pytest.approx(11.0)
    assert result.loc[0, "depth_m"] == pytest.approx(16.0)
    assert len(sed.filter_targets_by_region(result, np.array([15.]), np.array([17.]))) == 1


def test_real_sed_selects_one_channel_without_leaking_channel_dimension(monkeypatch):
    channels = ["38kHz", "120kHz"]
    echodata = {"Sonar/Beam_group1": xr.Dataset(
        {"backscatter_r": (("channel", "ping_time", "range_sample", "beam"),
                           np.ones((2, 1, 3, 4))),
         "backscatter_i": (("channel", "ping_time", "range_sample", "beam"),
                           np.zeros((2, 1, 3, 4)))},
        coords={"channel": channels},
    )}
    ds_ts = xr.Dataset(
        {"TS": (("channel", "ping_time", "range_sample"),
                [[[-80., -40., -80.]], [[-80., -35., -80.]]]),
         "echo_range": (("channel", "range_sample"), [[10., 11., 12.], [20., 21., 22.]]),
         "depth": (("channel", "range_sample"), [[15., 16., 17.], [25., 26., 27.]])},
        coords={"channel": channels},
    )
    monkeypatch.setattr(sed, "_detect_ping_candidates", lambda *_args: [
        {"peak_idx": 1, "left": 0, "right": 2, "peak_ts": -35.,
         "pulse_len": 3, "norm_pulse": 1.},
    ])
    monkeypatch.setattr(sed, "compute_split_beam_angles", lambda window, *_args: (
        np.zeros(len(window)), np.zeros(len(window)),
    ))

    result = sed.detect_single_targets_real(echodata, ds_ts, {}, channel_id="120kHz")

    assert len(result) == 1
    assert result.loc[0, "channel"] == "120kHz"
    assert result.loc[0, "range_m"] == pytest.approx(21.)
    assert result.loc[0, "depth_m"] == pytest.approx(26.)
