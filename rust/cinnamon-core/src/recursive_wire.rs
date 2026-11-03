//! Versioned historical resolved-margin-tree wire adapter.
//!
//! This is serialization/validation only. All geometry is produced by the
//! existing independent Rust margin_tree and auto_cross_tree kernels.
use serde::Deserialize;
use serde_json::{json, Value};
use crate::margin_tree::{MarginTreeNode, compute_margin_tree};
use crate::margin_flex_pipeline::MarginFlexItem;
use crate::line_layout::{Direction, Wrap, WritingDirection};
use crate::main_alignment::JustifyContent;
use crate::align_content::AlignContent;
use crate::cross_alignment::CrossAlign;
use crate::edge_pipeline::{BoxEdges, Edges};
use crate::intrinsic::{IntrinsicFlexInput, IntrinsicSizes, MainAxis, OverflowMode, Basis};
use crate::FlexBasis;

#[derive(Deserialize)]
struct Request {
    generation: u64,
    writing: String,
    nodes: Vec<Node>,
    #[serde(default)]
    auto_cross: Vec<String>,
}
#[derive(Deserialize)]
struct Node {
    node_id: String,
    parent_id: Option<String>,
    width: f64, height: f64,
    item: Option<Item>,
    edges: WireBoxEdges,
    direction: String,
    wrap: String,
    main_gap: f64, cross_gap: f64,
    justify: String,
    align_items: String,
    align_content: String,
    intrinsic_basis: Option<WireIntrinsic>,
}
#[derive(Deserialize)]
struct WireEdges { top: f64, right: f64, bottom: f64, left: f64 }
#[derive(Deserialize)]
struct WireBoxEdges { margin: WireEdges, border: WireEdges, padding: WireEdges }
#[derive(Deserialize)]
struct Flex { basis: f64, hypothetical: f64, grow: f64, shrink: f64,
    min_size: f64, max_size: Option<f64> }
