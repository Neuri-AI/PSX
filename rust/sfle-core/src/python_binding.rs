//! Optional PyO3/maturin boundary for the same versioned pure Rust engine.
//! A rejected layout is returned as an explicit diagnostic, not retried.
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use serde_json::{json,Value};
use crate::compute::{compute,compute_provisional,compute_incremental_with_reuse,LayoutInput,LayoutResult};

#[pyfunction]
fn schema_version() -> u32 { 1 }

fn compute_impl(input: &str, provisional: bool) -> PyResult<String> {
    let snapshot: LayoutInput = serde_json::from_str(input)
        .map_err(|error| PyValueError::new_err(format!("SFLE_INVALID_WIRE: {error}")))?;
    let answer: Value = match if provisional {
        compute_provisional(&snapshot)
    } else {
        compute(&snapshot)
    } {
        Ok(layout) => json!({"ok":true,"result":layout}),
        Err(failure) => json!({"ok":false,"error":{
            "code":failure.code,
            "message":failure.message,
            "node_id":failure.node_id,
        }}),
    };
    serde_json::to_string(&answer)
        .map_err(|error| PyValueError::new_err(format!("SFLE_INVALID_WIRE: {error}")))
}

/// Layout measured inline fragments in the native Rust engine.
#[pyfunction]
fn compute_inline_text_json(input: &str) -> PyResult<String> {
    use crate::semantic_inline_text::{layout_inline, InlineRequest};
    let request: InlineRequest = serde_json::from_str(input)
        .map_err(|error| PyValueError::new_err(
            format!("SFLE_INVALID_INLINE_WIRE: {error}")
        ))?;
    let result = layout_inline(&request).map_err(PyValueError::new_err)?;
    serde_json::to_string(&result)
        .map_err(|error| PyValueError::new_err(
            format!("SFLE_INVALID_INLINE_WIRE: {error}")
        ))
}

#[pyfunction]
fn compute_measured_flow_json(input: &str) -> PyResult<String> {
    use crate::flow_layout::{self, BlockItem, InlineAtom};
    let data: Value = serde_json::from_str(input)
        .map_err(|err| PyValueError::new_err(format!("Invalid measured-flow wire: {err}")))?;
    let bad = || PyValueError::new_err("Invalid measured-flow input.");
    let mode = data["mode"].as_str().ok_or_else(bad)?;
    let width = data["available_width"].as_f64().ok_or_else(bad)?;
    let items = data["items"].as_array().ok_or_else(bad)?;
    let number = |v: &Value, key: &str| -> PyResult<f64> {
        v.get(key).and_then(Value::as_f64).ok_or_else(bad)
    };
    let placements = if mode == "block" {
        let blocks: Vec<BlockItem> = items.iter().map(|item| {
            Ok(BlockItem {
                width: number(item, "width")?,
                height: number(item, "height")?,
                margin_top: number(item, "margin_top")?,
                margin_right: number(item, "margin_right")?,
                margin_bottom: number(item, "margin_bottom")?,
                margin_left: number(item, "margin_left")?,
            })
        }).collect::<PyResult<_>>()?;
        flow_layout::layout_blocks(width, &blocks)
    } else if mode == "inline" {
        let atoms: Vec<InlineAtom> = items.iter().map(|item| {
            Ok(InlineAtom {
                width: number(item, "width")?,
                height: number(item, "height")?,
                baseline: number(item, "baseline")?,
            })
        }).collect::<PyResult<_>>()?;
        flow_layout::layout_inline_atoms(width, &atoms)
    } else {
        return Err(bad());
    };
    let placements = placements.map_err(PyValueError::new_err)?;
    let records: Vec<Value> = placements.iter().map(|p| json!({
        "x": p.x, "y": p.y, "width": p.width, "height": p.height,
    })).collect();
    serde_json::to_string(&records).map_err(|err|
        PyValueError::new_err(format!("Invalid measured-flow result: {err}"))
    )
}

#[pyfunction]
fn compute_recursive_tree_json(input: &str) -> PyResult<String> {
    crate::recursive_wire::calculate(input).map_err(PyValueError::new_err)
}

#[pyfunction]
fn compute_json(input: &str) -> PyResult<String> {
    compute_impl(input, false)
}

#[pyfunction]
fn compute_provisional_json(input: &str) -> PyResult<String> {
    compute_impl(input, true)
}

