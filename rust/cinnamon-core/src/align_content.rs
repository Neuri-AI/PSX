//! F2.2.3 resolved align-content physical multi-line distribution.

use crate::FlexMathError;
use crate::layout_unit::LayoutUnit;

fn unit(value:f64)->f64 { LayoutUnit::from_nearest(value).expect("validated geometry").to_px() }
fn sum(values:impl IntoIterator<Item=f64>)->f64 { values.into_iter().fold(LayoutUnit::from_raw(0),|a,v|a+LayoutUnit::from_nearest(v).expect("validated geometry")).to_px() }
fn sub(value:f64, values:impl IntoIterator<Item=f64>)->f64 { values.into_iter().fold(LayoutUnit::from_nearest(value).expect("validated geometry"),|a,v|a-LayoutUnit::from_nearest(v).expect("validated geometry")).to_px() }

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum AlignContent {
    FlexStart, FlexEnd, Center, SpaceBetween, SpaceAround, SpaceEvenly, Stretch,
}

#[derive(Clone, Debug, PartialEq)]
pub struct CrossLineDistribution {
    pub starts: Vec<f64>,
    pub sizes: Vec<f64>,
    pub free_space: f64,
}

pub fn distribute_cross_lines(
    mode: AlignContent,
    container_cross_size: f64,
    line_sizes: &[f64],
    gap: f64,
    forward: bool,
    nowrap: bool,
) -> Result<CrossLineDistribution, FlexMathError> {
    if !container_cross_size.is_finite() || container_cross_size < 0.0
        || !gap.is_finite() || gap < 0.0
        || line_sizes.iter().any(|n| !n.is_finite() || *n < 0.0)
        || (nowrap && line_sizes.len() > 1)
    {
        return Err(FlexMathError::InvalidInput("invalid resolved cross-line input"));
    }
    let extent=unit(container_cross_size);
    let gap=unit(gap);
    let count = line_sizes.len();
    if count == 0 {
        return Ok(CrossLineDistribution {
            starts: vec![], sizes: vec![], free_space: extent,
        });
    }
    let mut sizes = if nowrap { vec![extent] }
                    else { line_sizes.iter().map(|v|unit(*v)).collect() };
    let free = sub(extent, sizes.iter().copied().chain(std::iter::repeat(gap).take(count.saturating_sub(1))));
    let mut leading = 0.0;
    let mut between = gap;
    if !nowrap {
        match mode {
            AlignContent::FlexEnd => leading = free,
            AlignContent::Center => leading = free / 2.0,
            AlignContent::SpaceBetween if count > 1 => between = sum([between, free.max(0.0) / (count - 1) as f64]),
            AlignContent::SpaceAround if free > 0.0 => {
                between = sum([between, free / count as f64]);
                leading = free / (2 * count) as f64;
            }
            AlignContent::SpaceEvenly if free > 0.0 => {
                between = sum([between, free / (count + 1) as f64]);
                leading = LayoutUnit::from_floor(free / (count + 1) as f64)
                    .expect("validated fractional leading offset").to_px();
            }
            AlignContent::Stretch if free > 0.0 => {
                for size in &mut sizes { *size = sum([*size, free / count as f64]); }
            }
            _ => {}
        }
    }
    let mut cursor = unit(if forward { leading } else { sub(extent, [leading]) });
    let mut starts = Vec::with_capacity(count);
    for size in &sizes {
        if forward {
            starts.push(cursor);
            cursor = sum([cursor, *size, between]);
        } else {
            cursor = sub(cursor, [*size]);
            starts.push(cursor);
            cursor = sub(cursor, [between]);
        }
    }
    Ok(CrossLineDistribution { starts, sizes, free_space: free })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn between_includes_fixed_gap() {
        let v = distribute_cross_lines(AlignContent::SpaceBetween, 100.0, &[20.0, 20.0], 10.0, true, false).unwrap();
        assert_eq!(v.starts, vec![0.0, 80.0]);
    }

    #[test]
    fn stretch_expands_lines_not_boxes() {
        let v = distribute_cross_lines(AlignContent::Stretch, 100.0, &[20.0, 20.0], 10.0, true, false).unwrap();
        assert_eq!(v.sizes, vec![45.0, 45.0]);
        assert_eq!(v.starts, vec![0.0, 55.0]);
    }

    #[test]
    fn chromium_153_fractional_space_evenly_uses_floored_leading_and_rounded_gap() {
        let v = distribute_cross_lines(
            AlignContent::SpaceEvenly, 100.0, &[20.0, 20.0], 10.0, true, false
        ).unwrap();
        assert_eq!(v.starts, vec![16.65625, 63.328125]);
        assert_eq!(v.free_space, 50.0);
    }

    #[test]
    fn reverse_and_overflow_keep_signed_origin() {
        let v = distribute_cross_lines(AlignContent::Center, 30.0, &[20.0, 20.0], 10.0, false, false).unwrap();
        assert_eq!(v.starts, vec![20.0, -10.0]);
    }
}
