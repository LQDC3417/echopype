# Real-data Test Boundaries Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep normal regression deterministic and fast while retaining opt-in, bounded validation against the local EK80 raw file.

**Architecture:** Pytest owns the execution boundary through a `real_data` marker and a `--run-real-data` switch. Real-data school-detection assertions use a fixed slice of the loaded dataset and a wall-clock budget, so they exercise the real algorithm without silently consuming an unbounded runtime. The visual template is an untracked reference artifact, so its tests skip instead of failing when the artifact is absent.

**Tech Stack:** Python 3.13, pytest 8, xarray, echopype, PySide6.

---

### Task 1: Make the untracked visual template test optional

**Files:**
- Modify: `tests/test_gui_template.py:1-15`

- [ ] **Step 1: Reproduce the clean-checkout failure**

Run: `python -m pytest tests/test_gui_template.py -q`

Expected: collection fails with `ModuleNotFoundError: No module named 'templates'` when `templates/echoview_gui_template.py` is absent.

- [ ] **Step 2: Guard the optional reference artifact**

Replace the unconditional template import with:

```python
from pathlib import Path

import pytest

_TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "templates" / "echoview_gui_template.py"
if _TEMPLATE_PATH.is_file():
    from templates.echoview_gui_template import EchoviewTemplateWindow
else:
    EchoviewTemplateWindow = None
```

At the start of the template-specific test, skip only that test when `EchoviewTemplateWindow is None`.

- [ ] **Step 3: Verify the guard**

Run: `python -m pytest tests/test_gui_template.py -q`

Expected: the template-only assertion is skipped, the remaining GUI tests still run, and there is no collection error.

### Task 2: Define the real-data test switch with a failing unit test

**Files:**
- Create: `tests/test_real_data_test_control.py`
- Modify: `tests/conftest.py:1-10`
- Modify: `pyproject.toml:24-25`

- [ ] **Step 1: Write the failing hook tests**

Create `tests/test_real_data_test_control.py` with fake pytest parser/config/item objects that assert:

```python
def test_adds_run_real_data_option():
    parser = _Parser()
    conftest.pytest_addoption(parser)
    assert parser.group.options == [
        (("--run-real-data",), {"action": "store_true", "default": False}),
    ]


def test_skips_marked_items_without_run_real_data():
    item = _Item(real_data=True)
    conftest.pytest_collection_modifyitems(_Config(False), [item])
    assert [marker.name for marker in item.markers] == ["skip"]


def test_leaves_marked_items_enabled_with_run_real_data():
    item = _Item(real_data=True)
    conftest.pytest_collection_modifyitems(_Config(True), [item])
    assert item.markers == []
```

- [ ] **Step 2: Verify the tests fail for the missing hooks**

Run: `python -m pytest tests/test_real_data_test_control.py -q`

Expected: `AttributeError` because `pytest_addoption` and `pytest_collection_modifyitems` do not exist yet.

- [ ] **Step 3: Implement the minimal pytest hooks**

Add to `tests/conftest.py`:

```python
def pytest_addoption(parser):
    group = parser.getgroup("real-data")
    group.addoption("--run-real-data", action="store_true", default=False)


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-real-data"):
        return

    skip_real_data = pytest.mark.skip(
        reason="requires local raw data; rerun with --run-real-data"
    )
    for item in items:
        if item.get_closest_marker("real_data"):
            item.add_marker(skip_real_data)
```

Add this marker declaration under `[tool.pytest.ini_options]` in `pyproject.toml`:

```toml
markers = [
    "real_data: requires local EK80 raw data and --run-real-data",
]
```

- [ ] **Step 4: Verify the hook tests pass**

Run: `python -m pytest tests/test_real_data_test_control.py -q`

Expected: `3 passed`.

### Task 3: Bound real-data fish-school detection tests

**Files:**
- Modify: `tests/conftest.py`
- Modify: `tests/test_real_data_test_control.py`
- Modify: `tests/test_e2e_prd.py`
- Modify: `tests/test_gui_integration.py`
- Modify: `tests/test_grid_overlay.py`

- [ ] **Step 1: Add a failing slice contract test**

Extend `tests/test_real_data_test_control.py` with an xarray dataset of shape `(80, 5000)` and this assertion:

```python
subset = subset_for_school_detection(dataset)
assert subset.sizes == {"ping_time": 64, "range_sample": 4096}
```

- [ ] **Step 2: Verify it fails because the helper is missing**

Run: `python -m pytest tests/test_real_data_test_control.py -q`

Expected: `AttributeError` because `subset_for_school_detection` does not exist in `conftest` yet.

- [ ] **Step 3: Implement the bounded dataset helper**

Add this shared helper to `tests/conftest.py`:

```python
SCHOOL_TEST_MAX_PINGS = 64
SCHOOL_TEST_MAX_SAMPLES = 4096
SCHOOL_TEST_MAX_SECONDS = 30.0


def subset_for_school_detection(ds_sv):
    return ds_sv.isel(
        ping_time=slice(0, SCHOOL_TEST_MAX_PINGS),
        range_sample=slice(0, SCHOOL_TEST_MAX_SAMPLES),
    )
```

- [ ] **Step 4: Apply marker and budget to each real-data module**

After `import pytest`, add:

```python
pytestmark = pytest.mark.real_data
```

in `tests/test_e2e_prd.py` and `tests/test_gui_integration.py`. Add `import pytest` and the same marker to `tests/test_grid_overlay.py`.

In the E2E school test and GUI-integration school fixture, call `subset_for_school_detection(...)` before `detect_schools(...)`, time the call with `time.perf_counter()`, and assert the elapsed time is no greater than `SCHOOL_TEST_MAX_SECONDS`. When converting the GUI mask to a DataFrame, pass the same sliced dataset to `schools_to_dataframe`.

- [ ] **Step 5: Verify ordinary and opt-in behavior**

Run:

```powershell
python -m pytest -q
python -m pytest tests/test_e2e_prd.py::TestFR05_SchoolDetection::test_detect_schools_returns_mask --run-real-data -q
python -m pytest tests/test_gui_integration.py::test_school_detection --run-real-data -q
```

Expected: ordinary regression skips real-data modules; each opt-in school test passes within the 30-second budget.

### Task 4: Verify and commit the isolated change

**Files:**
- Modify: files from Tasks 1-3 only

- [ ] **Step 1: Run full static and regression verification**

Run:

```powershell
python -m ruff check src tests
python -m compileall -q src tests
python -m pytest -q
git diff --check
```

Expected: lint and compilation succeed, the default suite has no failures, and `git diff --check` has no output.

- [ ] **Step 2: Review the staged scope**

Run:

```powershell
git diff -- tests/conftest.py pyproject.toml tests/test_gui_template.py tests/test_real_data_test_control.py tests/real_data_helpers.py tests/test_e2e_prd.py tests/test_gui_integration.py tests/test_grid_overlay.py
git status --short
```

Expected: only the listed test infrastructure and configuration files are staged.

- [ ] **Step 3: Create the local commit**

Run:

```powershell
git add pyproject.toml tests/conftest.py tests/test_real_data_test_control.py tests/test_gui_template.py tests/test_e2e_prd.py tests/test_gui_integration.py tests/test_grid_overlay.py docs/superpowers/plans/2026-08-29-real-data-test-boundaries.md
git commit -m "test: isolate real data acceptance"
```

Expected: one local commit on `codex/real-data-test-boundaries`, with no push.
