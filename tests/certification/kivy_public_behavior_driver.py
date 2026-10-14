"""Isolated SDL2 native readback and event driver; no synthetic pass receipts."""
from __future__ import annotations

import json
import sys
import time
import struct
import zlib

from kivy.config import Config
Config.set('graphics', 'window_state', 'hidden')
from kivy.clock import Clock
import psx
from psx.core.reconcile import Reconciler
from psx.renderers.kivy.kivy import KivyRenderer
from psx.sfle.engine import PythonLayoutEngine
from psx.sfle.model import AvailableSize, LayoutConstraints


def renderer():
    return KivyRenderer(sfle_constraints=LayoutConstraints(
        AvailableSize(640, True), AvailableSize(180, True)), engine=PythonLayoutEngine())


def tick():
    # Flush native texture/layout/animation callbacks, including Switch's 160ms transition.
    for _ in range(24):
        Clock.tick()
        time.sleep(.01)


def leaf(component, props):
    children = ()
    if component == 'Box':
        from psx.core.vnode import Box
        return Box(psx.Text(props['child_value']), key='control')
    if component in ('Scroll', 'Flex'):
        children = (psx.Flex(psx.Text('Content'), width='600px', height='300px'),) if component == 'Scroll' else (psx.Text('Content'),)
    if component == 'Radio': props = dict(value='a', **props)
    if component == 'RadioGroup':
        children = (psx.Radio(value='a', label='Alpha', key='a'),
                    psx.Radio(value='b', label='Beta', key='b'))
    return getattr(psx, component)(*children, key='control',
        layout_width='300px', layout_height='90px', flex_shrink=0, **props)


def view(component, props):
    return psx.Flex(leaf(component, props), width='640px', height='180px',
                    align_items='flex-start')


def rgba(color):
    return tuple(int(color[i:i+2], 16) / 255 for i in (1, 3, 5)) + (1.,)


def write_rgba_png(path, width, height, color):
    """Create a deterministic PNG fixture without a test-only Pillow dependency."""
    red, green, blue = (int(color[index:index + 2], 16) for index in (1, 3, 5))
    row = bytes((red, green, blue, 255)) * width
    raw = b"".join(b"\x00" + row for _ in range(height))
    def chunk(kind, payload):
        return (struct.pack(">I", len(payload)) + kind + payload +
                struct.pack(">I", zlib.crc32(kind + payload) & 0xffffffff))
    data = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)) +
            chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))
    path.write_bytes(data)


# Assertions below inspect toolkit properties, composed native controls or actual
# drawing instructions. Stored PSX props are never used as native readback.
CASES = {
    'Badge': ({'label': 'Before', 'enabled': True, 'size': 'small'}, {'label': 'After', 'enabled': False, 'size': 'large'}),
    'Text': ({'value': 'Before', 'font_size': 14, 'bold': False, 'italic': False,
              'align': 'left', 'color': '#102030', 'enabled': True},
             {'value': 'After', 'font_size': 23, 'bold': True, 'italic': True,
              'align': 'right', 'color': '#304050', 'enabled': False}),
    'Button': ({'label': 'Before', 'font_size': 14, 'enabled': True},
               {'label': 'After', 'font_size': 23, 'enabled': False}),
    'Input': ({'value': 'Before', 'placeholder': 'Hint', 'font_size': 14,
              'read_only': False, 'password': False, 'enabled': True},
             {'value': 'After', 'placeholder': 'New hint', 'font_size': 23,
              'read_only': True, 'password': True, 'enabled': False}),
    'TextArea': ({'value': 'Before\nline', 'placeholder': 'Hint', 'font_size': 14,
                 'read_only': False, 'enabled': True},
                {'value': 'After\nline', 'placeholder': 'New hint', 'font_size': 23,
                 'read_only': True, 'enabled': False}),
    'Checkbox': ({'checked': False, 'enabled': True}, {'checked': True, 'enabled': False}),
    'Slider': ({'value': 25, 'min': 0, 'max': 100, 'step': 1,
                'orientation': 'horizontal', 'enabled': True},
               {'value': 45, 'min': 20, 'max': 80, 'step': 5,
                'orientation': 'vertical', 'enabled': False}),
    'Select': ({'options': [{'label': 'Alpha', 'value': 1}, {'label': 'Beta', 'value': 2}],
                'value': 1, 'placeholder': 'Pick', 'enabled': True},
               {'options': [{'label': 'Gamma', 'value': 3}, {'label': 'Delta', 'value': 4}],
                'value': 4, 'placeholder': 'Choose', 'enabled': False}),
    'ProgressBar': ({'value': 25, 'min': 0, 'max': 100, 'enabled': True, 'indeterminate': False},
                    {'value': 45, 'min': 20, 'max': 80, 'enabled': False, 'indeterminate': True}),
    'Radio': ({'label': 'Alpha', 'enabled': True}, {'label': 'Beta', 'enabled': False}),
    'RadioGroup': ({'value': 'a', 'enabled': True}, {'value': 'b', 'enabled': False}),
    'Switch': ({'checked': False, 'label': 'Before', 'size': 'small',
                'color': '#102030', 'enabled': True},
               {'checked': True, 'label': 'After', 'size': 'large',
                'color': '#304050', 'enabled': False}),
    'SpinBox': ({'value': 2, 'min': 0, 'max': 10, 'step': 1, 'decimals': 0, 'enabled': True},
                {'value': 4.5, 'min': 1, 'max': 8, 'step': .5, 'decimals': 1, 'enabled': False}),
    'Divider': ({'orientation': 'horizontal', 'thickness': 1, 'color': '#102030'},
                {'orientation': 'vertical', 'thickness': 3, 'color': '#304050'}),
    'Link': ({'label': 'Before', 'underline': False, 'color': '#102030', 'enabled': True},
             {'label': 'After', 'underline': True, 'color': '#304050', 'enabled': False}),
}


