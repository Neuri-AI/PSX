# Tutorial: añadir un widget portable a PSX

Esta guía muestra cómo añadir un widget nuevo al **markup oficial de PSX**.
El objetivo no es que las personas que usan PSX escriban `Native(...)`, ni que
conozcan Qt, Tkinter o Kivy. Tras completar el trabajo, la API pública será una
sola:

```python
return psx("""
    <Column padding={24} spacing={12}>
        <Text>Name</Text>
        <TextField
            value={name}
            placeholder="Your name"
            enabled={can_edit}
            on_change={set_name}
            on_submit={save}
        />
    </Column>
""")
```

Internamente, PSX montará un control real para el renderer activo:

| PSX | Qt | Tkinter | Kivy |
| --- | --- | --- | --- |
| `TextField` | `QLineEdit` | `ttk.Entry` | `TextInput(multiline=False)` |
| `TextArea` | `QPlainTextEdit` | `tk.Text` | `TextInput(multiline=True)` |

> **Estado actual:** `TextField` y `TextArea` son el ejemplo de diseño de este
> tutorial; todavía no forman parte de la API pública. Los primitives portables
> actuales son `Column`, `Row`, `Text` y `Button`.

## Antes de escribir código: dos ideas importantes

### Un primitive portable no es un wrapper de todas las APIs nativas

Qt, Tkinter y Kivy tienen nombres y capacidades diferentes. La tarea de PSX es
definir una pequeña API que tenga el mismo significado en todos los renderers.

Para `TextField`, empezaremos con estas props:

| Prop | Tipo | Significado |
| --- | --- | --- |
| `value` | `str` | Texto controlado por el estado de Python. |
| `placeholder` | `str` | Ayuda cuando el campo está vacío. |
| `enabled` | `bool` | Permite o bloquea edición. |
| `read_only` | `bool` | El contenido se puede seleccionar, pero no editar. |
| `password` | `bool` | Oculta los caracteres introducidos. |
| `on_change` | callable que recibe `str` | Se llama al cambiar el texto. |
| `on_submit` | callable sin argumentos | Se llama al confirmar el campo. |
| `key` | `str` o `int` | Conserva identidad durante reconciliación. |
| `ref` | `use_ref()` | Referencia al handle montado por PSX. |

No agregues al contrato portable una prop sólo porque exista en una plataforma.
Por ejemplo, `inputMask` de Qt, colores específicos de Kivy o estilos ttk no
deben entrar en `TextField` hasta que PSX pueda documentar un comportamiento
equivalente y probado en los tres backends.

### `TextField` y `TextArea` son widgets diferentes

Un campo de una línea debe ser `TextField`. El texto multilínea debe ser
`TextArea`. Esta separación evita flags ambiguos y permite usar el widget
correcto de cada toolkit.

- En Qt, [`QLineEdit`](https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QLineEdit.html)
  es de una línea; [`QPlainTextEdit`](https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QPlainTextEdit.html)
  es la opción de texto plano multilínea.
- [`QTextEdit`](https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QTextEdit.html)
  permite texto enriquecido; no debe ser el backend inicial de un `TextArea`
  de texto plano.
