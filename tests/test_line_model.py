import numpy as np
import pytest

from src.core.lines import LineManager


def test_default_zero_and_surface_follow_positive_downward_offset():
    manager = LineManager()

    assert manager.get("zero").name == "Zero"
    assert manager.get("surface").reference_id == "zero"
    np.testing.assert_allclose(
        manager.resolve_for_pings("surface", np.array([1, 2, 3])),
        np.array([2.0, 2.0, 2.0]),
    )


def test_derived_line_follows_its_reference_data():
    manager = LineManager()
    manager.set_line_data("bottom", [20.0, 21.0, 22.0], [10, 20, 30], kind="detected")
    manager.add_line("near_bottom", "Near Bottom", reference_id="bottom", offset_m=-1.5)

    np.testing.assert_allclose(
        manager.resolve_for_pings("near_bottom", np.array([10, 20, 30])),
        np.array([18.5, 19.5, 20.5]),
    )


def test_manual_edit_converts_derived_line_to_independent_line():
    manager = LineManager()
    manager.add_line("custom", "Custom", reference_id="surface", offset_m=3.0)

    manager.set_line_data("custom", [8.0, 9.0], [1, 2], kind="manual")
    manager.set_offset("surface", 10.0)

    assert manager.get("custom").kind == "manual"
    assert manager.get("custom").reference_id is None
    np.testing.assert_allclose(manager.resolve_for_pings("custom", [1, 2]), [8.0, 9.0])


def test_rejects_cycles_and_protected_deletion():
    manager = LineManager()
    manager.add_line("first", "First", reference_id="surface")
    manager.add_line("second", "Second", reference_id="first")

    with pytest.raises(ValueError, match="cycle"):
        manager.set_reference("first", "second")
    with pytest.raises(ValueError, match="referenced"):
        manager.delete_line("first")
    with pytest.raises(ValueError, match="protected"):
        manager.delete_line("surface", protected_ids={"surface"})


def test_reindexes_line_values_by_ping_time_and_excludes_missing_values():
    manager = LineManager()
    manager.set_line_data("bottom", [20.0, 22.0], [10, 30], kind="detected")

    actual = manager.resolve_for_pings("bottom", np.array([10, 20, 30]))

    np.testing.assert_allclose(actual, [20.0, np.nan, 22.0], equal_nan=True)


def test_revision_changes_when_line_definition_or_data_changes():
    manager = LineManager()
    initial = manager.revision

    manager.set_offset("surface", 3.0)
    after_offset = manager.revision
    manager.set_line_data("bottom", [10.0], [1], kind="detected")

    assert after_offset > initial
    assert manager.revision > after_offset