def readback(component, widget, props, name):
    value = props[name]
    if name == 'enabled':
        assert widget.disabled == (not value)
    elif component == 'Badge':
        if name == 'label': assert widget.text == value
        else: assert widget.font_size == {'small': 22, 'medium': 24, 'large': 28}[value]
    elif component == 'Text':
        native = {'value': 'text', 'align': 'halign'}.get(name, name)
        observed = getattr(widget, native)
        assert tuple(observed) == rgba(value) if name == 'color' else observed == value
    elif component in ('Input', 'TextArea', 'Button'):
        native = {'value': 'text', 'label': 'text', 'placeholder': 'hint_text',
                  'read_only': 'readonly'}.get(name, name)
        assert getattr(widget, native) == value
    elif component == 'Checkbox':
        assert widget.active == value
    elif component == 'Slider':
        assert getattr(widget, name) == value
    elif component == 'Select':
        if name == 'options':
            assert tuple(widget.values) == tuple(item['label'] for item in value)
        elif name == 'value':
            assert widget.text == next(item['label'] for item in props['options'] if item['value'] == value)
        else:
            # An unset selection must display the hint in the real Spinner.
            assert widget.text == value
    elif component == 'ProgressBar':
        if name == 'indeterminate':
            assert (widget._psx_indeterminate_anim is not None) == value
        elif name == 'max':
            assert widget.max == props['max'] - props['min']
        elif name == 'min':
            assert widget.max == props['max'] - value
        else:
            assert widget.value == props['value'] - props['min']
    elif component == 'Radio':
        assert widget._psx_label.text == value
    elif component == 'RadioGroup':
        assert {key: cb.active for key, cb in widget._psx_radios.items()} == {'a': value == 'a', 'b': value == 'b'}
    elif component == 'Switch':
        from psx.renderers.components.switch import SWITCH_SIZES
        if name == 'label': assert widget._psx_label.text == value
        elif name == 'checked': assert abs(widget._psx_control.progress - float(value)) < .001
        elif name == 'size': assert tuple(widget._psx_control.size) == tuple(v * 2 for v in SWITCH_SIZES[value])
        else: assert widget._psx_control.active_color == value
    elif component == 'SpinBox':
        if name in ('value', 'decimals'): assert widget._psx_parts[1].text == f"{props['value']:.{props['decimals']}f}"
        else: raise ValueError('SpinBox bound/step need behavioral rather than stored-prop readback')
    elif component == 'Divider':
        if name == 'thickness': assert widget._psx_line_before.width == value
        elif name == 'color': assert tuple(widget._psx_color_instruction.rgba) == rgba(value)
        else:
            points = widget._psx_line_before.points
            assert points[0] == points[2] if value == 'vertical' else points[1] == points[3]
    elif component == 'Link':
        if name == 'color': assert tuple(widget.color) == rgba(value)
        else:
            text = props['label']
            assert widget.text == (f'[u]{text}[/u]' if props['underline'] else text)