- En Tkinter, `ttk.Entry` es de una línea y `tk.Text` es multilínea. La
  [documentación oficial de Tkinter](https://docs.python.org/3/library/tkinter.html)
  es la referencia de la biblioteca estándar; este
  [tutorial de `Text`](https://python-course.eu/tkinter/text-widget-in-tkinter.php)
  sirve sólo como lectura complementaria, no como contrato de PSX.
- En Kivy, el mismo
  [`TextInput`](https://kivy.org/doc/stable/api-kivy.uix.textinput.html) cubre
  los dos casos con su propiedad `multiline`.

## Paso 1: escribe primero el contrato y el ejemplo de uso

Antes de editar renderers, crea un ejemplo que quieras que funcione. Es la
forma más simple de descubrir si una API es clara:

```python
from psx import component, psx, use_state


@component
def NameForm():
    name, set_name = use_state("")

    def save() -> None:
        print(f"Saving {name}")

    return psx("""
        <Column padding={24} spacing={12}>
            <Text>Welcome, {name}</Text>
            <TextField
                value={name}
                placeholder="Your name"
                on_change={set_name}
                on_submit={save}
            />
            <Button label="Save" enabled={name_is_valid} on_click={save} />
        </Column>
    """)
```

El ejemplo usa referencias seguras de PSX, no expresiones arbitrarias. Calcula
`name_is_valid` en Python antes del template. En un módulo sin la transformación
M4B, pasa esos valores mediante `scope={...}`.

## Paso 2: crea el builder del core

Los builders existentes están en `psx/core/vnode.py`. Añade un constructor
`TextField` junto a `Text` y `Button`.

```python
from collections.abc import Callable


def TextField(
    value: str = "",
    *,
    placeholder: str = "",
    enabled: bool = True,
    read_only: bool = False,
    password: bool = False,
    on_change: Callable[[str], None] | None = None,
    on_submit: Callable[[], None] | None = None,
    key: str | int | None = None,
    ref: object | None = None,
) -> VNode:
    if not isinstance(value, str):
        raise TypeError("TextField value must be a string.")
    if not isinstance(placeholder, str):
        raise TypeError("TextField placeholder must be a string.")
    if not all(isinstance(flag, bool) for flag in (enabled, read_only, password)):
        raise TypeError("TextField enabled, read_only and password must be booleans.")
    if on_change is not None and not callable(on_change):
        raise TypeError("TextField on_change must be callable or None.")
    if on_submit is not None and not callable(on_submit):
        raise TypeError("TextField on_submit must be callable or None.")

    return create_element(
        "TextField",
        key=key,
        ref=ref,
        value=value,
        placeholder=placeholder,
        enabled=enabled,
        read_only=read_only,
        password=password,
        on_change=on_change,
        on_submit=on_submit,
    )
```

También exporta `TextField` desde `psx/__init__.py`. Un builder centralizado
impide que cada renderer acepte props distintas por accidente.

## Paso 3: registra el tag en el compilador de markup

En `psx/markup/compile.py`, importa `TextField` y agrégalo a `_PRIMITIVES`:

```python
_PRIMITIVES = {
    "Column": Column,
    "Row": Row,
    "Text": Text,
    "Button": Button,
    "TextField": TextField,
    "Fragment": VFragment,
    "Native": Native,
}
```

No hace falta añadir una regla especial de contenido: `TextField` es un nodo
vacío, como un control HTML `<input>`. El texto se recibe siempre mediante la
prop `value`.

En este punto, añade pruebas de markup:

```python
tree = psx('<TextField value={name} placeholder="Name" />', scope={"name": "Ada"})
assert tree.type == "TextField"
assert tree.props["value"] == "Ada"
assert tree.props["placeholder"] == "Name"
```

## Paso 4: implementa Qt

Edita `psx/renderers/qt/pyside6.py` y luego aplica el mismo patrón a los
renderers PyQt. El widget real es `QLineEdit`.

| Prop PSX | Operación de `QLineEdit` |
| --- | --- |
| `value` | `setText(value)` |
| `placeholder` | `setPlaceholderText(value)` |
| `enabled` | `setEnabled(value)` |
| `read_only` | `setReadOnly(value)` |
| `password` | `setEchoMode(QLineEdit.EchoMode.Password)` o `Normal` |
| `on_change` | señal `textChanged(str)` |
| `on_submit` | señal `returnPressed()` |

En `create()`, importa y crea el `QLineEdit`. En `update()`, aplica sólo las
props modificadas. Antes de llamar a `setText`, compara el valor nuevo con
`widget.text()`. Si son iguales, no hagas nada. Si necesitas bloquear una señal
durante una actualización programática, conserva y restaura el estado de
`blockSignals`; de ese modo no conviertes un render en un evento de usuario.

En `bind_event()`, añade ambos eventos. El callback de `textChanged` debe hacer
`slot.invoke(text)`; el de `returnPressed` debe hacer `slot.invoke()`. Devuelve
una suscripción que desconecte exactamente ese callback durante el desmontaje.

## Paso 5: implementa Tkinter

Edita `psx/renderers/tkinter.py`. El control de una línea es `ttk.Entry`.

`Entry` no tiene una prop `text` equivalente a Qt. La forma estable es crear
un `tk.StringVar`, inicializarlo con `value` y entregarlo como `textvariable`.
Guarda ese `StringVar` en el handle de PSX: si no mantienes una referencia,
Python puede recolectarlo y el enlace deja de ser fiable.

| Prop PSX | Implementación Tkinter |
| --- | --- |
| `value` | `StringVar.set(value)` |
| `placeholder` | Adaptador propio; no existe en `ttk.Entry` estándar |
| `enabled` | `widget.state(("!disabled",))` o `("disabled",)` |
| `read_only` | estado `readonly` |
| `password` | `widget.configure(show="*")` |
| `on_change` | `StringVar.trace_add("write", callback)` |
| `on_submit` | `widget.bind("<Return>", callback)` |

Para una primera versión portable, implementa el placeholder como una pequeña
capa PSX y documenta sus límites. No finjas que `ttk.Entry` tiene esa capacidad
nativa. El callback de `trace_add` debe enviar `variable.get()` a
`slot.invoke(...)`.

Al desmontar, elimina tanto el `trace` como el binding de `<Return>`. Es fácil
olvidarlo y terminar con callbacks duplicados después de varios renders.

## Paso 6: implementa Kivy

Edita `psx/renderers/kivy.py` e importa `kivy.uix.textinput.TextInput`. Para
`TextField`, créalo con `multiline=False`.

| Prop PSX | Propiedad o evento de Kivy |
| --- | --- |
| `value` | `text` |
| `placeholder` | `hint_text` |
| `enabled` | `disabled=not enabled` |
| `read_only` | `readonly` |
| `password` | `password` |
| `on_change` | binding de `text` |
| `on_submit` | binding de `on_text_validate` |

Kivy llama al callback de `text` con el widget y el texto. El adaptador PSX
debe ocultar ese detalle y llamar sólo a `slot.invoke(text)`. El callback de
`on_text_validate` no necesita argumentos.

## Paso 7: valida las props en los tres renderers

Cada renderer ya rechaza props desconocidas. Añade `TextField` a esa validación
con exactamente estas props:

```python
{"value", "placeholder", "enabled", "read_only", "password", "on_change", "on_submit"}
```

Esto es importante: si Qt acepta una prop extra pero Tkinter no, el usuario no
debe descubrirlo sólo al cambiar de plataforma. O la prop entra al contrato
portable con una implementación y pruebas para todos los backends, o queda
fuera del primitive.

## Paso 8: conserva identidad, foco y cursor

Prueba este caso antes de considerar el widget terminado:

1. Renderiza `<TextField key="name" value={name} ... />`.
2. Da foco al control y mueve el cursor a la mitad del texto.
3. Actualiza otro nodo de la pantalla.
4. Confirma que el `TextField` sigue siendo la misma instancia nativa y no
   perdió foco ni posición del cursor.

La reconciliación de PSX reutiliza la instancia cuando tipo y `key` son
compatibles. El renderer debe actualizar propiedades, no reconstruir el widget.

## Paso 9: escribe pruebas pequeñas antes de una prueba gráfica

Incluye al menos estas pruebas:

1. `TextField(...)` rechaza tipos inválidos.
2. El markup genera un VNode de tipo `TextField`.
3. Cada renderer crea el control nativo correcto.
4. Un cambio de `value` actualiza la instancia existente.
5. `on_change` recibe exactamente un `str`.
6. `on_submit` no recibe argumentos.
7. `enabled`, `read_only` y `password` se aplican.
8. Al desmontar, las suscripciones se limpian.
9. Una prop desconocida genera `RendererCapabilityError` con un mensaje útil.

Después ejecuta las pruebas del proyecto en el entorno indicado y haz una
prueba manual mínima en Qt, Tkinter y Kivy. Las pruebas unitarias encuentran
regresiones; la prueba manual confirma foco, teclado, cursor y apariencia.

## Paso 10: crea `TextArea` como el siguiente primitive

No intentes resolver texto multilínea dentro de `TextField`. Crea un segundo
widget con contrato separado:

```xml
<TextArea
    value={notes}
    placeholder="Write your notes"
    on_change={set_notes}
/>
```

Su primera implementación debe usar texto plano:

- Qt: `QPlainTextEdit` y la señal `textChanged`; lee el valor con
  `toPlainText()`.
- Tkinter: `tk.Text`; lee el valor con `get("1.0", "end-1c")`.
- Kivy: `TextInput(multiline=True)`.

No uses `QTextEdit` como reemplazo silencioso de `TextArea`: su modelo de texto
enriquecido necesita una API PSX distinta y explícita si se incorpora después.

## ¿Y `QInputDialog`?

[`QInputDialog`](https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QInputDialog.html)
es un diálogo temporal de Qt, no un campo componible dentro del árbol visual.
Por eso no es la implementación de `TextField`. Más adelante PSX podría
diseñar un primitive o servicio `PromptDialog`, con apertura, resultado y
cancelación explícitos; debe ser un proyecto separado y no una prop escondida
en un campo de texto.

## Checklist de entrega

- [ ] Builder exportado desde `psx`.
- [ ] Tag registrado en el compilador de markup.
- [ ] Contrato de props validado en el core.
- [ ] Implementación en PySide6, PyQt6, PyQt5, Tkinter y Kivy.
- [ ] Eventos con la misma firma pública en todos los renderers.
- [ ] Limpieza de eventos al desmontar.
- [ ] Pruebas unitarias y prueba manual en los tres backends.
- [ ] Documentación de capacidades y límites conocidos.

Cuando este checklist esté completo, un usuario de PSX podrá usar
`<TextField />` sin importar cuál UI framework está funcionando debajo.
