from psx.devtools.qyro_reload import _render_class_source


def test_reload_captures_pydux_slice_definitions():
    src = '''
from velto.state import create_slice, configure_store
user_slice = create_slice(name="user", initial_state={"name": "fredo"}, reducers={})
store = configure_store({"user": user_slice}, devtools=True)
class Window:
    def render(self):
        return None
'''
    result = _render_class_source(src, "Window", frozenset())
    assert "create_slice" in result
    assert "inspector_auto_start=False" in result