def properties(component):
    initial, updated = CASES[component]
    tree = Reconciler(renderer())
    mounted = tree.render(view(component, initial))
    widget = mounted.children[0].handle.widget
    tick()
    verified = []
    names = list(initial)
    if component == 'ProgressBar': names.remove('value') # value verified in determinate update below
    if component == 'Select': names.remove('placeholder') # verified with unset selection below
    if component == 'SpinBox': names = ['value', 'decimals', 'enabled']
    for name in names: readback(component, widget, initial, name)
    second = tree.render(view(component, updated))
    assert second.children[0].handle.widget is widget
    tick()
    for name in names:
        readback(component, widget, updated, name)
        verified.extend((['property', name, 'live_update'], ['property', name, 'native_readback']))
    if component == 'ProgressBar':
        props = dict(updated, indeterminate=False)
        tree.render(view(component, props))
        readback(component, widget, props, 'value')
        verified.extend((['property', 'value', 'live_update'], ['property', 'value', 'native_readback']))
    if component == 'Select':
        for props in (dict(initial, value=None), dict(updated, value=None)):
            tree.render(view(component, props))
            readback(component, widget, props, 'placeholder')
        verified.extend((['property', 'placeholder', 'live_update'], ['property', 'placeholder', 'native_readback']))
    tree.unmount()
    assert widget.parent is None
    return verified


EVENTS = [('Button', 'on_click'), ('Checkbox', 'on_change'), ('Input', 'on_change'),
          ('Input', 'on_submit'), ('TextArea', 'on_change'), ('Slider', 'on_change'),
          ('Select', 'on_change'), ('Switch', 'on_change'), ('SpinBox', 'on_change'),
          ('RadioGroup', 'on_change')]


def events(component, event):
    props = {'Select': {'options': [{'label': 'Alpha', 'value': 1}, {'label': 'Beta', 'value': 2}], 'value': 1},
             'Button': {'label': 'Push'}, 'Input': {'value': ''}, 'TextArea': {'value': ''},
             'RadioGroup': {'value': 'a'}, 'SpinBox': {'value': 2},
             'Slider': {'value': 20}}.get(component, {})
    calls, rebound = [], []
    tree = Reconciler(renderer())
    node = tree.render(view(component, dict(props, **{event: lambda *args: calls.append(args)})))
    widget = node.children[0].handle.widget
    tick()
    def dispatch():
        if component in ('Button', 'Link'): widget.dispatch('on_release'); return ()
        if component == 'Checkbox': widget.active = not widget.active; return (widget.active,)
        if component in ('Input', 'TextArea'):
            if event == 'on_submit': widget.dispatch('on_text_validate'); return ()
            widget.text += 'edit'; return (widget.text,)
        if component == 'Slider': widget.value += 5; return (widget.value,)
        if component == 'Select': widget.text = 'Beta' if widget.text != 'Beta' else 'Alpha'; return (2 if widget.text == 'Beta' else 1,)
        if component == 'Switch': widget._psx_control.dispatch('on_release'); return (True,)
        if component == 'SpinBox': widget._psx_parts[2].dispatch('on_release'); return (3.,)
        if component == 'RadioGroup':
            target = 'b' if widget._psx_radios['a'].active else 'a'
            widget._psx_radios[target].active = True
            return (target,)
    expected = dispatch()
    assert calls == [expected], (component, calls, expected)
    verified = [['event', event, 'native_dispatch'], ['event', event, 'payload']]
    node = tree.render(view(component, dict(props, **{event: lambda *args: rebound.append(args)})))
    assert node.children[0].handle.widget is widget
    baseline = len(calls)
    expected = dispatch()
    assert len(calls) == baseline and rebound == [expected], (component, calls, rebound)
    verified.append(['event', event, 'rebind'])
    tree.unmount()
    baseline = (len(calls), len(rebound))
    dispatch()
    assert (len(calls), len(rebound)) == baseline, (component, calls, rebound)
    verified.append(['event', event, 'teardown'])
    return verified




