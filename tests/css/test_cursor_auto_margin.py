from psx.css.properties import foundation_registry
from psx.sfle.lengths import LengthKind

def test_margin_auto_is_valid():
    assert foundation_registry().validate('margin-left', 'auto').value.kind is LengthKind.AUTO
