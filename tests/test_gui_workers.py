"""GUI 工作线程的回归测试。"""

from pathlib import Path

import numpy as np
import xarray as xr


def _make_sv_dataset(value: float) -> xr.Dataset:
    """构造最小的 Sv 数据集。"""
    return xr.Dataset(
        {"Sv": (("ping_time", "range_sample"), np.array([[value]], dtype=np.float32))},
        coords={
            "ping_time": ("ping_time", np.array(["2026-01-01"], dtype="datetime64[ns]")),
            "echo_range": ("range_sample", np.array([1.0], dtype=np.float32)),
        },
    )


def test_merge_worker_skips_raw_echodata_combine_for_multiple_files(monkeypatch):
    """多文件导入不应因滤波器元数据维度不同而调用 combine_echodata。"""
    import echopype as ep

    from src.core import acoustic, merge
    from src.gui.workers import MergeFilesWorker

    raw_files = [Path("first.raw"), Path("second.raw")]
    echodata_by_path = {raw_files[0]: object(), raw_files[1]: object()}
    datasets = {
        echodata_by_path[raw_files[0]]: _make_sv_dataset(-40.0),
        echodata_by_path[raw_files[1]]: _make_sv_dataset(-41.0),
    }

    monkeypatch.setattr(
        acoustic,
        "open_single_file",
        lambda path, config: echodata_by_path[path],
    )
    monkeypatch.setattr(
        acoustic,
        "compute_sv",
        lambda echodata, config: datasets[echodata],
    )
    monkeypatch.setattr(merge, "merge_aligned", lambda ds_list, dedup=True: ds_list[0])

    def fail_combine(*args, **kwargs):
        raise AssertionError("多文件 GUI 导入不应调用 combine_echodata")

    monkeypatch.setattr(ep, "combine_echodata", fail_combine)

    worker = MergeFilesWorker(raw_files, config={})
    finished = []
    errors = []
    worker.finished.connect(finished.append)
    worker.error.connect(errors.append)

    worker.run()

    assert errors == []
    assert len(finished) == 1
    assert worker.echodata is None


def test_merge_worker_continues_after_one_file_fails(monkeypatch):
    """单个 raw 失败时应继续合并成功文件并返回失败报告。"""
    from src.core import acoustic, merge
    from src.gui.workers import MergeFilesWorker

    raw_files = [Path("good.raw"), Path("bad.raw"), Path("good2.raw")]
    echodata_by_path = {
        raw_files[0]: object(),
        raw_files[2]: object(),
    }
    datasets = {
        echodata_by_path[raw_files[0]]: _make_sv_dataset(-40.0),
        echodata_by_path[raw_files[2]]: _make_sv_dataset(-41.0),
    }

    def open_file(path, config):
        if path == raw_files[1]:
            raise OSError("损坏的 raw 文件")
        return echodata_by_path[path]

    monkeypatch.setattr(acoustic, "open_single_file", open_file)
    monkeypatch.setattr(
        acoustic,
        "compute_sv",
        lambda echodata, config: datasets[echodata],
    )
    monkeypatch.setattr(merge, "merge_aligned", lambda ds_list, dedup=True: ds_list[0])

    worker = MergeFilesWorker(raw_files, config={})
    finished = []
    errors = []
    worker.finished.connect(finished.append)
    worker.error.connect(errors.append)

    worker.run()

    assert errors == []
    assert len(finished) == 1
    result = finished[0]
    assert result.loaded_files == ("good.raw", "good2.raw")
    assert [item.path for item in result.failed_files] == ["bad.raw"]
    assert result.dataset["Sv"].values[0, 0] == -40.0


def test_merge_worker_reports_when_all_files_fail(monkeypatch):
    """全部 raw 失败时应通过 error 信号返回，不应让 QThread 未捕获异常。"""
    from src.core import acoustic
    from src.gui.workers import MergeFilesWorker

    raw_files = [Path("bad1.raw"), Path("bad2.raw")]

    def open_file(path, config):
        raise OSError(f"无法读取 {path.name}")

    monkeypatch.setattr(acoustic, "open_single_file", open_file)

    worker = MergeFilesWorker(raw_files, config={})
    finished = []
    errors = []
    worker.finished.connect(finished.append)
    worker.error.connect(errors.append)

    worker.run()

    assert finished == []
    assert len(errors) == 1
    assert "bad1.raw" in errors[0]
    assert "bad2.raw" in errors[0]


def test_bottom_worker_returns_valid_point_diagnostics(monkeypatch):
    """底线 worker 应返回有效点统计，便于区分算法无结果和渲染未显示。"""
    from src.core import bottom_detection, region
    from src.gui.workers import BottomDetectionResult, DetectSeafloorWorker

    monkeypatch.setattr(
        bottom_detection,
        "detect_bottom",
        lambda *args, **kwargs: np.array([10.0, np.nan, 30.0]),
    )
    monkeypatch.setattr(
        region,
        "get_echo_range_1d",
        lambda ds: np.array([0.0, 10.0, 20.0, 30.0]),
    )
    monkeypatch.setattr(
        region,
        "bottom_depth_to_sample_indices",
        lambda depths, echo_range: np.array([1.0, np.nan, 3.0]),
    )

    dataset = type("Dataset", (), {"sizes": {"range_sample": 4}})()
    worker = DetectSeafloorWorker(dataset, {"processing": {"bottom_detection": {}}})
    finished = []
    worker.finished.connect(finished.append)

    worker.run()

    assert len(finished) == 1
    result = finished[0]
    assert isinstance(result, BottomDetectionResult)
    assert result.valid_count == 2
    assert result.total_count == 3