def disabled(component, event):
    from kivy.tests.common import UnitTestTouch
    from kivy.core.window import Window
    props = {'Button': {'label': 'Push'}, 'Select': {'options': ['Alpha', 'Beta'], 'value': 'Alpha'},
             'RadioGroup': {'value': 'a'}, 'SpinBox': {'value': 2}, 'Slider': {'value': 20}}.get(component, {})
    calls = []
    tree = Reconciler(renderer())
    node = tree.render(view(component, dict(props, enabled=False,
        **{event: lambda *args: calls.append(args)})))
    root, widget = node.handle.widget, node.children[0].handle.widget
    Window.add_widget(root)
    tick()
    target = {'Switch': lambda: widget._psx_control,
              'SpinBox': lambda: widget._psx_parts[2],
              'RadioGroup': lambda: widget._psx_radios['b']}.get(component, lambda: widget)()
    assert widget.disabled and target.disabled
    before = (getattr(target, 'active', None), getattr(target, 'value', None), getattr(target, 'state', None))
    touch = UnitTestTouch(*target.to_window(*target.center))
    touch.touch_down()
    touch.touch_up()
    tick()
    after = (getattr(target, 'active', None), getattr(target, 'value', None), getattr(target, 'state', None))
    assert calls == [] and before == after, (component, calls, before, after)
    if component == 'Select': assert not widget.is_open
    tree.unmount()
    Window.remove_widget(root)
    return [['event', event, 'disabled'], ['interaction',
            'enabled__' + event, 'paired_native']] if component != 'RadioGroup' and component != 'SpinBox' else [['event', event, 'disabled']]


def lifecycle(component):
    from dataclasses import replace
    if component == 'Image':
        from tempfile import TemporaryDirectory
        temporary = TemporaryDirectory()
        from pathlib import Path
        path = Path(temporary.name) / 'native.png'
        write_rgba_png(path, 8, 4, '#ff0000')
        path = str(path)
        initial, updated = {'source': path, 'fit': 'contain'}, {'source': path, 'fit': 'cover'}
    else:
        initial, updated = {
            'Spacer': ({}, {}),
            'Box': ({'child_value': 'Before'}, {'child_value': 'After'}),
            'Flex': ({'direction': 'row'}, {'direction': 'column'}),
            'Scroll': ({'direction': 'vertical', 'enabled': True}, {'direction': 'horizontal', 'enabled': False}),
        }.get(component, CASES.get(component))
    if component == 'ProgressBar': updated = dict(updated, indeterminate=False)
    tree = Reconciler(renderer())
    def pair(props, reverse=False):
        children = [replace(leaf(component, props), key=key) for key in ('left', 'right')]
        if reverse: children.reverse()
        return psx.Flex(*children, width='640px', height='180px')
    node = tree.render(pair(initial))
    parent = node.handle.widget
    widgets = [child.handle.widget for child in node.children]
    assert len(parent.children) == 2 and all(widget.parent is parent for widget in widgets)
    result = [['lifecycle', 'mount', 'native_behavior']]
    node = tree.render(pair(updated))
    assert [child.handle.widget for child in node.children] == widgets
    assert all(widget.parent is parent for widget in widgets)
    result.append(['lifecycle', 'update', 'native_behavior'])
    node = tree.render(pair(updated, reverse=True))
    assert [child.handle.widget for child in node.children] == widgets[::-1]
    assert [child.node.key for child in node.children] == ['right', 'left']
    assert all(widget.parent is parent for widget in widgets)
    # Native Kivy insertion order is reversed relative to declarative order.
    assert parent.children == widgets
    result.append(['lifecycle', 'reorder', 'native_behavior'])
    tree.unmount()
    assert parent.children == [] and all(widget.parent is None for widget in widgets)
    result.append(['lifecycle', 'unmount', 'native_behavior'])
    return result



