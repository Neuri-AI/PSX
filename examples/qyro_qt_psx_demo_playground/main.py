import sys
from PySide6.QtWidgets import QMainWindow
from qyro import ApplicationContext
from psx import psx
from psx.integrations.qyro import PSXComponent
from psx.integrations.pydux import use_dispatch, use_selector
from pydux import configure_store, create_slice

auth_slice = create_slice(
    name="auth",
    initial_state={"email": "", "password": "", "accepted": False},
    reducers={
        "set_email": lambda state, action: state.update(email=action.payload),
        "set_password": lambda state, action: state.update(password=action.payload),
        "set_accepted": lambda state, action: state.update(accepted=action.payload),
        "reset": lambda state, action: state.update(email="", password="", accepted=False),
    },
)

store = configure_store(
    {
        "auth": auth_slice,
    },
    devtools=True,
)

class QyroQtPsxDemo(QMainWindow, PSXComponent, ApplicationContext):

    def component_will_mount(self):
        self.setMinimumSize(640, 480)

    def render(self):
        email = use_selector(lambda state: state["auth"]["email"])
        password = use_selector(lambda state: state["auth"]["password"])
        accepted = use_selector(lambda state: state["auth"]["accepted"])
        dispatch = use_dispatch()

        def on_email_change(value):
            dispatch(auth_slice.actions.set_email(value))

        def on_password_change(value):
            dispatch(auth_slice.actions.set_password(value))

        def on_accept_change(value):
            dispatch(auth_slice.actions.set_accepted(value))

        def cancel():
            dispatch(auth_slice.actions.reset())

        def save():
            if not email or not password or not accepted:
                print("Complete all fields and accept the terms")
                return
            print("Account data validated")

        def on_note_change(value):
            print(f"Nuevo texto: {value}")

        return psx("""
            <Column spacing={12} padding={30}>
              <Text value="Crear cuenta" font_size={20} bold={True} />
              <Column spacing={12}>
                <Input value={email} placeholder="Email" on_change={on_email_change} />
                <Input value={password} placeholder="Password" on_change={on_password_change} password={True} />
              </Column>
              <Row spacing={0}>
                <Checkbox checked={accepted} on_change={on_accept_change} />
                <Text value="Acepto los términos y condiciones" />
              </Row>
              <Row spacing={8}>
                <Button label="Cancelar" on_click={cancel} />
                <Button label="Guardar" on_click={save} />
              </Row>

                <Row spacing={12}>
                  <TextArea
                    value=""
                    placeholder="Escribe tu nota aquí..."
                    font_size={14}
                    on_change={on_note_change}
                  />
                </Row>

            </Column>
        """)


if __name__ == "__main__":
    window = QyroQtPsxDemo()
    window.show()
    sys.exit(window.run())
