"""Pure, dependency-free regression tests for the mixed native resize probe."""
from benchmarks.kivy_qt_mixed_resize import percentile, compare, KINDS


def test_nearest_rank_percentiles_cover_all_samples():
    data = list(range(1, 101))
    assert percentile(data, 50) == 50
    assert percentile(data, 95) == 95
    assert percentile(data, 99) == 99


def test_fixture_has_ten_distinct_native_leaf_types():
    assert len(KINDS) == 10
    assert len(set(KINDS)) == 10


def test_geometry_comparison_ignores_process_specific_ids():
    base = {"backend": "qt", "engine": "python", "rectangles": {
        480: {"id-11": [0, 0, 100, 50], "id-12": [100, 0, 80, 50]}}}
    kivy = {"backend": "kivy", "engine": "rust", "rectangles": {
        480: {"id-999": [100, 0, 80, 50], "id-888": [0, 0, 100, 50]}}}
    assert compare([base, kivy], 1)["passed"]
    kivy["rectangles"][480]["id-999"][2] = 83
    assert not compare([base, kivy], 1)["passed"]