def interactions(component):
    calls = []
    tree = Reconciler(renderer())
    if component == 'Input':
        def render(**props):
            widget = tree.render(view('Input', dict(value='', on_change=calls.append, **props))).children[0].handle.widget
            tick()
            return widget
        widget = render(read_only=True)
        widget.insert_text('blocked')
        assert widget.text == '' and calls == []
        widget = render(read_only=False)
        widget.insert_text('edited')
        assert widget.text == 'edited' and calls == ['edited'], (widget.text, calls)
        verified = [['interaction', 'read_only__on_change', 'paired_native']]
        calls.clear()
        widget = render(password=True)
        widget.insert_text('secret')
        assert widget.password and widget.text == 'secret' and calls == ['secret']
        verified.append(['interaction', 'password__value', 'paired_native'])
        widget = render(placeholder='Hint')
        assert widget.hint_text == 'Hint' and widget.text == ''
        widget.insert_text('content')
        assert widget.hint_text == 'Hint' and widget.text == 'content'
        verified.append(['interaction', 'placeholder__value', 'paired_native'])
    elif component == 'Slider':
        widget = tree.render(view('Slider', {'min': 20, 'max': 80, 'value': 100, 'step': 5})).children[0].handle.widget
        assert widget.value == 80 and widget.min == 20 and widget.max == 80
        widget = tree.render(view('Slider', {'min': 30, 'max': 60, 'value': 10, 'step': 5})).children[0].handle.widget
        assert widget.value == 30 and widget.min == 30 and widget.max == 60
        verified = [['interaction', 'min__max', 'paired_native']]
        widget = tree.render(view('Slider', {'min': 0, 'max': 100, 'value': 10, 'step': 5})).children[0].handle.widget
        widget.value_normalized = .23
        assert widget.value == 25, widget.value
        verified.append(['interaction', 'value__step', 'paired_native'])
    elif component == 'SpinBox':
        def render(**props):
            return tree.render(view('SpinBox', dict(on_change=calls.append, **props))).children[0].handle.widget
        widget = render(value=-2, min=1, max=8, step=.5, decimals=1)
        assert widget._psx_parts[1].text == '1.0' and widget._psx_parts[0].disabled
        widget = render(value=10, min=1, max=8, step=.5, decimals=1)
        assert widget._psx_parts[1].text == '8.0' and widget._psx_parts[2].disabled
        verified = [['interaction', 'value__min', 'paired_native'], ['interaction', 'value__max', 'paired_native']]
        for name in ('min', 'max'):
            verified.extend((['property', name, 'live_update'], ['property', name, 'native_readback']))
        widget = render(value=4.5, min=1, max=8, step=.5, decimals=1)
        widget._psx_parts[2].dispatch('on_release')
        assert calls == [5.0]
        widget = render(value=4.5, min=1, max=8, step=.25, decimals=2)
        widget._psx_parts[2].dispatch('on_release')
        assert calls == [5.0, 4.75]
        assert widget._psx_parts[1].text == '4.50'
        verified.extend((['property', 'step', 'live_update'], ['property', 'step', 'native_readback'],
                         ['interaction', 'step__decimals', 'paired_native']))
    elif component == 'Select':
        widget = tree.render(view('Select', {'options': [{'label': 'Alpha', 'value': 1}], 'value': 1})).children[0].handle.widget
        assert widget.text == 'Alpha'
        widget = tree.render(view('Select', {'options': [{'label': 'Beta', 'value': 2}], 'value': 1, 'placeholder': 'Choose'})).children[0].handle.widget
        assert widget.text == 'Choose' and tuple(widget.values) == ('Beta',)
        widget = tree.render(view('Select', {'options': [{'label': 'Beta', 'value': 2}], 'value': 2})).children[0].handle.widget
        assert widget.text == 'Beta'
        verified = [['interaction', 'options__value', 'paired_native']]
    else: raise ValueError(component)
    tree.unmount()
    return verified



