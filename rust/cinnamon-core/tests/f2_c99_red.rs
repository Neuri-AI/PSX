mod common;
use sfle_core::compute::compute;

#[test]
fn c99_multinode_percentage_cycle_has_specific_diagnostic() {
    let (case,snapshot) = common::fixture("C99");
    let failure=compute(&snapshot).expect_err("C99 must reject an unsupported multi-node cycle");
    assert_eq!(failure.code,case["expected"]["diagnostic"].as_str().unwrap());
    assert_eq!(failure.node_id.as_deref(),case["expected"]["node"].as_str());
    for token in ["multi-node","percentage","cycle"] {
        assert!(failure.message.to_lowercase().contains(token),
            "Diagnostic must identify the unsupported CSS dependency cycle: {token}");
    }
}

#[test]
fn c99_diagnostic_cannot_reject_supported_a01() {
    let (_,snapshot) = common::fixture("A01");
    match compute(&snapshot) {
        Err(failure) => assert_ne!(failure.code,"SFLE_UNSUPPORTED_FEATURE",
            "A01 is supported in approved alpha scope and cannot be rejected as unknown"),
        Ok(_) => (),
    }
}
