//! SFLE v1 normalized snapshot runner for cross-language differential CI.
//! This is a pure batch diagnostic binary, not a public PSX API or PyO3 wheel.
use std::io::{self,Read};
use sfle_core::compute::{compute,compute_provisional,LayoutInput};
use serde_json::json;

fn main() {
    let mut text=String::new();
    if let Err(error)=io::stdin().read_to_string(&mut text) {
        println!("{}",json!({"ok":false,"error":{"code":"SFLE_INVALID_WIRE","message":error.to_string(),"node_id":null}}));
        return;
    }
    let snapshot: LayoutInput=match serde_json::from_str(&text){
        Ok(value)=>value,
        Err(error)=>{
            println!("{}",json!({"ok":false,"error":{"code":"SFLE_INVALID_WIRE","message":error.to_string(),"node_id":null}}));
            return;
        }
    };
    let provisional=std::env::args().skip(1).any(|arg|arg=="--provisional");
    let outcome=if provisional{compute_provisional(&snapshot)}else{compute(&snapshot)};
    match outcome{
        Ok(result)=>println!("{}",json!({"ok":true,"result":result})),
        Err(error)=>println!("{}",json!({"ok":false,"error":{
            "code":error.code,"message":error.message,"node_id":error.node_id,
        }})),
    }
}
