mod common;
use sfle_core::compute::compute;

#[test]
fn accepted_cyclic_percentage_cases_use_real_rust_engine() {
    let mut failures=Vec::new();
    for id in ["C01","C02","C03","C04","C05","C06"] {
        let (case,snapshot)=common::fixture(id);
        match compute(&snapshot) {
            Err(error)=>failures.push(format!("{id}: {} {}",error.code,error.message)),
            Ok(result)=>{
                for (key,value) in case["expected"].as_object().unwrap() {
                    if key=="intrinsic_gap"||key=="used_gap" {continue;}
                    let Some(expected)=value.as_f64() else{continue;};
                    let Some((node,axis))=key.split_once('.') else{continue;};
                    let Some(rect)=result.boxes.iter().find(|b|b.node_id==node) else{
                        failures.push(format!("{id}: missing {node}"));continue;
                    };
                    let actual=match axis{
                        "width"=>rect.content.width,"height"=>rect.content.height,
                        "x"=>rect.content.x,"y"=>rect.content.y,
                        "padding_top"=>rect.content.y-rect.padding.y,
                        _=>{failures.push(format!("{id}: unexpected {axis}"));continue;}
                    };
                    if (actual-expected).abs()>0.01{
                        failures.push(format!("{id} {key}: {actual} != {expected}"));
                    }
                }
            }
        }
    }
    assert!(failures.is_empty(),"Rust C01-C06 acceptance failures:\n{}",failures.join("\n"));
}
