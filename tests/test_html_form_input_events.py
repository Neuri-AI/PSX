"""HTML-like form attributes and semantic input events are portable."""
import pytest
from psx.markup.compile import psx
from psx.markup.html_aliases import InputChangeEvent


def test_form_input_names_types_values_and_submit():
    observed = []
    submitted = []
    auth = {"username": "", "password": ""}
    def change(event):
        assert isinstance(event, InputChangeEvent)
        auth[event.target.name] = event.target.value
        observed.append((event.type, event.target.name, event.target.value))
    def submit():
        submitted.append(dict(auth))
    tree = psx("""
        <form on_submit={submit}>
            <input type="text" name="username" value={auth.username} on_change={change}/>
            <input type="password" name="password" value={auth.password} on_change={change}/>
            <button type="submit">Login</button>
        </form>
    """, scope={"auth":auth, "change":change, "submit":submit})
    assert tree.type == "form"
    username, password, button = tree.children
    assert username.type == "Input" and username.props["password"] is False
    assert password.type == "Input" and password.props["password"] is True
    username.props["on_change"]("fredo")
    password.props["on_change"]("secret")
    assert auth == {"username":"fredo", "password":"secret"}
    assert observed == [("change", "username", "fredo"), ("change", "password", "secret")]
    button.props["on_click"]()
    assert submitted == [{"username":"fredo", "password":"secret"}]
    password.props["on_submit"]()
    assert len(submitted) == 2


def test_button_type_button_does_not_submit():
    submissions = []
    tree = psx('<form on_submit={submit}><button type="button">No</button><button type="submit">Yes</button></form>',
               scope={"submit":lambda: submissions.append("submit")})
    for button in tree.children:
        button.props["on_click"]()
    assert submissions == ["submit"]


@pytest.mark.parametrize("kind", ["email", "number", "checkbox"])
def test_unsupported_input_types_fail_explicitly(kind):
    with pytest.raises(ValueError, match="input type"):
        psx(f'<input type="{kind}" />')


def test_legacy_input_callback_remains_raw_string():
    from psx.core.vnode import Input
    values = []
    node = Input(on_change=values.append, password=True)
    node.props["on_change"]("foo")
    assert values == ["foo"]
