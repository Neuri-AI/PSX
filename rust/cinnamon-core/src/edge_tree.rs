//! Pure nested resolved Flex with padding/border content origins.
//! CSS lengths and intrinsic flex bases must be resolved upstream.

use crate::edge_pipeline::{BoxEdges, BoxRect, EdgeItem, compute_edge_layout, Edges};
use crate::line_layout::{Direction, Rect, Wrap, WritingDirection};
use crate::{FlexBasis, FlexMathError};
use std::collections::HashMap;

#[derive(Clone, Debug, PartialEq)]
pub struct EdgeTreeNode {
    pub id: String,
    pub parent: Option<String>,
    pub width: f64,
    pub height: f64,
    pub flex: Option<FlexBasis>,
    pub edges: BoxEdges,
    pub direction: Direction,
    pub wrap: Wrap,
    pub main_gap: f64,
    pub cross_gap: f64,
    pub order: i32,
}

fn move_rect(rect: Rect, x: f64, y: f64) -> Rect {
    Rect { x: rect.x + x, y: rect.y + y, ..rect }
}
fn move_box(b: BoxRect, x: f64, y: f64) -> BoxRect {
    BoxRect {
        content: move_rect(b.content,x,y),
        padding: move_rect(b.padding,x,y),
        border: move_rect(b.border,x,y),
        margin: move_rect(b.margin,x,y),
    }
}

pub fn compute_edge_tree(
    nodes: &[EdgeTreeNode],
    writing: WritingDirection,
) -> Result<Vec<(String, BoxRect)>, FlexMathError> {
    if nodes.is_empty() { return Ok(vec![]); }
    let mut children: HashMap<&str,Vec<usize>> = HashMap::new();
    for (i,node) in nodes.iter().enumerate() {
        if node.id.is_empty() || children.contains_key(node.id.as_str())
            || ![node.width,node.height,node.main_gap,node.cross_gap]
                .iter().all(|v| v.is_finite() && *v>=0.0)
            || node.edges.margin != Edges::default()
        { return Err(FlexMathError::InvalidInput("invalid edge-tree node")); }
        if i==0 {
            if node.parent.is_some() { return Err(FlexMathError::InvalidInput("root has parent")); }
        } else {
            let parent = node.parent.as_deref().ok_or(
                FlexMathError::InvalidInput("missing parent")
            )?;
            if node.flex.is_none() || !children.contains_key(parent) {
                return Err(FlexMathError::InvalidInput("non-preorder parent or flex basis"));
            }
            children.get_mut(parent).expect("validated").push(i);
        }
        children.insert(node.id.as_str(),vec![]);
    }
    let root=&nodes[0];
    let e=root.edges;
    let border=Rect {
        x:0.0,y:0.0,
        width:root.width+e.padding.left+e.padding.right+e.border.left+e.border.right,
        height:root.height+e.padding.top+e.padding.bottom+e.border.top+e.border.bottom,
    };
    let padding=Rect {
        x:e.border.left,y:e.border.top,
        width:root.width+e.padding.left+e.padding.right,
        height:root.height+e.padding.top+e.padding.bottom,
    };
    let content=Rect {
        x:padding.x+e.padding.left,y:padding.y+e.padding.top,
        width:root.width,height:root.height,
    };
    let mut geometry=HashMap::new();
    geometry.insert(root.id.as_str(), BoxRect {content,padding,border,margin:border});
    for node in nodes {
        let origin=geometry[node.id.as_str()].content;
        let horizontal=matches!(node.direction,Direction::Row|Direction::RowReverse);
        let child_indices=&children[node.id.as_str()];
        if child_indices.is_empty() {continue;}
        let items:Vec<_>=child_indices.iter().map(|&index|{
            let child=&nodes[index];
            EdgeItem {
                id:child.id.clone(),
                flex:child.flex.expect("validated"),
                cross_content_size:if horizontal {child.height} else {child.width},
                edges:child.edges,
                order:child.order,
            }
        }).collect();
        let result=compute_edge_layout(
            &items,origin.width,origin.height,node.direction,writing,node.wrap,
            node.main_gap,node.cross_gap,
        )?;
        for (id,b) in result.boxes {
            let key=nodes.iter().find(|n|n.id==id).expect("known ID").id.as_str();
            geometry.insert(key,move_box(b,origin.x,origin.y));
        }
    }
    Ok(nodes.iter().map(|n|(n.id.clone(),geometry[n.id.as_str()])).collect())
}

#[cfg(test)]
mod tests {
    use super::*;
    fn basis(v:f64)->FlexBasis {
        FlexBasis {basis:v,hypothetical:v,grow:0.0,shrink:1.0,min_size:0.0,max_size:None}
    }
    fn node(id:&str,parent:Option<&str>,w:f64,h:f64,flex:Option<FlexBasis>)->EdgeTreeNode{
        EdgeTreeNode{
            id:id.into(),parent:parent.map(str::to_string),width:w,height:h,flex,
            edges:BoxEdges::default(),direction:Direction::Row,wrap:Wrap::NoWrap,
            main_gap:0.0,cross_gap:0.0,order:0,
        }
    }
    #[test]
    fn nested_edges_shift_descendant_content_origin() {
        let mut root=node("root",None,200.0,80.0,None);
        root.edges.padding.left=5.0;
        root.edges.border.left=1.0;
        let mut parent=node("parent",Some("root"),50.0,30.0,Some(basis(50.0)));
        parent.edges.padding.left=6.0;
        parent.edges.border.left=2.0;
        let leaf=node("leaf",Some("parent"),10.0,10.0,Some(basis(10.0)));
        let boxes=compute_edge_tree(&[root,parent,leaf],WritingDirection::Ltr).unwrap();
        assert_eq!(boxes[1].1.border.x,6.0);
        assert_eq!(boxes[1].1.content.x,14.0);
        assert_eq!(boxes[2].1.border.x,14.0);
    }
}