#[derive(Deserialize)]
struct WireMargin { value: Option<f64> }
#[derive(Deserialize)]
struct Item {
    node_id: String, flex: Flex, cross_content_size: f64,
    edges: WireBoxEdges, main_start: WireMargin, main_end: WireMargin,
    order: i32, cross_start: WireMargin, cross_end: WireMargin,
    align_self: String, cross_size_auto: bool,
    min_cross_content_size: f64, max_cross_content_size: Option<f64>,
    baseline_from_cross_start: Option<f64>,
}
#[derive(Deserialize)]
struct WireLength { kind: String, value: Option<f64> }
#[derive(Deserialize)]
struct WireIntrinsicSizes {
    min_content_width: f64, max_content_width: f64,
    min_content_height: f64, max_content_height: f64,
    preferred_width: f64, preferred_height: f64,
}
#[derive(Deserialize)]
struct WireIntrinsic {
    intrinsic: WireIntrinsicSizes,
    axis: String, flex_basis: WireLength,
    grow: f64, shrink: f64,
    preferred_main_size: Option<f64>, max_main_size: Option<f64>,
    min_main_size: Option<f64>, overflow: String, scroll_container: bool,
    aspect_ratio: Option<f64>, preferred_cross_size: Option<f64>,
    replaced: bool, has_aspect_ratio_transfer: bool,
}
fn parsed<T: Copy>(input: &str, variants: &[(&str, T)], name: &str) -> Result<T, String> {
    variants.iter().find(|(key,_)| *key == input)
        .map(|(_, val)| *val).ok_or_else(|| format!("Unknown {name}: {input}"))
}
fn direction(v:&str)->Result<Direction,String>{
    parsed(v,&[("row",Direction::Row),("row-reverse",Direction::RowReverse),
        ("column",Direction::Column),("column-reverse",Direction::ColumnReverse)],"direction")
}
fn wrap(v:&str)->Result<Wrap,String>{
    parsed(v,&[("nowrap",Wrap::NoWrap),("wrap",Wrap::Wrap),
        ("wrap-reverse",Wrap::WrapReverse)],"wrap")
}
fn justify(v:&str)->Result<JustifyContent,String>{
    parsed(v,&[("flex-start",JustifyContent::FlexStart),
        ("flex-end",JustifyContent::FlexEnd),("center",JustifyContent::Center),
        ("space-between",JustifyContent::SpaceBetween),
        ("space-around",JustifyContent::SpaceAround),
        ("space-evenly",JustifyContent::SpaceEvenly)],"justify")
}
fn cross(v:&str)->Result<CrossAlign,String>{
    parsed(v,&[("auto",CrossAlign::Auto),("flex-start",CrossAlign::FlexStart),
        ("flex-end",CrossAlign::FlexEnd),("center",CrossAlign::Center),
        ("stretch",CrossAlign::Stretch),("baseline",CrossAlign::Baseline)],"align")
}
fn align(v:&str)->Result<AlignContent,String>{
    parsed(v,&[("flex-start",AlignContent::FlexStart),
        ("flex-end",AlignContent::FlexEnd),("center",AlignContent::Center),
        ("space-between",AlignContent::SpaceBetween),
        ("space-around",AlignContent::SpaceAround),
        ("space-evenly",AlignContent::SpaceEvenly),
        ("stretch",AlignContent::Stretch)],"align-content")
}
fn axis(v:&str)->Result<MainAxis,String>{
    parsed(v,&[("horizontal",MainAxis::Horizontal),
        ("vertical",MainAxis::Vertical)],"intrinsic axis")
}
fn overflow(v:&str)->Result<OverflowMode,String>{
    parsed(v,&[("visible",OverflowMode::Visible),("clip",OverflowMode::Clip),
        ("hidden",OverflowMode::Hidden),("auto",OverflowMode::Auto),
        ("scroll",OverflowMode::Scroll)],"overflow")
}
impl From<WireEdges> for Edges {
    fn from(e:WireEdges)->Self {
        Self{top:e.top,right:e.right,bottom:e.bottom,left:e.left}
    }
}
impl From<WireBoxEdges> for BoxEdges {
    fn from(e:WireBoxEdges)->Self {
        Self{margin:e.margin.into(),border:e.border.into(),padding:e.padding.into()}
    }
}
impl From<Flex> for FlexBasis {
    fn from(f:Flex)->Self {
        Self{basis:f.basis,hypothetical:f.hypothetical,grow:f.grow,
            shrink:f.shrink,min_size:f.min_size,max_size:f.max_size}
    }
}
impl WireIntrinsic {
    fn into_core(self)->Result<IntrinsicFlexInput,String> {
        let basis = match self.flex_basis.kind.as_str() {
            "px" => Basis::Px(self.flex_basis.value.ok_or("px basis requires value")?),
            "auto" => Basis::Auto,
            "min-content" => Basis::MinContent,
            "max-content" => Basis::MaxContent,
            "content" => Basis::Content,
            _ => Basis::Unsupported,
        };
        let m=self.intrinsic;
        Ok(IntrinsicFlexInput{
            intrinsic:IntrinsicSizes{
                min_content_width:m.min_content_width,
                max_content_width:m.max_content_width,
                min_content_height:m.min_content_height,
                max_content_height:m.max_content_height,
                preferred_width:m.preferred_width,
                preferred_height:m.preferred_height,
            },
            axis:axis(&self.axis)?,flex_basis:basis,grow:self.grow,shrink:self.shrink,
            preferred_main_size:self.preferred_main_size,
            max_main_size:self.max_main_size,min_main_size:self.min_main_size,
            overflow:overflow(&self.overflow)?,scroll_container:self.scroll_container,
            aspect_ratio:self.aspect_ratio,preferred_cross_size:self.preferred_cross_size,
            replaced:self.replaced,
            has_aspect_ratio_transfer:self.has_aspect_ratio_transfer,
        })
    }
}
impl Item {
    fn into_core(self)->Result<MarginFlexItem,String> {
        Ok(MarginFlexItem{
            id:self.node_id,flex:self.flex.into(),
            cross_content_size:self.cross_content_size,
            edges:self.edges.into(),main_start:self.main_start.value,
            main_end:self.main_end.value,order:self.order,
            cross_start:self.cross_start.value,cross_end:self.cross_end.value,
            align_self:cross(&self.align_self)?,cross_size_auto:self.cross_size_auto,
            min_cross_content_size:self.min_cross_content_size,
            max_cross_content_size:self.max_cross_content_size,
            baseline_from_cross_start:self.baseline_from_cross_start,
        })
    }
}
impl Node {
    fn into_core(self)->Result<MarginTreeNode,String>{
        Ok(MarginTreeNode{
            id:self.node_id,parent:self.parent_id,width:self.width,height:self.height,
            item:self.item.map(Item::into_core).transpose()?,
            edges:self.edges.into(),direction:direction(&self.direction)?,
            wrap:wrap(&self.wrap)?,main_gap:self.main_gap,cross_gap:self.cross_gap,
            justify:justify(&self.justify)?,align_items:cross(&self.align_items)?,
            align_content:align(&self.align_content)?,
            intrinsic_basis:self.intrinsic_basis.map(WireIntrinsic::into_core).transpose()?,
        })
    }
}
pub fn calculate(input:&str)->Result<String,String>{
    let req:Request=serde_json::from_str(input)
        .map_err(|e|format!("Malformed recursive Cinnamon wire: {e}"))?;
    let writing=parsed(&req.writing,&[
        ("ltr",WritingDirection::Ltr),("rtl",WritingDirection::Rtl)],"writing direction")?;
    let nodes:Vec<MarginTreeNode>=req.nodes.into_iter()
        .map(Node::into_core).collect::<Result<_,_>>()?;
    let layout=if req.auto_cross.is_empty(){
        compute_margin_tree(&nodes,writing)
    } else {
        crate::auto_cross_tree::compute_auto_cross_tree(&nodes,&req.auto_cross,writing)
    }.map_err(|e|format!("Recursive Cinnamon geometry failed: {e:?}"))?;
    let boxes:Vec<Value>=layout.boxes.iter().map(|b|{
        let rect=|r:crate::line_layout::Rect|json!({
            "x":r.x,"y":r.y,"width":r.width,"height":r.height,
        });
        json!({"node_id":b.id,"content":rect(b.content),"padding":rect(b.padding),
            "border":rect(b.border),
            "used_main_start_margin":b.used_main_start_margin,
            "used_main_end_margin":b.used_main_end_margin,
            "line_index":b.line_index,
            "used_cross_start_margin":b.used_cross_start_margin,
            "used_cross_end_margin":b.used_cross_end_margin})
    }).collect();
    serde_json::to_string(&json!({"generation":req.generation,"boxes":boxes}))
        .map_err(|e|e.to_string())
}
