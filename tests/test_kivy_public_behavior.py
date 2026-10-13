"""Kivy widget behavior assertions executed against real SDL2 providers."""
from __future__ import annotations

import os
import subprocess
import sys
import textwrap

import pytest

from tests.certification.public_behavior_census import Feature, assert_feature


@pytest.mark.parametrize(("component", "property_name"), [
    ("Input", "value"),
    ("Checkbox", "checked"),
    ("ProgressBar", "value"),
])
def test_kivy_native_updated_widget_survives_reconciliation(request, component, property_name):
    # A fresh interpreter isolates Kivy's singleton application and graphics
    # provider, exactly as the mandatory native Kivy layout suite does.
    script = textwrap.dedent("""
        from kivy.config import Config
        Config.set('graphics', 'window_state', 'hidden')
        from psx import Flex, Input, Checkbox, ProgressBar
        from psx.core.reconcile import Reconciler
        from psx.renderers.kivy.kivy import KivyRenderer
        from psx.sfle.engine import PythonLayoutEngine
        from psx.sfle.model import AvailableSize, LayoutConstraints

        renderer = KivyRenderer(
            sfle_constraints=LayoutConstraints(
                AvailableSize(260, True), AvailableSize(80, True)),
            engine=PythonLayoutEngine())
        tree = Reconciler(renderer)
        component = COMPONENT
        def view(updated):
            port = {
                'Input': lambda v: Input(
                    value='after' if v else 'before',
                    key='control', layout_width='120px',
                    layout_height='32px', flex_basis='120px', flex_shrink=0),
                'Checkbox': lambda v: Checkbox(
                    checked=v, key='control', layout_width='32px',
                    layout_height='32px', flex_basis='32px', flex_shrink=0),
                'ProgressBar': lambda v: ProgressBar(
                    value=65 if v else 25, key='control',
                    layout_width='120px', layout_height='32px',
                    flex_basis='120px', flex_shrink=0),
            }[component]
            return Flex(port(updated), width='260px', height='80px',
                        align_items='flex-start')
        read = {
            'Input': lambda widget: widget.text,
            'Checkbox': lambda widget: widget.active,
            'ProgressBar': lambda widget: widget.value,
        }[component]
        before = {'Input': 'before', 'Checkbox': False, 'ProgressBar': 25}[component]
        after = {'Input': 'after', 'Checkbox': True, 'ProgressBar': 65}[component]
        first = tree.render(view(False))
        widget = first.children[0].handle.widget
        assert read(widget) == before, (component, read(widget), before)
        updated = tree.render(view(True))
        assert updated.children[0].handle.widget is widget, component
        assert read(widget) == after, (component, read(widget), after)
        assert renderer.sfle_result.geometry_commit_error <= 1
        tree.unmount()
    """).replace("COMPONENT", repr(component))
    env = dict(os.environ, KIVY_NO_FILELOG="1", KIVY_NO_ARGS="1")
    env["PYTHONPATH"] = "src" + os.pathsep + env.get("PYTHONPATH", "")
    result = subprocess.run([sys.executable, "-c", script], env=env,
                            capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    for scenario in ("live_update", "native_readback"):
        assert_feature(request, Feature(component, "kivy", "property",
                                        property_name, scenario, applicability="native"),
                       result.returncode == 0)
