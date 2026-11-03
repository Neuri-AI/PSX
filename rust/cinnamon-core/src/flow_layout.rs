//! Pure geometry for measured normal-flow block boxes and atomic inline boxes.
//! Text shaping, margin collapse and multi-fragment inline formatting are
//! intentionally excluded; callers must reject those unresolved features.
use crate::layout_unit::LayoutUnit;

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Placement { pub x: f64, pub y: f64, pub width: f64, pub height: f64 }

#[derive(Clone, Copy, Debug)]
pub struct BlockItem {
    pub width: f64, pub height: f64, pub margin_top: f64,
    pub margin_right: f64, pub margin_bottom: f64, pub margin_left: f64,
}

#[derive(Clone, Copy, Debug)]
pub struct InlineAtom { pub width: f64, pub height: f64, pub baseline: f64 }

fn px(value: f64) -> Result<f64, &'static str> {
    Ok(LayoutUnit::from_nearest(value)?.to_px())
}

pub fn layout_blocks(available_width: f64, items: &[BlockItem]) -> Result<Vec<Placement>, &'static str> {
    if available_width < 0.0 { return Err("Available block inline size cannot be negative."); }
    let _width = px(available_width)?;
    let mut y = 0.0;
    let mut placements = Vec::with_capacity(items.len());
    for child in items {
        if child.width < 0.0 || child.height < 0.0 {
            return Err("Block border-box dimensions cannot be negative.");
        }
        let top = px(y + child.margin_top)?;
        placements.push(Placement {
            x: px(child.margin_left)?, y: top,
            width: px(child.width)?, height: px(child.height)?,
        });
        y = px(top + child.height + child.margin_bottom)?;
    }
    Ok(placements)
}

pub fn layout_inline_atoms(available_width: f64, atoms: &[InlineAtom]) -> Result<Vec<Placement>, &'static str> {
    if available_width < 0.0 { return Err("Available inline size cannot be negative."); }
    let width = px(available_width)?;
    let mut lines: Vec<Vec<usize>> = Vec::new();
    let mut current = Vec::new();
    let mut used = 0.0;
    for (i, atom) in atoms.iter().enumerate() {
        if atom.width < 0.0 || atom.height < 0.0 || atom.baseline < 0.0 || atom.baseline > atom.height {
            return Err("Invalid atomic inline box metrics.");
        }
        let w = px(atom.width)?;
        if !current.is_empty() && px(used + w)? > width {
            lines.push(std::mem::take(&mut current));
            used = 0.0;
        }
        current.push(i);
        used = px(used + w)?;
    }
    if !current.is_empty() { lines.push(current); }
    let mut output = vec![Placement{x:0.0,y:0.0,width:0.0,height:0.0}; atoms.len()];
    let mut y = 0.0;
    for line in lines {
        let ascent = line.iter().map(|&i| px(atoms[i].baseline)).collect::<Result<Vec<_>,_>>()?
            .into_iter().fold(0.0_f64, f64::max);
        let descent = line.iter().map(|&i| px(atoms[i].height-atoms[i].baseline)).collect::<Result<Vec<_>,_>>()?
            .into_iter().fold(0.0_f64, f64::max);
        let mut x = 0.0;
        for i in line {
            let atom = atoms[i];
            output[i] = Placement {
                x: px(x)?, y: px(y + ascent - atom.baseline)?,
                width: px(atom.width)?, height: px(atom.height)?,
            };
            x = px(x + atom.width)?;
        }
        y = px(y + ascent + descent)?;
    }
    Ok(output)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[derive(serde::Deserialize)]
    struct BlockCase {
        available: f64,
        items: Vec<[f64; 6]>,
        expected: Vec<[f64; 4]>,
    }

    #[derive(serde::Deserialize)]
    struct InlineCase {
        available: f64,
        items: Vec<[f64; 3]>,
        expected: Vec<[f64; 4]>,
    }

    #[derive(serde::Deserialize)]
    struct SharedCases {
        blocks: Vec<BlockCase>,
        inline: Vec<InlineCase>,
    }

    #[test]
    fn block_and_inline_match_shared_language_geometry_vectors() {
        let cases: SharedCases = serde_json::from_str(include_str!(
            "../../../tests/fixtures/flow_geometry_cases.json"
        ))
        .expect("Shared geometry vectors must be valid JSON");

        for case in cases.blocks {
            let items: Vec<BlockItem> = case
                .items
                .iter()
                .map(|entry| BlockItem {
                    width: entry[0],
                    height: entry[1],
                    margin_top: entry[2],
                    margin_right: entry[3],
                    margin_bottom: entry[4],
                    margin_left: entry[5],
                })
                .collect();
            let actual = layout_blocks(case.available, &items).unwrap();
            let observed: Vec<[f64; 4]> = actual
                .iter()
                .map(|rect| [rect.x, rect.y, rect.width, rect.height])
                .collect();
            assert_eq!(observed, case.expected);
        }

        for case in cases.inline {
            let items: Vec<InlineAtom> = case
                .items
                .iter()
                .map(|entry| InlineAtom {
                    width: entry[0],
                    height: entry[1],
                    baseline: entry[2],
                })
                .collect();
            let actual = layout_inline_atoms(case.available, &items).unwrap();
            let observed: Vec<[f64; 4]> = actual
                .iter()
                .map(|rect| [rect.x, rect.y, rect.width, rect.height])
                .collect();
            assert_eq!(observed, case.expected);
        }
    }
    #[test]
    fn blocks_keep_measured_width_and_stack() {
        let items = [
            BlockItem{width:320.0,height:40.0,margin_top:0.0,margin_right:0.0,margin_bottom:0.0,margin_left:0.0},
            BlockItem{width:220.0,height:25.0,margin_top:10.0,margin_right:0.0,margin_bottom:0.0,margin_left:15.0},
        ];
        let rects=layout_blocks(320.0,&items).unwrap();
        assert_eq!(rects[1],Placement{x:15.0,y:50.0,width:220.0,height:25.0});
    }
    #[test]
    fn inline_atoms_wrap_on_width_and_respect_baselines() {
        let items = [
            InlineAtom{width:60.0,height:20.0,baseline:15.0},
            InlineAtom{width:40.0,height:10.0,baseline:8.0},
            InlineAtom{width:35.0,height:12.0,baseline:9.0},
        ];
        let rects=layout_inline_atoms(100.0,&items).unwrap();
        assert_eq!(rects[1].y,7.0);
        assert_eq!(rects[2].y,20.0);
    }
}
