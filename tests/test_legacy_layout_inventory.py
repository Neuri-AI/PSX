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


def test_legacy_layout_inventory_detects_import_only_no_builder_call():
    refs = references("tests/old_adapter.py", "from psx import Row, Column\n")
    assert {(item.symbol, item.usage) for item in refs} == {
        ("Row", "import"), ("Column", "import"),
    }


def test_shipped_python_examples_no_longer_depend_on_legacy_containers():
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    examples = sorted((root / "examples").rglob("*.py"))
    assert examples
    violations = [
        item for file in examples
        for item in references(
            file.relative_to(root).as_posix(),
            file.read_text(encoding="utf-8"),
        )
    ]
    assert not violations, violations



@pytest.mark.parametrize("legacy_name", ("Row", "Column"))
def test_removed_portable_layout_cannot_be_imported_or_resolved(legacy_name):
    import psx
    from psx.core.errors import MarkupSyntaxError, UnknownComponentError
    from psx.core.registry import builtin_component_registry

    assert legacy_name not in psx.__all__
    assert not hasattr(psx, legacy_name)
    registry = builtin_component_registry()
    assert not registry.contains(legacy_name)
    with pytest.raises(UnknownComponentError):
        registry.resolve(legacy_name)
    with pytest.raises(MarkupSyntaxError, match="Unknown PSX tag"):
        psx.psx(f"<{legacy_name} />")


def test_native_renderers_cannot_register_a_second_layout_authority():
    # Runtime bridge adapters must never register removed layout engines.
    from psx.renderers.headless import HeadlessRenderer
    renderer = HeadlessRenderer()
    assert renderer.adapters.get("Row") is None
    assert renderer.adapters.get("Column") is None
