# Portable TextArea

`TextArea` representa un campo de entrada de texto de múltiples líneas portable. 
Mantiene un contrato idéntico en Qt (`QPlainTextEdit`), Kivy (`TextInput`) y Tkinter (`Text`).

| Propiedad | Tipo | Predeterminado |
| :--- | :--- | :--- |
| `value` | `str` | `""` (Primer argumento posicional o contenido del tag) |
| `placeholder` | `str` | `""` |
| `font_size` | `int` o `float` (>0) | `14` |
| `enabled` | `bool` | `True` |
| `read_only` | `bool` | `False` |
| `on_change` | `Callable[[str], None]` o `None` | `None` |
| `key` | `str`, `int` o `None` | `None` |
| `ref` | PSX Ref o `None` | `None` |

### Ejemplo en API Python

```python
TextArea(
    "Contenido inicial...",
    placeholder="Escribe tu nota aquí...",
    font_size=16,
    on_change=lambda text: print(f"Nuevo texto: {text}"),
)
```

### PSX

```psx
def render():
    return psx(
        """<TextArea
            value="Contenido inicial..."
            placeholder="Escribe tu nota aquí..."
            font_size=16
            on_change=lambda text: print(f"Nuevo texto: {text}")
        />"""
    )
```