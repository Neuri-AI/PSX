//! Optional PyO3/maturin boundary for the same versioned pure Rust engine.
//! A rejected layout is returned as an explicit diagnostic, not retried.
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use serde_json::{json,Value};
use crate::compute::{compute,compute_provisional,LayoutInput};

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

#[pyfunction]
fn compute_json(input: &str) -> PyResult<String> {
    compute_impl(input, false)
}

#[pyfunction]
fn compute_provisional_json(input: &str) -> PyResult<String> {
    compute_impl(input, true)
}

#[pymodule]
fn _sfle_native(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(schema_version,module)?)?;
    module.add_function(wrap_pyfunction!(compute_json,module)?)?;
    module.add_function(wrap_pyfunction!(compute_provisional_json,module)?)?;
    Ok(())
}
