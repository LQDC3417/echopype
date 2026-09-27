
import numpy as np
import pandas as pd
import xarray as xr

from src.core.export import export_sv_to_csv, export_to_netcdf


def test_export_preserves_channels_and_navigation(tmp_path):
    dataset = xr.Dataset(
        {"Sv": (("channel", "ping_time", "range_sample"), np.array([[[-50.0]], [[-60.0]]])),
         "latitude": ("ping_time", [30.0]), "longitude": ("ping_time", [120.0])},
        coords={"channel": ["38k", "120k"], "ping_time": [np.datetime64("2026-01-01", "ns")], "range_sample": [0]},
    )
    output = export_sv_to_csv(dataset, tmp_path / "sv.csv")
    frame = pd.read_csv(output)
    assert frame["channel"].tolist() == ["38k", "120k"]
    assert frame["Sv"].tolist() == [-50.0, -60.0]
    output = export_to_netcdf(dataset, tmp_path / "sv.nc")
    with xr.open_dataset(output, engine="h5netcdf") as restored:
        xr.testing.assert_equal(restored, dataset)


def test_netcdf_omits_optional_none_attributes_without_mutating_source(tmp_path):
    dataset = xr.Dataset({"Sv_corrected": ("sample", [-50.])}, attrs={"optional": None})
    dataset.Sv_corrected.attrs = {"noise_max": None, "units": "dB"}
    output = export_to_netcdf(dataset, tmp_path / "clean.nc")
    with xr.open_dataset(output, engine="h5netcdf") as restored:
        assert restored.Sv_corrected.attrs == {"units": "dB"}
        assert "optional" not in restored.attrs
    assert dataset.Sv_corrected.attrs["noise_max"] is None
    assert dataset.attrs["optional"] is None
