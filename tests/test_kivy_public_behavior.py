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
