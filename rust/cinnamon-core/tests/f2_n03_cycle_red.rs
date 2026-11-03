mod common;
use sfle_core::compute::compute;

#[test]
fn acceptance_n03_unlisted_cycle_rejected_with_identity() {
    let (case,snapshot)=common::fixture("N03");
    let error=compute(&snapshot).expect_err("N03 must reject unsupported percentage dependency");
    assert_eq!(error.code,"SFLE_UNSUPPORTED_FEATURE");
    assert_eq!(error.node_id.as_deref(),case["expected"]["node"].as_str());
    let description=case["expected"]["cycle_kind"].as_str().unwrap();
    for word in description.split_whitespace(){
        assert!(error.message.to_lowercase().contains(&word.to_lowercase()),
            "Diagnostic must identify {word}: {}",error.message);
    }
}
