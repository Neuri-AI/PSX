"""Migration scanner must discover active API, registration and markup usage."""
import pytest

from scripts.ci.legacy_layout_inventory import references


def test_legacy_layout_inventory_classifies_executable_usage():
    text = '''
from psx import Row, Column
root = Row(Column())
component = create_element("Row")
custom = registry.register("Column", factory)
markup = "<Column><Row /></Column>"
'''
    refs = references("tests/example.py", text)
    assert {(ref.symbol, ref.usage) for ref in refs} >= {
        ("Row", "identifier"),
        ("Column", "identifier"),
        ("Row", "component_name"),
        ("Column", "component_name"),
        ("Row", "markup"),
        ("Column", "markup"),
    }


def test_legacy_layout_inventory_ignores_unrelated_names():
    text = '''
from psx import Flex
tree = Flex(direction="row")
label = "row"
other = "ColumnLayout"
'''
    assert references("tests/example.py", text) == ()


def test_legacy_layout_inventory_fails_on_malformed_python():
    with pytest.raises(SyntaxError):
        references("tests/broken.py", "def invalid(")


def test_legacy_layout_inventory_reports_line_numbers():
    refs = references("tests/example.py", "x = 1\ny = Row()\n")
    assert len(refs) == 1
    assert refs[0].line == 2


def test_legacy_layout_inventory_finds_private_adapter_and_contract_routes():
    refs = references("psx/renderers/example.py", '''
ROW_CONTRACT.validate(options)
adapter = QtColumnAdapter()
validate_row_props(options)
''')
    assert {ref.symbol for ref in refs} == {
        "ROW_CONTRACT", "QtColumnAdapter", "validate_row_props",
    }
