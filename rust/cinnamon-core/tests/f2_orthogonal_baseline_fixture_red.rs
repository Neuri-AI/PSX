mod common;

#[test]
fn shared_corpus_fixture_has_explicit_absent_orthogonal_baseline() {
    let (_case, snapshot) = common::fixture("A01");
    assert_eq!(snapshot.measurements.len(), 1);
    assert!(snapshot.measurements.iter().all(|measurement|
        measurement.intrinsic.orthogonal_baseline.is_none()
    ));
}
