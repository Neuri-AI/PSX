from __future__ import annotations

import pytest

from psx.core.contracts import BUTTON_CONTRACT, INPUT_CONTRACT, TEXT_CONTRACT
from psx.core.errors import RendererCapabilityError
from psx.core.vnode import Button, Input, Text


def test_portable_contracts_are_backend_independent_and_declare_semantics() -> None:
    assert TEXT_CONTRACT.child_policy == "text-only"
    assert BUTTON_CONTRACT.events == {"on_click"}
    assert INPUT_CONTRACT.events == {"on_change", "on_submit"}
    assert TEXT_CONTRACT.with_defaults({"value": "x"})["font_size"] == 16


@pytest.mark.parametrize(
    ("builder", "contract", "props"),
    [
        (Text, TEXT_CONTRACT, {"value": "x", "color": "invalid"}),
        (Button, BUTTON_CONTRACT, {"label": "x", "enabled": 1}),
        (Input, INPUT_CONTRACT, {"value": "x", "placeholder": "", "font_size": 14,
                                  "enabled": True, "read_only": False, "password": False,
                                  "on_change": None, "on_submit": None, "extra": True}),
    ],
)
def test_contract_and_legacy_builders_reject_invalid_portable_props(builder, contract, props) -> None:
    with pytest.raises(RendererCapabilityError):
        contract.validate(props)
    with pytest.raises(RendererCapabilityError):
        builder(**props)
