//! Deterministic twelve-column Grid row packing. No pixel geometry or toolkit.
//! Mirrors the Python `psx.sfle.grid_math` parity fallback.
use std::collections::HashSet;

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct GridSlot {
    pub id: String,
    /// None means distributive auto; Some(1..=12) means an explicit span.
    pub span: Option<u8>,
    pub offset: u8,
    pub order: i32,
}

#[derive(Clone, Debug, PartialEq)]
pub struct PackedGridItem {
    pub id: String,
    pub start: f64,
    pub span: f64,
}

#[derive(Clone, Debug, PartialEq)]
pub struct PackedGridRow {
    pub items: Vec<PackedGridItem>,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum GridPackingError {
    InvalidInput(&'static str),
}

fn validate(items: &[GridSlot]) -> Result<(), GridPackingError> {
    let mut ids = HashSet::new();
    for item in items {
        if item.id.is_empty() || !ids.insert(item.id.as_str()) {
            return Err(GridPackingError::InvalidInput("Grid IDs must be nonempty and unique"));
        }
        if item.span.is_some_and(|span| !(1..=12).contains(&span)) {
            return Err(GridPackingError::InvalidInput("Grid span must be between 1 and 12"));
        }
        if item.offset > 11 {
            return Err(GridPackingError::InvalidInput("Grid offset must be between 0 and 11"));
        }
        if item.span.is_some_and(|span| span as u16 + item.offset as u16 > 12) {
            return Err(GridPackingError::InvalidInput("Grid span + offset exceeds 12"));
        }
    }
    Ok(())
}

fn finalize(items: &[GridSlot]) -> Result<PackedGridRow, GridPackingError> {
    let used: u32 = items.iter().map(|item|
        item.offset as u32 + item.span.unwrap_or(0) as u32).sum();
    let autos = items.iter().filter(|item| item.span.is_none()).count();
    if used > 12 || (autos > 0 && used >= 12) {
        return Err(GridPackingError::InvalidInput("Grid row has no auto capacity"));
    }
    let share = if autos > 0 { (12 - used) as f64 / autos as f64 } else { 0.0 };
    let mut cursor = 0.0;
    let mut result = Vec::with_capacity(items.len());
    for item in items {
        cursor += item.offset as f64;
        let span = item.span.map_or(share, f64::from);
        result.push(PackedGridItem { id: item.id.clone(), start: cursor, span });
        cursor += span;
    }
    Ok(PackedGridRow { items: result })
}

/// Stable order sorting, logical offsets, distributive auto and monotonic rows.
/// A pending auto item must retain strictly positive width before the next
/// explicit item may join its row. Closed rows never accept later items.
pub fn pack_grid_rows(items: &[GridSlot]) -> Result<Vec<PackedGridRow>, GridPackingError> {
    validate(items)?;
    let mut sorted: Vec<&GridSlot> = items.iter().collect();
    sorted.sort_by_key(|item| item.order); // stable equal-order identity
    let mut rows = Vec::new();
    let mut current: Vec<GridSlot> = Vec::new();
    let mut explicit_used: u32 = 0;
    let mut autos: u32 = 0;
    for item in sorted {
        let reservation = item.offset as u32 + item.span.unwrap_or(0) as u32;
        let exhausts_autos = (autos > 0 || item.span.is_none()) &&
            explicit_used + reservation >= 12;
        if !current.is_empty() &&
            (explicit_used + reservation > 12 || exhausts_autos) {
            rows.push(finalize(&current)?);
            current.clear();
            explicit_used = 0;
            autos = 0;
        }
        current.push(item.clone());
        explicit_used += reservation;
        autos += u32::from(item.span.is_none());
    }
    if !current.is_empty() { rows.push(finalize(&current)?); }
    Ok(rows)
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::Value;

    #[test]
    fn canonical_row_packing_fixtures() {
        let cases: Value = serde_json::from_str(include_str!(
            "../../../tests/fixtures/grid_row_packing.json"
        )).unwrap();
        assert_eq!(cases["schema_version"], 1);
        for case in cases["cases"].as_array().unwrap() {
            let name = case["name"].as_str().unwrap();
            let items: Vec<GridSlot> = case["items"].as_array().unwrap().iter().map(|item| {
                GridSlot {
                    id: item["id"].as_str().unwrap().to_owned(),
                    span: if item["span"].is_null() || item["span"] == "auto" {
                        None
                    } else { Some(item["span"].as_u64().unwrap() as u8) },
                    offset: item["offset"].as_u64().unwrap_or(0) as u8,
                    order: item["order"].as_i64().unwrap_or(0) as i32,
                }
            }).collect();
            let outcome = pack_grid_rows(&items);
            if case["error"] == "invalid" {
                assert!(outcome.is_err(), "{name}: expected rejection");
                continue;
            }
            let result = outcome.unwrap_or_else(|e| panic!("{name}: {e:?}"));
            let expected = case["rows"].as_array().unwrap();
            assert_eq!(result.len(), expected.len(), "{name}: row count");
            for (row, expected_row) in result.iter().zip(expected) {
                let entries = expected_row.as_array().unwrap();
                assert_eq!(row.items.len(), entries.len(), "{name}: item count");
                for (actual, reference) in row.items.iter().zip(entries) {
                    assert_eq!(actual.id, reference["id"].as_str().unwrap(), "{name}: identity");
                    assert!((actual.start - reference["start"].as_f64().unwrap()).abs() < 1e-10,
                        "{name}: start for {}", actual.id);
                    assert!((actual.span - reference["span"].as_f64().unwrap()).abs() < 1e-10,
                        "{name}: span for {}", actual.id);
                }
            }
        }
    }

    #[test]
    fn rejects_invalid_native_types_and_overflow() {
        let invalid = GridSlot { id: "x".into(), span: Some(0), offset: 0, order: 0 };
        assert!(pack_grid_rows(&[invalid]).is_err());
        let invalid = GridSlot { id: "x".into(), span: Some(12), offset: 1, order: 0 };
        assert!(pack_grid_rows(&[invalid]).is_err());
        let invalid = GridSlot { id: "x".into(), span: None, offset: 12, order: 0 };
        assert!(pack_grid_rows(&[invalid]).is_err());
    }
}


#[derive(Clone, Debug, PartialEq, Eq)]
pub struct GridPixelItem {
    pub id: String,
    /// Horizontal origin in signed 1/64px units.
    pub x_raw: i32,
    pub width_raw: i32,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct GridPixelRow { pub items: Vec<GridPixelItem> }

/// Deterministically project twelve-column units to physical LTR edges.
/// One gutter is inserted per adjacent pair of actual widgets. A logical
/// empty offset does not acquire an extra gap.
pub fn project_grid_rows(
    rows: &[PackedGridRow],
    content_width: f64,
    column_gap: f64,
) -> Result<Vec<GridPixelRow>, GridPackingError> {
    use crate::layout_unit::LayoutUnit;
    if !content_width.is_finite() || content_width < 0.0 ||
        !column_gap.is_finite() || column_gap < 0.0 {
        return Err(GridPackingError::InvalidInput("Invalid Grid content width or gap"));
    }
    if content_width * 64.0 > i32::MAX as f64 ||
        column_gap * 64.0 > i32::MAX as f64 {
        return Err(GridPackingError::InvalidInput("Grid width or gap exceeds LayoutUnit range"));
    }
    let width = LayoutUnit::from_nearest(content_width)
        .map_err(|_| GridPackingError::InvalidInput("Invalid Grid width"))?.raw() as i64;
    let gap = LayoutUnit::from_nearest(column_gap)
        .map_err(|_| GridPackingError::InvalidInput("Invalid Grid gap"))?.raw() as i64;
    let mut result = Vec::with_capacity(rows.len());
    for row in rows {
        let count = row.items.len();
        if count == 0 {
            result.push(GridPixelRow { items: vec![] });
            continue;
        }
        let gaps = (count as i64 - 1) * gap;
        if gaps > width {
            return Err(GridPackingError::InvalidInput("Grid gaps exceed content width"));
        }
        let usable = width - gaps;
        let mut boxes = Vec::with_capacity(count);
        let mut previous_end = 0_i64;
        for (index, item) in row.items.iter().enumerate() {
            if !item.start.is_finite() || !item.span.is_finite() ||
                item.start < 0.0 || item.span <= 0.0 ||
                item.start + item.span > 12.0 + 1e-9 {
                return Err(GridPackingError::InvalidInput("Grid logical extent outside row"));
            }
            // Quantize logical values at one-billionth of a column before
            // projecting, mirroring the Python implementation's shared origin.
            let first = (item.start * 1_000_000_000.0).round() as i128;
            let last = ((item.start + item.span) * 1_000_000_000.0).round() as i128;
            let denom = 12_000_000_000_i128;
            let start = ((2 * first * usable as i128 + denom) / (2 * denom)) as i64;
            let end = ((2 * last * usable as i128 + denom) / (2 * denom)) as i64;
            let x = start + index as i64 * gap;
            let right = end + index as i64 * gap;
            if x < previous_end || right < x || x > i32::MAX as i64 ||
               right > i32::MAX as i64 {
                return Err(GridPackingError::InvalidInput("Grid projected edges invalid"));
            }
            boxes.push(GridPixelItem {
                id: item.id.clone(), x_raw: x as i32,
                width_raw: (right - x) as i32,
            });
            previous_end = right;
        }
        result.push(GridPixelRow { items: boxes });
    }
    Ok(result)
}

#[cfg(test)]
mod pixel_projection_tests {
    use super::*;
    use serde_json::Value;

    #[test]
    fn shared_pixel_edge_fixtures() {
        let fixtures: Value = serde_json::from_str(include_str!(
            "../../../tests/fixtures/grid_pixel_projection.json"
        )).unwrap();
        assert_eq!(fixtures["schema_version"], 1);
        for fixture in fixtures["cases"].as_array().unwrap() {
            let name = fixture["name"].as_str().unwrap();
            let slots: Vec<GridSlot> = fixture["items"].as_array().unwrap().iter().map(|item| {
                GridSlot {
                    id: item["id"].as_str().unwrap().to_string(),
                    span: if item["span"] == "auto" || item["span"].is_null() {
                        None
                    } else { Some(item["span"].as_u64().unwrap() as u8) },
                    offset: item["offset"].as_u64().unwrap_or(0) as u8,
                    order: item["order"].as_i64().unwrap_or(0) as i32,
                }
            }).collect();
            let rows = pack_grid_rows(&slots).unwrap();
            let outcome = project_grid_rows(
                &rows,
                fixture["width"].as_f64().unwrap(),
                fixture["gap"].as_f64().unwrap(),
            );
            if fixture["error"] == "invalid" {
                assert!(outcome.is_err(), "{name} should reject impossible gutters");
                continue;
            }
            let computed = outcome.unwrap_or_else(|err| panic!("{name}: {err:?}"));
            let expected = fixture["rows"].as_array().unwrap();
            assert_eq!(computed.len(), expected.len(), "{name}");
            for (row, targets) in computed.iter().zip(expected) {
                for (box_, target) in row.items.iter().zip(targets.as_array().unwrap()) {
                    assert_eq!(box_.id, target["id"].as_str().unwrap(), "{name}");
                    assert_eq!(box_.x_raw, target["x_raw"].as_i64().unwrap() as i32, "{name}");
                    assert_eq!(box_.width_raw, target["width_raw"].as_i64().unwrap() as i32, "{name}");
                }
            }
        }
    }
}


#[derive(Clone, Debug, PartialEq, Eq)]
pub struct GridRect {
    pub id: String,
    pub x_raw: i32,
    pub y_raw: i32,
    pub width_raw: i32,
    pub height_raw: i32,
}

/// Projects LTR/RTL horizontal coordinates and top-aligned rows.
/// All heights must be explicitly supplied; intrinsic sizing is a later gate.
pub fn layout_grid_rects(
    rows: &[PackedGridRow],
    content_width: f64,
    column_gap: f64,
    row_gap: f64,
    item_heights: &std::collections::HashMap<String, f64>,
    rtl: bool,
) -> Result<Vec<Vec<GridRect>>, GridPackingError> {
    use crate::layout_unit::LayoutUnit;
    if !row_gap.is_finite() || row_gap < 0.0 {
        return Err(GridPackingError::InvalidInput("Invalid row gap"));
    }
    if row_gap * 64.0 > i32::MAX as f64 {
        return Err(GridPackingError::InvalidInput("Grid row gap exceeds LayoutUnit range"));
    }
    let projected = project_grid_rows(rows, content_width, column_gap)?;
    let width = LayoutUnit::from_nearest(content_width)
        .map_err(|_| GridPackingError::InvalidInput("Invalid Grid width"))?.raw() as i64;
    let gap = LayoutUnit::from_nearest(row_gap)
        .map_err(|_| GridPackingError::InvalidInput("Invalid Grid row gap"))?.raw() as i64;
    let mut heights = std::collections::HashMap::new();
    for row in &projected {
        for item in &row.items {
            let height = item_heights.get(&item.id)
                .ok_or(GridPackingError::InvalidInput("Missing Grid item height"))?;
            if !height.is_finite() || *height < 0.0 {
                return Err(GridPackingError::InvalidInput("Invalid Grid item height"));
            }
            if *height * 64.0 > i32::MAX as f64 {
                return Err(GridPackingError::InvalidInput("Grid height exceeds LayoutUnit range"));
            }
            heights.insert(item.id.clone(), LayoutUnit::from_nearest(*height)
                .map_err(|_| GridPackingError::InvalidInput("Invalid Grid item height"))?
                .raw() as i64);
        }
    }
    let mut y = 0_i64;
    let mut result = Vec::with_capacity(projected.len());
    for row in projected {
        let mut rects = Vec::with_capacity(row.items.len());
        let mut row_height = 0_i64;
        for item in row.items {
            let height = heights[&item.id];
            row_height = row_height.max(height);
            let x = if rtl { width - item.x_raw as i64 - item.width_raw as i64 }
                    else { item.x_raw as i64 };
            if x < i32::MIN as i64 || x > i32::MAX as i64 ||
                y > i32::MAX as i64 || height > i32::MAX as i64 ||
                y + height > i32::MAX as i64 {
                return Err(GridPackingError::InvalidInput("Grid rectangle overflow"));
            }
            rects.push(GridRect {
                id: item.id, x_raw: x as i32, y_raw: y as i32,
                width_raw: item.width_raw, height_raw: height as i32,
            });
        }
        if !rects.is_empty() { y += row_height + gap; }
        result.push(rects);
    }
    Ok(result)
}


#[cfg(test)]
mod cross_axis_tests {
    use super::*;
    use std::collections::HashMap;
    use serde_json::Value;

    #[test]
    fn shared_rtl_and_row_geometry_fixtures() {
        let fixtures: Value = serde_json::from_str(include_str!(
            "../../../tests/fixtures/grid_cross_axis.json"
        )).unwrap();
        assert_eq!(fixtures["schema_version"], 1);
        for case in fixtures["cases"].as_array().unwrap() {
            let name = case["name"].as_str().unwrap();
            let slots: Vec<GridSlot> = case["items"].as_array().unwrap().iter().map(|item| {
                GridSlot {
                    id: item["id"].as_str().unwrap().to_owned(),
                    span: if item["span"] == "auto" || item["span"].is_null() {
                        None
                    } else { Some(item["span"].as_u64().unwrap() as u8) },
                    offset: item["offset"].as_u64().unwrap_or(0) as u8,
                    order: item["order"].as_i64().unwrap_or(0) as i32,
                }
            }).collect();
            let heights: HashMap<String, f64> = case["heights"].as_object().unwrap()
                .iter().map(|(key, value)| (key.clone(), value.as_f64().unwrap()))
                .collect();
            let rows = pack_grid_rows(&slots).unwrap();
            let result = layout_grid_rects(
                &rows, case["width"].as_f64().unwrap(),
                case["gap"].as_f64().unwrap(),
                case["row_gap"].as_f64().unwrap(),
                &heights, case["rtl"].as_bool().unwrap(),
            );
            if case["error"] == "invalid" {
                assert!(result.is_err(), "{name}: expected error");
                continue;
            }
            let actual = result.unwrap_or_else(|err| panic!("{name}: {err:?}"));
            let expected = case["rows"].as_array().unwrap();
            assert_eq!(actual.len(), expected.len(), "{name}: rows");
            for (row, target_row) in actual.iter().zip(expected) {
                assert_eq!(row.len(), target_row.as_array().unwrap().len(), "{name}");
                for (rect, target) in row.iter().zip(target_row.as_array().unwrap()) {
                    assert_eq!(rect.id, target["id"].as_str().unwrap(), "{name}");
                    assert_eq!(rect.x_raw, target["x_raw"].as_i64().unwrap() as i32, "{name}");
                    assert_eq!(rect.y_raw, target["y_raw"].as_i64().unwrap() as i32, "{name}");
                    assert_eq!(rect.width_raw, target["width_raw"].as_i64().unwrap() as i32, "{name}");
                    assert_eq!(rect.height_raw, target["height_raw"].as_i64().unwrap() as i32, "{name}");
                }
            }
        }
    }
}
