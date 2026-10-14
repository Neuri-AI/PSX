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
