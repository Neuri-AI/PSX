"""HTML radio name groups use the portable exclusive-selection native host."""
import pytest
from psx.markup.compile import psx
from psx.markup.html_aliases import InputChangeEvent

MARKUP = """
<>
  <div><input type="radio" id="email" name="contacto" value="email" checked />
       <label for="email">Correo electrónico</label></div>
  <div><input type="radio" id="telefono" name="contacto" value="telefono" />
       <label for="telefono">Teléfono</label></div>
  <div><input type="radio" id="whatsapp" name="contacto" value="whatsapp" />
       <label for="whatsapp">WhatsApp</label></div>
</>
"""

def test_radio_options_share_a_native_exclusive_group_with_clickable_labels():
    root = psx(MARKUP)
    group = root.children[0] if root.type == "Fragment" else root
    assert group.type == "RadioGroup"
    assert group.props["value"] == "email"
    assert [child.props["label"] for child in group.children] == [
        "Correo electrónico", "Teléfono", "WhatsApp",
    ]
    assert [child.props["value"] for child in group.children] == [
        "email", "telefono", "whatsapp",
    ]
    assert all(child.type == "Radio" for child in group.children)

def test_radio_change_emits_original_name_value_and_checked():
    events = []
    root = psx(MARKUP.replace('name="contacto"', 'name="contacto" on_change={changed}'),
               scope={"changed":events.append})
    group = root.children[0] if root.type == "Fragment" else root
    group.props["on_change"]("telefono")
    assert len(events) == 1 and isinstance(events[0], InputChangeEvent)
    assert events[0].target.name == "contacto"
    assert events[0].target.value == "telefono"
    assert events[0].target.checked is True

def test_multiple_checked_radios_in_one_named_group_rejected():
    with pytest.raises(ValueError, match="More than one checked"):
        psx(MARKUP.replace('value="telefono" />', 'value="telefono" checked />'))

def test_unnamed_html_radio_reports_missing_group_name():
    with pytest.raises(ValueError, match="group name"):
        psx('<input type="radio" value="a"/>')


def test_checkbox_label_for_is_part_of_native_toggle_hit_target():
    tree = psx('<div><input type="checkbox" id="scales" name="scales" checked />'
               '<label for="scales">Escamas</label></div>')
    assert tree.type == "div"
    assert len(tree.children) == 1
    checkbox = tree.children[0]
    assert checkbox.type == "Checkbox"
    assert checkbox.props["checked"] is True
    assert checkbox.props["label"] == "Escamas"
