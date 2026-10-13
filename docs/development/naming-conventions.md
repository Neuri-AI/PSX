# Source naming conventions

This is a **mandatory development and CI convention** for PSX.

## Name behavior, not delivery milestones

A developer must know what an artifact does from its name, without first
consulting a planning document. Use semantic filenames, Python module paths,
functions, classes, constants, fixtures, test names and CI workflow/job names.
Phase labels `F1`, `F2`, `F3`, gate labels `G1`, `G2`, `G3`
and increment labels `C1`–`C6` are for roadmap prose, historical audits
and release metadata **only**. Never use them as executable identifiers.

| Avoid | Use |
| --- | --- |
| `psx/sfle/f3_native_cache.py` | `psx/sfle/native_intrinsic_cache.py` |
| `psx/sfle/f3_native_coverage.py` | `psx/sfle/native_component_capabilities.py` |
| `g2_native_leaf_needs_measurement(...)` | `native_leaf_needs_measurement(...)` |
| `tests/test_f3_g2_c6_precision.py` | `tests/test_native_geometry_precision.py` |
| A C5-named certifier | A certifier named for the native operation or resource behavior it validates |
| A G1-named CI workflow | A Flex-layout contract workflow |

## Rules

1. **Modules and packages:** choose the responsibility, domain and platform
   (`qt_layout_bridge`, `native_resource_watch`, `native_operation_receipts`);
   do not encode the sprint/phase/gate that introduced them.
2. **Functions and methods:** prefer action or predicate verbs
   (`native_leaf_needs_measurement`, `measure_width_dependent_content`).
3. **Classes/constants:** describe their actual contract. Preserve genuinely
   public compatibility/API identifiers unless explicitly approved as a
   breaking change.
4. **Tests:** name the behavior, condition, and backend; use distinct
   behavior-specific executed assertions. Existing N/A and unsupported
   cases remain explicit and are never counted as passing native support.
5. **CI:** workflow filenames, job names, script paths, JSON receipt names,
   and references in selectors must be intelligible without a roadmap.
6. **Diagnostics:** user-facing exceptions describe the unsupported
   operation/backend. Planning codes must not be used as explanations.
   Preserve stable published machine-readable diagnostic codes.
7. **Documentation:** planning milestones remain valid as dated historical
   references. Update current code examples, source links and invocations
   after any rename. Do not rewrite historical acceptance outcomes.
8. **Migration safety:** perform atomic reference updates across imports,
   renderers, tests, scripts, workflows, packaging and documentation.
   Remove old shim paths only when all consumers have migrated.
   Re-run the full required G2/native/Chromium/Rust/fallback certification
   on one immutable source SHA; doc-only follow-ups never re-run product tests.

A proposed component (such as a future `Modal`) must also declare its
functional family, child policy, platform ownership and dedicated native
acceptance tests. The family is a *semantic contract*, not a roadmap gate.

See [SFLE F3 implementation plan](../architecture/sfle-f3-implementation.md)
for historical phase acceptance and the [PSX roadmap](../roadmap.md).
