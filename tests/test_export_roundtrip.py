
import numpy as np
import pandas as pd
import pytest
import xarray as xr

from src.core.export import export_sv_to_csv, export_to_excel, export_to_netcdf, export_to_zarr
from src.gui.handlers import interaction_handlers
from src.gui.handlers.interaction_handlers import InteractionMixin


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


def test_excel_without_results_contains_explanation(tmp_path):
    output = export_to_excel(None, pd.DataFrame(), tmp_path / "results.xlsx")
    assert pd.ExcelFile(output).sheet_names == ["说明"]
    assert pd.read_excel(output, sheet_name="说明")["说明"].tolist() == [
        "当前没有鱼群或积分结果"
    ]


def test_zarr_roundtrip(tmp_path):
    dataset = xr.Dataset({"Sv": ("sample", [-50.0])})
    output = export_to_zarr(dataset, tmp_path / "sv_data.zarr")
    with xr.open_zarr(output, consolidated=False) as restored:
        xr.testing.assert_equal(restored, dataset)


def test_zarr_default_preserves_existing_directory(tmp_path):
    output = tmp_path / "sv_data.zarr"
    output.mkdir()
    marker = output / "keep.txt"
    marker.write_text("keep", encoding="utf-8")

    with pytest.raises(FileExistsError):
        export_to_zarr(xr.Dataset({"Sv": ("sample", [-50.0])}), output)

    assert marker.read_text(encoding="utf-8") == "keep"


def test_gui_zarr_only_exports_selected_sv(monkeypatch, tmp_path):
    dataset = xr.Dataset({"Sv": ("sample", [-50.0])})

    class Dialog:
        Accepted = 1

        def __init__(self, _parent):
            pass

        def exec(self):
            return self.Accepted

        def get_formats(self):
            return ["zarr"]

        def get_content(self):
            return {"sv": True, "schools": False, "grid": False}

    calls = []
    monkeypatch.setattr(interaction_handlers, "ExportDialog", Dialog)
    monkeypatch.setattr(
        "src.core.export.export_to_zarr",
        lambda ds, path: calls.append((ds, path)) or path,
    )
    host = type("Host", (), {})()
    host._config = {"output": {"dir": str(tmp_path)}}
    host._ds_Sv = dataset
    host._get_analysis_ds = lambda: dataset
    host._schools_df = None
    host._integration_df = None
    host._input_incomplete = False
    host.statusbar = type("StatusBar", (), {"set_status": lambda self, text: calls.append(text)})()

    InteractionMixin._export(host)

    assert calls[0] == (dataset, tmp_path / "sv_data.zarr")
    assert "1" in calls[1]


def test_gui_existing_zarr_reports_error_before_other_exports(monkeypatch, tmp_path):
    dataset = xr.Dataset({"Sv": ("sample", [-50.0])})
    existing = tmp_path / "sv_data.zarr"
    existing.mkdir()
    marker = existing / "keep.txt"
    marker.write_text("keep", encoding="utf-8")

    class Dialog:
        Accepted = 1

        def __init__(self, _parent):
            pass

        def exec(self):
            return self.Accepted

        def get_formats(self):
            return ["zarr", "netcdf"]

        def get_content(self):
            return {"sv": True, "schools": False, "grid": False}

    messages = []
    monkeypatch.setattr(interaction_handlers, "ExportDialog", Dialog)
    monkeypatch.setattr(interaction_handlers.QMessageBox, "warning",
                        lambda _parent, _title, message: messages.append(message))
    host = type("Host", (), {})()
    host._config = {"output": {"dir": str(tmp_path)}}
    host._ds_Sv = dataset
    host._get_analysis_ds = lambda: dataset
    host._schools_df = None
    host._integration_df = None
    host._input_incomplete = False
    host.statusbar = type("StatusBar", (), {"set_status": lambda self, text: messages.append(text)})()

    InteractionMixin._export(host)

    assert len(messages) == 1
    assert "sv_data.zarr" in messages[0]
    assert marker.read_text(encoding="utf-8") == "keep"
    assert not (tmp_path / "sv_data.nc").exists()
