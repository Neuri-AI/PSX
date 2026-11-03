mod common;
use sfle_core::compute::compute;

#[test]
fn n04_unmeasured_indefinite_block_percent_is_unsupported() {
    let (case,snapshot)=common::fixture("N04");
    let result=compute(&snapshot).expect_err("N04 indefinite percentage may not resolve to zero");
    assert_eq!(result.code,"SFLE_UNSUPPORTED_FEATURE");
    assert_eq!(result.node_id.as_deref(),case["expected"]["node"].as_str());
    for token in ["unmeasured","indefinite","percentage","cycle"] {
        assert!(result.message.to_lowercase().contains(token),
            "Missing rejection class {token}: {}",result.message);
    }
}
