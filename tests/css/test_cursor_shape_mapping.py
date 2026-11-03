from psx.css.cursor import KIVY_CURSOR_SHAPES, QT_CURSOR_SHAPES, TK_CURSOR_SHAPES

def test_all_adapters_map_css_cursor_values():
    expected = {'default', 'none', 'context-menu', 'help', 'pointer', 'progress', 'wait'}
    assert set(KIVY_CURSOR_SHAPES) == expected
    assert set(QT_CURSOR_SHAPES) == expected
    assert set(TK_CURSOR_SHAPES) == expected
