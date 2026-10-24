"""Live Qt evidence for native-clickable HTML control labels."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from psx.core.reconcile import Reconciler
from psx.markup.compile import psx
from psx.renderers.qt.pyside import PySide6Renderer


def test_html_radio_labels_are_native_click_targets():
    renderer = PySide6Renderer(argv=["psx-html-radio-native"])
    reconciler = Reconciler(renderer)
    changes = []
    try:
        root = psx("""
        <div>
            <div><input type="radio" id="email" name="contact" value="email" checked on_change={changed}/>
                 <label for="email">Email</label></div>
            <div><input type="radio" id="phone" name="contact" value="phone" on_change={changed}/>
                 <label for="phone">Phone</label></div>
        </div>""", scope={"changed":changes.append})
        mounted = reconciler.render(root)
        group = mounted.children[0]
        email = group.children[0].handle.widget
        phone = group.children[1].handle.widget
        assert email.text() == "Email"
        assert phone.text() == "Phone"
        assert email.isChecked()
        phone.click()
        assert phone.isChecked()
        assert not email.isChecked()
        assert changes and changes[-1].target.value == "phone"
        assert changes[-1].target.name == "contact"
    finally:
        reconciler.unmount()


def test_html_checkbox_associated_label_clicks_native_toggle():
    renderer = PySide6Renderer(argv=["psx-html-checkbox-native"])
    reconciler = Reconciler(renderer)
    try:
        root = psx('<div><input type="checkbox" id="agree" checked/>'
                   '<label for="agree">Agree</label></div>')
        mounted = reconciler.render(root)
        checkbox = mounted.children[0].handle.widget
        assert checkbox.text() == "Agree"
        assert checkbox.isChecked()
        checkbox.click()
        assert not checkbox.isChecked()
    finally:
        reconciler.unmount()
