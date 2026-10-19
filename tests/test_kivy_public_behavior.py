"""Public Kivy behavior certified through actual isolated SDL2 native widgets."""
from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest
from tests.certification.public_behavior_census import Feature, assert_feature

COMPONENTS = ('Text', 'Button', 'Input', 'TextArea', 'Checkbox', 'Slider', 'Select',
              'ProgressBar', 'Radio', 'RadioGroup', 'Switch', 'SpinBox', 'Divider', 'Link', 'Badge')
EVENTS = [('Button', 'on_click'), ('Checkbox', 'on_change'), ('Input', 'on_change'),
          ('Input', 'on_submit'), ('TextArea', 'on_change'), ('Slider', 'on_change'),
          ('Select', 'on_change'), ('Switch', 'on_change'), ('SpinBox', 'on_change'),
          ('RadioGroup', 'on_change'), ('Link', 'on_click')]


def run_driver(request, component, mode, *args):
    env = dict(os.environ, KIVY_NO_FILELOG='1', KIVY_NO_ARGS='1', KIVY_WINDOW='sdl2', KIVY_TEXT='sdl2')
    result = subprocess.run([sys.executable, '-m',
        'tests.certification.kivy_public_behavior_driver', mode, component, *args],
        env=env, capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stdout + '\n' + result.stderr
    receipts = [line for line in result.stdout.splitlines() if line.startswith('PSX_NATIVE_VERIFIED=')]
    assert len(receipts) == 1, result.stdout
    verified = json.loads(receipts[0].split('=', 1)[1])
    assert verified
    assert len({tuple(row) for row in verified}) == len(verified)
    for kind, name, scenario in verified:
        assert_feature(request, Feature(component, 'kivy', kind, name, scenario,
                                        applicability='native'), True)


@pytest.mark.parametrize('component', COMPONENTS)
def test_kivy_public_property_update_and_native_readback(request, component):
    run_driver(request, component, 'property')


@pytest.mark.parametrize(('component', 'event'), EVENTS)
def test_kivy_real_event_payload_rebind_and_teardown(request, component, event):
    run_driver(request, component, 'event', event)


@pytest.mark.parametrize('component', COMPONENTS + ('Image', 'Spacer', 'Box', 'Flex', 'Scroll'))
def test_kivy_keyed_native_mount_update_reorder_unmount(request, component):
    run_driver(request, component, 'lifecycle')


@pytest.mark.parametrize(('component', 'event'), [row for row in EVENTS
    if row[0] in ('Button', 'Checkbox', 'Slider', 'Select', 'Switch', 'SpinBox', 'RadioGroup')])
def test_kivy_disabled_controls_reject_native_touch(request, component, event):
    run_driver(request, component, 'disabled', event)


@pytest.mark.parametrize('component', ('Input', 'Slider', 'SpinBox', 'Select'))
def test_kivy_coupled_properties_produce_real_native_behavior(request, component):
    run_driver(request, component, 'interaction')


@pytest.mark.parametrize('component', ('Image', 'Badge'))
def test_kivy_native_resource_and_canvas_property_updates(request, component):
    run_driver(request, component, 'decoration')


def test_kivy_radio_value_update_reindexes_native_group_and_event_payload(request):
    run_driver(request, 'Radio', 'radio_value')


@pytest.mark.parametrize('component', ('Grid', 'GridItem'))
def test_kivy_grid_unsupported_mount_fails_before_native_allocation(request, component):
    env = dict(os.environ, KIVY_NO_FILELOG='1', KIVY_NO_ARGS='1', KIVY_WINDOW='sdl2', KIVY_TEXT='sdl2')
    result = subprocess.run([sys.executable, '-m',
        'tests.certification.kivy_public_behavior_driver', 'grid_unsupported_mount', component],
        env=env, capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stdout + '\n' + result.stderr
    receipts = [line for line in result.stdout.splitlines() if line.startswith('PSX_NATIVE_VERIFIED=')]
    assert len(receipts) == 1
    assert json.loads(receipts[0].split('=', 1)[1]) == [['interaction', 'unsupported_mount', 'kivy_fail_closed']]
    from tests.certification.public_behavior_census import CONTRACT
    assert_feature(request, Feature(component, CONTRACT, 'interaction',
                                    'unsupported_mount', 'kivy_fail_closed',
                                    applicability='shared'), True)


def test_html_block_native_geometry_and_reconciliation(request):
    script = """
from kivy.config import Config
Config.set("graphics", "window_state", "hidden")
from psx import psx
from psx.core.reconcile import Reconciler
from psx.renderers.kivy.kivy import KivyRenderer
from psx.sfle.engine import PythonLayoutEngine
from psx.sfle.model import AvailableSize, LayoutConstraints

renderer = KivyRenderer(
    sfle_constraints=LayoutConstraints(
        AvailableSize(400, True), AvailableSize(120, True)),
    engine=PythonLayoutEngine(),
)
tree = Reconciler(renderer)
first = tree.render(psx(
    '<div><button key="a">Alpha</button><button key="b">Beta</button></div>'
))
alpha, beta = (item.handle.widget for item in first.children)
root_widget = first.handle.widget
updated = tree.render(psx(
    '<div><button key="b">Beta</button><button key="a">Alpha</button></div>'
))
assert updated.handle.widget is root_widget
assert updated.children[0].handle.widget is beta
assert updated.children[1].handle.widget is alpha
assert round(alpha.width) == 400 and round(beta.width) == 400
assert round(beta.y) == round(alpha.y + alpha.height)
assert round(root_widget.height) == 120
inline = tree.render(psx(
    '<div display="inline"><button key="b">Beta</button>'
    '<button key="a">Alpha</button></div>'
))
assert inline.handle.widget is root_widget
assert inline.children[0].handle.widget is beta
assert inline.children[1].handle.widget is alpha
assert round(beta.x) == 0
assert round(alpha.x) == round(beta.x + beta.width)
assert round(alpha.width) < 400
prior_generation = renderer.sfle_result.generation
renderer.set_sfle_constraints(LayoutConstraints(
    AvailableSize(240, True), AvailableSize(120, True),
))
resized = tree.render(psx(
    '<div><button key="b">Beta</button><button key="a">Alpha</button></div>'
))
assert resized.children[0].handle.widget is beta
assert resized.children[1].handle.widget is alpha
assert round(beta.width) == 240 and round(alpha.width) == 240
assert round(beta.y) == round(alpha.y + alpha.height)
assert renderer.sfle_result.generation > prior_generation
tree.unmount()
assert alpha.parent is None and beta.parent is None
"""
    environment = dict(
        os.environ, KIVY_NO_FILELOG="1", KIVY_NO_ARGS="1",
        KIVY_WINDOW="sdl2", KIVY_TEXT="sdl2",
    )
    run = subprocess.run(
        [sys.executable, "-c", script],
        env=environment, capture_output=True, text=True, timeout=90,
    )
    assert_feature(
        request, Feature("div", "kivy", "interaction", "semantic_flow",
                         "native_geometry", applicability="partial_native"),
        run.returncode == 0, run.stdout + "\\n" + run.stderr,
    )
    assert_feature(
        request, Feature("div", "kivy", "interaction", "semantic_flow",
                         "display_reflow", applicability="partial_native"),
        run.returncode == 0, run.stdout + "\\n" + run.stderr,
    )
    assert_feature(
        request, Feature("div", "kivy", "interaction", "semantic_flow",
                         "viewport_reflow", applicability="partial_native"),
        run.returncode == 0, run.stdout + "\\n" + run.stderr,
    )


def test_semantic_flow_native_geometry_per_tag(request):
    tags = (
        "span", "p", "h1", "h2", "h3", "h4", "h5", "h6",
        "section", "main", "header", "footer", "form", "label", "ul", "li",
    )
    script = """
from kivy.config import Config
Config.set("graphics", "window_state", "hidden")
from psx import psx
from psx.core.reconcile import Reconciler
from psx.renderers.kivy.kivy import KivyRenderer
from psx.sfle.engine import PythonLayoutEngine
from psx.sfle.model import AvailableSize, LayoutConstraints

tags = (
    "span", "p", "h1", "h2", "h3", "h4", "h5", "h6",
    "section", "main", "header", "footer", "form", "label", "ul", "li",
)
renderer = KivyRenderer(
    sfle_constraints=LayoutConstraints(
        AvailableSize(400, True), AvailableSize(120, True)),
    engine=PythonLayoutEngine(),
)
tree = Reconciler(renderer)
for tag in tags:
    content = "Action" if tag in ("li", "label") else (
        "<li>Action</li>" if tag == "ul" else "<button>Action</button>"
    )
    root = tree.render(psx(f"<{tag}>{content}</{tag}>"))
    child = root.children[0].handle.widget
    assert child.parent is root.handle.widget, tag
    assert round(root.handle.widget.width) == 400, tag
    assert 0 < child.width <= 400, tag
    assert round(child.x) == 0, tag
    assert round(child.y + child.height) == 120, tag
    if tag == "span":
        assert child.width < 400, tag
    elif tag not in ("label", "li"):
        assert round(child.width) == 400, tag
    else:
        # Native Kivy text measurement may consume the full viewport:
        # verify the committed rectangle rather than inventing a fixed glyph width.
        actual = dict(renderer.sfle_result.boxes)
        assert len(actual) >= 2, tag
        assert round(child.width) <= 400, tag
tree.unmount()
"""
    # Kivy may redirect sys.stdout and sys.stderr to its own Logger;
    # preserve native failure details through an unredirected diagnostic FD.
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        import pathlib
        diagnostic = pathlib.Path(tmpdir) / "semantic-flow-native.log"
        wrapped = (
            "import sys, traceback\n"
            "try:\n"
            + "".join("    " + line + "\n" for line in script.splitlines())
            + "except BaseException:\n"
            "    with open(sys.argv[1], 'w') as report:\n"
            "        traceback.print_exc(file=report)\n"
            "    raise\n"
        )
        env = dict(
            os.environ, KIVY_NO_FILELOG="1", KIVY_NO_ARGS="1",
            KIVY_WINDOW="sdl2", KIVY_TEXT="sdl2",
        )
        run = subprocess.run(
            [sys.executable, "-c", wrapped, str(diagnostic)], env=env,
            capture_output=True, text=True, timeout=90,
        )
        failure_details = diagnostic.read_text() if diagnostic.exists() else ""
    assert run.returncode == 0, (
        failure_details + run.stdout + "\\n" + run.stderr
    )
    for tag in tags:
        assert_feature(
            request, Feature(tag, "kivy", "interaction", "semantic_flow",
                             "native_geometry", applicability="partial_native"),
            run.returncode == 0,
        )


def test_semantic_form_submission_from_native_kivy_release(request):
    script = """
from kivy.config import Config
Config.set("graphics", "window_state", "hidden")
from psx.core.vnode import Button
from psx.core.reconcile import Reconciler
from psx.markup.html_aliases import _formatting_host
from psx.renderers.kivy.kivy import KivyRenderer
from psx.sfle.engine import PythonLayoutEngine
from psx.sfle.model import AvailableSize, LayoutConstraints

renderer = KivyRenderer(
    sfle_constraints=LayoutConstraints(
        AvailableSize(220, True), AvailableSize(120, True)),
    engine=PythonLayoutEngine(),
)
tree = Reconciler(renderer)
calls = []
def view(tag):
    return _formatting_host(
        "form", Button("Submit", key="submit"),
        on_submit=lambda: calls.append(tag),
    )
first = tree.render(view("first"))
native = first.children[0].handle.widget
native.dispatch("on_release")
updated = tree.render(view("second"))
native.dispatch("on_release")
assert updated.children[0].handle.widget is native
assert calls == ["first", "second"], calls
tree.unmount()
assert native.parent is None
"""
    env = dict(
        os.environ, KIVY_NO_FILELOG="1", KIVY_NO_ARGS="1",
        KIVY_WINDOW="sdl2", KIVY_TEXT="sdl2",
    )
    result = subprocess.run(
        [sys.executable, "-c", script], env=env,
        capture_output=True, text=True, timeout=90,
    )
    assert_feature(
        request, Feature("form", "kivy", "event", "on_submit",
                         "native_dispatch", applicability="partial_native"),
        result.returncode == 0, result.stdout + "\\n" + result.stderr,
    )
