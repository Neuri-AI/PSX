//! RED D-F1.13: reproduce Chromium 153 FixedPoint<6,int32_t> arithmetic.
use sfle_core::layout_unit::{LayoutUnit, I32_MAX_RAW, I32_MIN_RAW};

#[test]
fn conversion_modes_and_signed_half_ties() {
    for (x,t,f,c,n) in [
        (0.0,0,0,0,0),
        (1.0/128.0,0,0,1,1),
        (-1.0/128.0,0,-1,0,-1),
        (3.0/128.0,1,1,2,2),
        (-3.0/128.0,-1,-2,-1,-2),
        (13.0/64.0,13,13,13,13),
        (-13.0/64.0,-13,-13,-13,-13),
    ] {
        assert_eq!(LayoutUnit::from_trunc(x).unwrap().raw(),t);
        assert_eq!(LayoutUnit::from_floor(x).unwrap().raw(),f);
        assert_eq!(LayoutUnit::from_ceil(x).unwrap().raw(),c);
        assert_eq!(LayoutUnit::from_nearest(x).unwrap().raw(),n);
    }
}

#[test]
fn saturating_extremes_and_intermediate_widening() {
    assert_eq!((LayoutUnit::from_raw(I32_MAX_RAW)+LayoutUnit::from_raw(1)).raw(),I32_MAX_RAW);
    assert_eq!((LayoutUnit::from_raw(I32_MIN_RAW)+LayoutUnit::from_raw(-1)).raw(),I32_MIN_RAW);
    assert_eq!(LayoutUnit::from_trunc(1e20).unwrap().raw(),I32_MAX_RAW);
    assert_eq!(LayoutUnit::from_trunc(-1e20).unwrap().raw(),I32_MIN_RAW);
    assert_eq!(LayoutUnit::from_raw(80).mul_div(LayoutUnit::from_raw(I32_MAX_RAW),
               LayoutUnit::from_raw(160)).unwrap().raw(),1073741823);
    assert!(LayoutUnit::from_nearest(f64::NAN).is_err());
    assert!(LayoutUnit::from_floor(f64::INFINITY).is_err());
}
