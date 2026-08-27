import numpy as np
import pytest

from src.core.region import AnalysisRegion, build_line_region_mask


def test_line_region_keeps_only_samples_between_per_ping_boundaries():
    mask, excluded = build_line_region_mask(
        np.array([0.0, 1.0, 2.0, 3.0, 4.0]),
        upper_depth_m=np.array([1.0, 2.0]),
        lower_depth_m=np.array([3.0, 4.0]),
    )

    assert excluded == 0
    np.testing.assert_array_equal(mask[0], [False, True, True, True, False])
    np.testing.assert_array_equal(mask[1], [False, False, True, True, True])


def test_line_region_excludes_entire_ping_when_boundaries_are_invalid():
    mask, excluded = build_line_region_mask(
        np.array([0.0, 1.0, 2.0, 3.0, 4.0]),
        upper_depth_m=np.array([1.0, np.nan, 4.0, -1.0]),
        lower_depth_m=np.array([3.0, 4.0, 2.0, 3.0]),
    )

    assert excluded == 3
    assert mask[0].sum() == 3
    assert not mask[1:].any()


def test_analysis_region_requires_different_existing_boundaries():
    region = AnalysisRegion("surface", "bottom")
    region.validate({"surface", "bottom"})

    with pytest.raises(ValueError, match="different"):
        AnalysisRegion("surface", "surface").validate({"surface"})
    with pytest.raises(ValueError, match="missing"):
        region.validate({"surface"})