def decoration(component):
    tree = Reconciler(renderer())
    if component == 'Image':
        from tempfile import TemporaryDirectory
        from pathlib import Path
        temporary = TemporaryDirectory()
        paths = [Path(temporary.name) / 'first.png', Path(temporary.name) / 'second.png']
        for path, size, color in zip(paths, [(8, 4), (16, 12)], ['#ff0000', '#0000ff']):
            write_rgba_png(path, *size, color)
        paths = [str(path) for path in paths]
        widget = tree.render(view('Image', {'source': paths[0], 'fit': 'contain', 'enabled': True})).children[0].handle.widget
        tick()
        assert widget.source == paths[0] and tuple(widget.texture.size) == (8, 4)
        assert widget.fit_mode == 'contain' and not widget.disabled
        updated = tree.render(view('Image', {'source': paths[1], 'fit': 'cover', 'enabled': False}))
        assert updated.children[0].handle.widget is widget
        tick()
        assert widget.source == paths[1] and tuple(widget.texture.size) == (16, 12)
        assert widget.fit_mode == 'cover' and widget.disabled
        names = ('source', 'fit', 'enabled')
    elif component == 'Badge':
        from kivy.graphics import RoundedRectangle, Line, Color
        def render(**props):
            widget = tree.render(view('Badge', dict(label='Badge', **props))).children[0].handle.widget
            tick()
            return widget
        widget = render(variant='success')
        colors = [i.rgba for i in widget.canvas.before.children if isinstance(i, Color)]
        assert tuple(colors[0]) == rgba('#15803D')
        widget = render(variant='danger')
        colors = [i.rgba for i in widget.canvas.before.children if isinstance(i, Color)]
        assert tuple(colors[0]) == rgba('#B91C1C')
        widget = render(appearance='filled')
        assert any(isinstance(i, RoundedRectangle) for i in widget.canvas.before.children)
        assert not any(isinstance(i, Line) for i in widget.canvas.before.children)
        widget = render(appearance='outline')
        assert any(isinstance(i, Line) for i in widget.canvas.before.children)
        assert not any(isinstance(i, RoundedRectangle) for i in widget.canvas.before.children)
        widget = render(shape='rounded')
        rect = next(i for i in widget.canvas.before.children if isinstance(i, RoundedRectangle))
        assert all(radius == (10, 10) for radius in rect.radius)
        widget = render(shape='pill')
        rect = next(i for i in widget.canvas.before.children if isinstance(i, RoundedRectangle))
        assert all(radius == (rect.size[1]/2, rect.size[1]/2) for radius in rect.radius)
        names = ('variant', 'appearance', 'shape')
    else: raise ValueError(component)
    tree.unmount()
    return [['property', name, scenario] for name in names for scenario in ('live_update', 'native_readback')]



def radio_value():
    calls = []
    tree = Reconciler(renderer())
    def group(value):
        return psx.Flex(psx.RadioGroup(psx.Radio(value, label='Alpha', key='a'),
            psx.Radio('b', label='Beta', key='b'), value=value, key='group',
            on_change=calls.append), width='640px', height='180px')
    root = tree.render(group('a'))
    widget = root.children[0].handle.widget
    checkbox = root.children[0].children[0].handle.widget._psx_checkbox
    assert widget._psx_radios['a'] is checkbox and checkbox.active
    root = tree.render(group('c'))
    assert root.children[0].children[0].handle.widget._psx_checkbox is checkbox
    assert 'a' not in widget._psx_radios and widget._psx_radios['c'] is checkbox
    assert checkbox.active and not widget._psx_radios['b'].active
    assert calls == [] # controlled update must not emit an edit
    widget._psx_radios['b'].active = True
    checkbox.active = True
    assert calls == ['b', 'c'], calls
    tree.unmount()
    return [['property', 'value', 'live_update'], ['property', 'value', 'native_readback']]

def grid_unsupported_mount(component):
    """Verify the native Kivy renderer rejects Grid before any widget allocation."""
    from psx.core.errors import RendererCapabilityError
    from kivy.uix.widget import Widget

    native = renderer()
    node = (psx.Grid(psx.GridItem(psx.Text('content')))
            if component == 'Grid' else psx.GridItem(psx.Text('content')))
    created = []
    original_init = Widget.__init__

    def traced_init(widget, *args, **kwargs):
        created.append(widget)
        return original_init(widget, *args, **kwargs)

    Widget.__init__ = traced_init
    try:
        try:
            native.create(node, None)
        except RendererCapabilityError as exc:
            assert 'Grid' in str(exc) and 'SFLE' in str(exc), str(exc)
        else:
            raise AssertionError(f'{component} mounted without Grid geometry support')
    finally:
        Widget.__init__ = original_init
        native.close()
    assert not created, f'{component} created {len(created)} native Kivy widgets before rejection'
    return [['interaction', 'unsupported_mount', 'kivy_fail_closed']]


if __name__ == '__main__':
    mode, component, *rest = sys.argv[1:]
    verified = (grid_unsupported_mount(component) if mode == 'grid_unsupported_mount' else
                properties(component) if mode == 'property' else
                lifecycle(component) if mode == 'lifecycle' else
                interactions(component) if mode == 'interaction' else
                decoration(component) if mode == 'decoration' else
                radio_value() if mode == 'radio_value' else
                disabled(component, rest[0]) if mode == 'disabled' else
                events(component, rest[0]))
    print('PSX_NATIVE_VERIFIED=' + json.dumps(verified))
