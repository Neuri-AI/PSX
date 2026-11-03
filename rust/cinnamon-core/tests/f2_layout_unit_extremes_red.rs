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


#[test]
fn signed_mul_div_cross_engine_boundary_matrix_never_overflows() {
    let raws=[
        I32_MIN_RAW,I32_MIN_RAW+1,-(1_i32<<20),-1,0,1,1_i32<<20,
        I32_MAX_RAW-1,I32_MAX_RAW,
    ];
    for raw in raws {
        for (multiplier,divisor) in [
            (I32_MAX_RAW,1_i32),
            (I32_MAX_RAW,I32_MAX_RAW),
            (-1_i32,1_i32),
            (I32_MIN_RAW,-1_i32),
        ] {
            let numerator=raw as i128*multiplier as i128;
            let expected=(numerator/divisor as i128)
                .clamp(i32::MIN as i128,i32::MAX as i128) as i32;
            let actual=LayoutUnit::from_raw(raw)
                .mul_div(LayoutUnit::from_raw(multiplier),
                         LayoutUnit::from_raw(divisor)).unwrap().raw();
            assert_eq!(actual,expected,
                "raw={raw} multiplier={multiplier} divisor={divisor}");
        }
    }
}

#[test]
fn extremes_are_stable_through_rounding_and_signed_subtraction() {
    for raw in [
        I32_MIN_RAW,I32_MIN_RAW+1,-1,0,1,I32_MAX_RAW-1,I32_MAX_RAW,
    ] {
        let a=LayoutUnit::from_raw(raw);
        let px=a.to_px();
        for from in [
            LayoutUnit::from_trunc(px),LayoutUnit::from_floor(px),
            LayoutUnit::from_ceil(px),LayoutUnit::from_nearest(px),
        ] {
            assert_eq!(from.unwrap().raw(),raw);
        }
        let sub=a-LayoutUnit::from_raw(I32_MAX_RAW);
        let expected=(raw as i128-I32_MAX_RAW as i128)
            .clamp(i32::MIN as i128,i32::MAX as i128) as i32;
        assert_eq!(sub.raw(),expected);
    }
}
