# Public behavior certification: reusable execution, exact evidence

F3's final functional gate uses the source-derived census in
`tests/certification/public_behavior_census.py`. This is a certification
mechanism, **not** evidence that the functional gate has passed.

## Semantic partitioning

* `backend=contract`: each declared portable property is checked once for
  its default, representative valid/boundary class and invalid rejection,
  independent of toolkit; each child policy appears once. Shared
  `FLEX_ITEM_PROPS` validation is not multiplied by the Qt binding count.
* Toolkit backends: only admitted G2 native capabilities receive property
  update/readback and live event/lifecycle scenarios. Qt's four bindings
  retain independent runtime evidence even though their test implementation
  can be parametrized.
* Unported nodes receive one explicit negative native-host capability
  scenario per backend. Transparent boundaries and external native ports
  retain their respective lifecycle/ownership contracts.
* Callback properties are validated centrally but are not classified as
  ordinary native property readbacks: they have semantic event scenarios.
* Meaningful property interactions are explicit `INTERACTIONS` rows.
  No all-pairs Cartesian explosion or silent dropping of known coupling.

## Executed assertions, not reference-based certifications

The `assert_feature(request, feature, condition)` helper asserts its
condition before attaching `psx_verified_feature` to the pytest testcase.
The runner emits this marker in JUnit as a testcase property. The collector
only imports marked cases, matching exact component/backend/feature/scenario.
A passing unrelated test, source-reference mention, skipped case or failed
assertion cannot become `executed_pass`.

Run the portable census and export the verified subset:

```bash
python -m pytest -q tests/test_public_behavior_census.py \
  tests/test_public_contract_census.py \
  tests/test_public_property_validation.py \
  --junitxml=public-behavior-core.xml

python -m tests.certification.public_behavior_census \
  --out public-behavior-inventory.json \
  --junit public-behavior-core.xml \
  --sha "$(git rev-parse HEAD)" \
  --environment "local-python"
```

This produces the full pending inventory and a separate receipt JSON with
verified `executed_pass`, `pending`, `failed`, and exclusions. The
GitHub Actions core suite also archives the JUnit and census artifacts.

## Required next steps for the final G5 signoff

1. Complete native behavior drivers across Qt bindings, Kivy, Tkinter and
   Headless, using parametrized tests with feature-specific real assertions
   and exact JUnit properties; add reviewed exclusions where appropriate.
2. Cover meaningful interactions, real events, callback rebinding, focus,
   lifecycle, rollback, resource/DPI invalidation and concurrent commits.
3. Feed all per-platform receipt manifests into the implemented immutable-SHA
   aggregator; require zero pending, failed or unreviewed applicable rows.
   The aggregator reopens the original JUnit testcase properties rather than
   trusting JSON manifests alone. Example after downloading artifacts:

   ```bash
   python -m tests.certification.public_behavior_census \\
     --out public-behavior-final-inventory.json \\
     --sha "$(git rev-parse HEAD)" \\
     --receipt-file artifacts/qt/public-behavior-inventory-receipts.json \\
     --receipt-file artifacts/tk/public-behavior-inventory-receipts.json \\
     --receipt-file artifacts/kivy/public-behavior-inventory-receipts.json \\
     --receipt-file artifacts/headless/public-behavior-inventory-receipts.json \\
     --require-complete
   ```

   Every downloaded receipt manifest must sit next to its original JUnit
   file and refer to the same source revision; a missing, failing or skipped
   feature assertion keeps the final gate RED.
4. Run Chromium comparisons, Rust/Python equivalence, frozen/wheel packaging,
   native integration, Scroll and G4 retirement on **the same immutable SHA**.

Incremental CI remains impact-selective, including zero product suites for
documentation-only changes. An incomplete development census is allowed to
emit a report; **only the formal final gate** may demand
`complete == true`. The report cannot certify a requirement merely
because an older native/lifecycle workflow passed.
