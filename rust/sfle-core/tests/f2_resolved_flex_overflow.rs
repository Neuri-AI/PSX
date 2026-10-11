//! Resolved f64 Flex kernel is not LayoutUnit storage: fail closed on
//! arithmetic overflow before any invalid geometry can be returned.
use sfle_core::{resolve_flexible_lengths,FlexBasis,FlexMathError};

fn fixed()->FlexBasis {
    FlexBasis {basis:1.0,hypothetical:1.0,grow:0.0,shrink:1.0,
               min_size:0.0,max_size:None}
}

#[test]
fn finite_gap_count_overflow_must_fail_closed() {
    let items=vec![fixed();4];
    for gap in [1e308,f64::MAX] {
        assert!(matches!(
            resolve_flexible_lengths(&items,100.0,gap),
            Err(FlexMathError::InvalidInput(_))
        ));
    }
}

#[test]
fn finite_base_sum_overflow_must_fail_closed() {
    let items=vec![
        FlexBasis{basis:1e308,hypothetical:1e308,..fixed()},
        FlexBasis{basis:1e308,hypothetical:1e308,..fixed()},
    ];
    assert!(matches!(
        resolve_flexible_lengths(&items,100.0,0.0),
        Err(FlexMathError::InvalidInput(_))
    ));
}
