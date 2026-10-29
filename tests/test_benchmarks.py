from __future__ import annotations

from benchmarks.psx_benchmark import compare, run_suite


def test_core_benchmark_suite_covers_reconciliation_paths_and_compares_results() -> None:
    result = run_suite(size=4, iterations=2, repeats=1)
    scenarios = result["scenarios"]
    assert {item["name"] for item in scenarios} == {
        "mount_unmount",
        "vnode_build_full",
        "vnode_build_single",
        "vnode_build_noop",
        "full_update_combined",
        "full_update_reconcile_only",
        "single_update_combined",
        "single_update_reconcile_only",
        "noop_update_combined",
        "noop_update_reconcile_only",
        "keyed_reorder",
        "keyed_reorder_reconcile_only",
        "event_callback_replacement",
        "event_mount_unmount_cleanup",
        "batched_state_scheduler",
        "markup_render",
        "markup_compile",
        "m4b_transform",
        "component_registry_resolution",
    }
    assert all(
        item["mean_ms"] >= 0
        and item["p95_ms"] >= item["median_ms"]
        and item["peak_python_bytes"] >= 0
        and item["retained_python_bytes"] >= 0
        for item in scenarios
    )
    assert compare(result, result) == [
        {"name": item["name"], "mean_ms_delta_percent": 0.0} for item in scenarios
    ]


def test_grid_resize_benchmark_supports_both_native_adapters_and_cinnamon_engines():
    import inspect
    from benchmarks import grid_resize_profile as profile

    parameters = inspect.signature(profile.measure).parameters
    assert "adapter" in parameters
    assert parameters["adapter"].default == "qt"
    source = inspect.getsource(profile.main)
    assert 'choices=("qt", "tk", "both")' in source
    assert 'choices=("python", "rust", "both")' in source
    assert "p99_wall_ms" in inspect.getsource(profile.measure)
