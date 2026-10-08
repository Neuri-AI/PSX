from __future__ import annotations

import unittest

from psx.core.errors import PSXError
from psx.integrations.qyro import _store_for_component


class _Store:
    def get_state(self):
        return {}

    def dispatch(self, action):
        return action

    def select(self, **kwargs):
        return lambda: None


def _component_with(namespace: dict[str, object]):
    exec("class View:\n    def render(self):\n        pass\n", namespace)
    return namespace["View"]()


class QyroStoreDiscoveryTests(unittest.TestCase):
    def test_uses_the_only_module_level_pydux_store(self) -> None:
        store = _Store()
        component = _component_with({"store": store})
        self.assertIs(_store_for_component(component), store)

    def test_multiple_stores_require_an_explicit_choice(self) -> None:
        component = _component_with({"first": _Store(), "second": _Store()})
        with self.assertRaisesRegex(PSXError, "More than one Pydux store"):
            _store_for_component(component)

    def test_explicit_store_wins_over_module_discovery(self) -> None:
        expected = _Store()
        component = _component_with({"first": _Store(), "second": _Store()})
        component.psx_store = expected
        self.assertIs(_store_for_component(component), expected)