#[pyfunction]
fn compute_incremental_json(
    input:&str, previous_input:&str, previous_result:&str,
)->PyResult<String>{
    let parse_error=|error:serde_json::Error|
        PyValueError::new_err(format!("SFLE_INVALID_WIRE: {error}"));
    let request:LayoutInput=serde_json::from_str(input).map_err(parse_error)?;
    let old_request:LayoutInput=serde_json::from_str(previous_input).map_err(parse_error)?;
    let old_result:LayoutResult=serde_json::from_str(previous_result).map_err(parse_error)?;
    let mut reused_contexts=Vec::new();
    let answer:Value=match compute_incremental_with_reuse(&request,&old_request,&old_result,&mut reused_contexts) {
        Ok(layout)=>json!({"ok":true,"result":layout,"reused_contexts":reused_contexts}),
        Err(failure)=>json!({"ok":false,"error":{
            "code":failure.code,"message":failure.message,"node_id":failure.node_id,
        }}),
    };
    serde_json::to_string(&answer)
        .map_err(|error|PyValueError::new_err(format!("SFLE_INVALID_WIRE: {error}")))
}

#[pymodule]
fn _sfle_native(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(schema_version,module)?)?;
    module.add_function(wrap_pyfunction!(compute_json,module)?)?;
    module.add_function(wrap_pyfunction!(compute_incremental_json,module)?)?;
    module.add_function(wrap_pyfunction!(compute_provisional_json,module)?)?;
    module.add_function(wrap_pyfunction!(compute_grid_json,module)?)?;
    module.add_function(wrap_pyfunction!(compute_inline_text_json,module)?)?;
    module.add_function(wrap_pyfunction!(compute_measured_flow_json,module)?)?;
    module.add_function(wrap_pyfunction!(compute_recursive_tree_json,module)?)?;
    Ok(())
}


#[pyfunction]
fn compute_grid_json(input: &str) -> PyResult<String> {
    use crate::grid_math::{GridSlot, GridItemConstraints, compute_grid};
    use std::collections::HashMap;
    let value: Value = serde_json::from_str(input)
        .map_err(|e| PyValueError::new_err(format!("Invalid Grid JSON: {e}")))?;
    let invalid = || PyValueError::new_err("Invalid Grid math input");
    let slots = value["items"].as_array().ok_or_else(invalid)?.iter().map(|item| {
        let span = if item["span"].is_null() || item["span"] == "auto" {
            None
        } else {
            Some(u8::try_from(item["span"].as_u64().ok_or_else(invalid)?)
                .map_err(|_| invalid())?)
        };
        Ok(GridSlot {
            id: item["id"].as_str().ok_or_else(invalid)?.to_owned(),
            span,
            offset: u8::try_from(item["offset"].as_u64().unwrap_or(0))
                .map_err(|_| invalid())?,
            order: i32::try_from(item["order"].as_i64().unwrap_or(0))
                .map_err(|_| invalid())?,
        })
    }).collect::<PyResult<Vec<_>>>()?;
    let heights: HashMap<String, f64> = value["heights"].as_object().ok_or_else(invalid)?
        .iter().map(|(key, v)| Ok((key.clone(), v.as_f64().ok_or_else(invalid)?)))
        .collect::<PyResult<_>>()?;
    let bound = |v: &Value, key: &str| -> PyResult<Option<f64>> {
        match v.get(key) {
            None | Some(Value::Null) => Ok(None),
            Some(number) => number.as_f64().map(Some).ok_or_else(invalid),
        }
    };
    let limits: HashMap<String, GridItemConstraints> =
        value["constraints"].as_object().ok_or_else(invalid)?
        .iter().map(|(key, v)| Ok((key.clone(), GridItemConstraints {
            min_width: bound(v, "min_width")?.unwrap_or(0.0),
            max_width: bound(v, "max_width")?,
            min_height: bound(v, "min_height")?.unwrap_or(0.0),
            max_height: bound(v, "max_height")?,
        }))).collect::<PyResult<_>>()?;
    let result = compute_grid(
        &slots,
        value["width"].as_f64().ok_or_else(invalid)?,
        value["column_gap"].as_f64().ok_or_else(invalid)?,
        value["row_gap"].as_f64().ok_or_else(invalid)?,
        &heights, &limits, value["rtl"].as_bool().ok_or_else(invalid)?,
    ).map_err(|e| PyValueError::new_err(format!("Grid math rejected: {e:?}")))?;
    let rows: Vec<Vec<Value>> = result.into_iter().map(|row| row.into_iter().map(|r| json!({
        "id":r.id,"x_raw":r.x_raw,"y_raw":r.y_raw,
        "width_raw":r.width_raw,"height_raw":r.height_raw,
        "used_width_raw":r.used_width_raw,"used_height_raw":r.used_height_raw,
        "overflow_x":r.overflow_x,"overflow_y":r.overflow_y,
    })).collect()).collect();
    serde_json::to_string(&rows)
        .map_err(|e| PyValueError::new_err(format!("Invalid Grid output: {e}")))
}
