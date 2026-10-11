//! D-F1.13 signed saturating Blink LayoutUnit primitive at 1/64 CSS px.
//! Chromium tag 153.0.8010.12: geometry/layout_unit.h FixedPoint<6,int32_t>.
//! Caller chooses conversion rounding; prequantization factors remain f64.
use std::ops::{Add, Sub};

pub const SCALE: i32 = 64;
pub const I32_MAX_RAW: i32 = i32::MAX;
pub const I32_MIN_RAW: i32 = i32::MIN;

#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub struct LayoutUnit(i32);

fn saturate(n: i128) -> i32 {
    n.clamp(i32::MIN as i128, i32::MAX as i128) as i32
}

fn scaled(value: f64, mode: u8) -> Result<i32, &'static str> {
    if !value.is_finite() {
        return Err("LayoutUnit rejects NaN and infinity.");
    }
    let raw = value * SCALE as f64;
    if raw >= i32::MAX as f64 + 1.0 { return Ok(i32::MAX); }
    if raw <= i32::MIN as f64 - 1.0 { return Ok(i32::MIN); }
    let result = match mode {
        0 => raw.trunc(),
        1 => raw.floor(),
        2 => raw.ceil(),
        3 => raw.round(),
        _ => return Err("Unsupported LayoutUnit rounding mode."),
    };
    Ok(saturate(result as i128))
}

impl LayoutUnit {
    pub fn from_raw(value: i32) -> Self { Self(value) }
    pub fn from_trunc(value: f64) -> Result<Self, &'static str> { Ok(Self(scaled(value,0)?)) }
    pub fn from_floor(value: f64) -> Result<Self, &'static str> { Ok(Self(scaled(value,1)?)) }
    pub fn from_ceil(value: f64) -> Result<Self, &'static str> { Ok(Self(scaled(value,2)?)) }
    pub fn from_nearest(value: f64) -> Result<Self, &'static str> { Ok(Self(scaled(value,3)?)) }
    pub fn raw(self) -> i32 { self.0 }
    pub fn to_px(self) -> f64 { self.0 as f64 / SCALE as f64 }
    pub fn saturating_add(self, rhs: Self) -> Self {
        Self(saturate(self.0 as i128 + rhs.0 as i128))
    }
    pub fn saturating_sub(self, rhs: Self) -> Self {
        Self(saturate(self.0 as i128 - rhs.0 as i128))
    }
    pub fn mul_div(self, multiplier: Self, divisor: Self) -> Result<Self, &'static str> {
        if divisor.0 == 0 { return Err("LayoutUnit MulDiv divisor cannot be zero."); }
        let n = self.0 as i128 * multiplier.0 as i128;
        Ok(Self(saturate(n / divisor.0 as i128)))
    }
}

impl Add for LayoutUnit {
    type Output = Self;
    fn add(self, rhs: Self) -> Self { self.saturating_add(rhs) }
}
impl Sub for LayoutUnit {
    type Output = Self;
    fn sub(self, rhs: Self) -> Self { self.saturating_sub(rhs) }
}
