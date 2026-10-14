"""Reviewed portable value classes; no toolkit execution is implied."""
from __future__ import annotations

ENUMS = {
    'wrap': ('nowrap', 'wrap', 'wrap-reverse'),
    'justify_content': ('flex-start', 'flex-end', 'center', 'space-between', 'space-around', 'space-evenly'),
    'align_items': ('stretch', 'flex-start', 'flex-end', 'center', 'baseline'),
    'align_content': ('normal', 'stretch', 'flex-start', 'flex-end', 'center', 'space-between', 'space-around', 'space-evenly'),
    'align_self': ('auto', 'stretch', 'flex-start', 'flex-end', 'center', 'baseline'),
    'align': ('left', 'center', 'right'),
    'orientation': ('horizontal', 'vertical'), 'fit': ('contain', 'cover', 'fill', 'none'),
    'scrollbar': ('auto', 'always', 'hidden'), 'variant': ('neutral', 'success', 'warning', 'danger', 'info'),
    'appearance': ('filled', 'outline'), 'size': ('small', 'medium', 'large'), 'shape': ('rounded', 'pill'),
}


def value_classes(component: str, name: str) -> tuple[tuple[object, ...], tuple[object, ...]]:
    """Return positive classes and rejection classes, independently of defaults."""
    if name.startswith('on_'):
        return (None, lambda *args: args, print), (False, 1, 'callback')
    if name == 'direction':
        return (('row', 'row-reverse', 'column', 'column-reverse') if component == 'Flex' else ('vertical', 'horizontal', 'both')), ('diagonal', None, True)
    if name == 'content_direction':
        return ('vertical', 'horizontal'), ('both', None, True)
    if name in ENUMS:
        return ENUMS[name], ('unsupported', None, 1)
    if name in ('enabled', 'checked', 'bold', 'italic', 'read_only', 'password', 'underline', 'indeterminate'):
        return (False, True), (0, 1, 'true', None)
    if name == 'color':
        valid = ('#000000', '#FFFFFF', '#aBc123')
        if component != 'Switch':
            valid = (None, *valid)
        return valid, ('red', '#fff', '#12345g', 0)
    if name == 'href':
        return (None, 'http://example.com', 'https://example.com/path?q=x'), ('', 'relative', 'ftp://example.com', 'https://', 1)
    if name == 'options':
        return ((), ['a', 'b'], ({'label': 'Zero', 'value': 0}, {'label': 'One', 'value': 'one'})), (None, 'a', ['a', 'a'], [{'label': 'a', 'value': True}], [{'label': 'a'}])
    if name == 'source':
        return ('a.png', '/missing/path/image.png'), ('', None, 1)
    if name in ('label', 'value', 'alt', 'placeholder'):
        if name in ('value', 'label') and component in ('Text', 'Button'):
            return ('', 'Unicode ñ\nline', 0, -1.5), (True, None, [])
        if name == 'value' and component in ('Radio', 'RadioGroup', 'Select'):
            return (('', -1, 0) if component == 'Radio' else (None, '', -1, 0)), (True, 1.5, [])
        if name != 'value' or component in ('Input', 'TextArea'):
            return ('', 'Unicode ñ\nline'), (None, 0, True)
    if name == 'font_size':
        return (0.5, 1, 48), (0, -1, True, '16', float('nan'), float('inf'))
    if name == 'decimals':
        return (0, 1, 9), (-1, 10, 1.5, True)
    if name in ('flex_grow', 'flex_shrink'):
        return (0, 0.5, 100), (-1, True, float('nan'), float('inf'))
    if name == 'order':
        return (-(1 << 31), 0, (1 << 31) - 1), (-(1 << 31) - 1, 1 << 31, True, 1.5)
    if name in ('spacing', 'thickness'):
        return ((0, 1, 100) if name == 'spacing' else (1, 2, 100)), ((-1, True, 1.5) if name == 'spacing' else (0, -1, True, 1.5))
    if name == 'padding':
        if component == 'Flex':
            return (0, '10%', (1, '2px'), [0, 1, 2, 3]), (-1, True, (1, 2, 3), 'auto')
        return (0, (1, 2), [0, 1, 2, 3]), (-1, True, (1, 2, 3), (1, -1))
    if name.startswith('layout_') or name == 'flex_basis' or (component == 'Flex' and name in ('width', 'height', 'min_width', 'min_height', 'max_width', 'max_height', 'gap', 'row_gap', 'column_gap')):
        if 'border_' in name:
            return (0, '2px', 1.5), (-1, '1%', 'auto', True)
        if 'margin_' in name:
            return (-1, '0px', '10%', 'auto'), ('none', 'min-content', True, float('inf'))
        if 'padding_' in name or name in ('gap', 'row_gap', 'column_gap'):
            return (0, '2px', '10%'), (-1, 'auto', True, float('inf'))
        maximum = name in ('max_width', 'max_height', 'layout_max_width', 'layout_max_height')
        return (0, '2px', '10%', 'min-content', 'max-content', 'none' if maximum else 'auto'), (-1, 'auto' if maximum else 'none', True, float('inf'))
    if name in ('width', 'height'):
        return ((None, 1, 100) if component == 'Image' else (None, 0.5, 100)), (0, -1, True, '100', float('inf'))
    if name in ('value', 'min', 'max', 'step'):
        if name == 'min':
            return (-100, 0, 1), (True, '0', float('nan'), float('inf'))
        if name == 'max':
            return (100, 101, 1000), (True, '100', float('nan'), float('-inf'))
        if name == 'step':
            return ((1, 2, 100) if component == 'SpinBox' else (0, 0.5, 2)), ((0, -1, True, float('nan'), float('inf')) if component == 'SpinBox' else (-1, True, float('nan'), float('inf')))
        return (-1, 0, 100, 101), (True, '0', float('nan'), float('inf'))
    raise AssertionError(f'Unreviewed property {component}.{name}')
