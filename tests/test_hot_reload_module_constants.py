from psx.devtools.qyro_reload import _render_class_source


def test_reload_preserves_initial_state_constants():
    source = """
INITIAL_STATE = {"name": "", "email": ""}
user_slice = create_slice(name="user", initial_state=INITIAL_STATE, reducers={})
store = configure_store({"user": user_slice}, devtools=False)
class MyApp:
    def render(self):
        return INITIAL_STATE["name"]
"""
    result = _render_class_source(source, "MyApp", frozenset())
    assert "INITIAL_STATE =" in result
    assert "initial_state=INITIAL_STATE" in result


def test_reload_preserves_transitive_and_annotated_constants():
    source = """
DEFAULT_NAME: str = "fredo"
INITIAL_STATE = {"name": DEFAULT_NAME}
user_slice = create_slice(name="user", initial_state=INITIAL_STATE, reducers={})
class MyApp:
    def render(self):
        return INITIAL_STATE
"""
    result = _render_class_source(source, "MyApp", frozenset())
    assert "DEFAULT_NAME: str" in result
    assert "INITIAL_STATE =" in result


def test_reload_does_not_evaluate_unrelated_module_side_effects():
    source = """
INITIAL_STATE = {"name": ""}
unrelated = dangerous_side_effect()
user_slice = create_slice(name="user", initial_state=INITIAL_STATE, reducers={})
class MyApp:
    def render(self):
        return INITIAL_STATE
"""
    result = _render_class_source(source, "MyApp", frozenset())
    assert "dangerous_side_effect" not in result
