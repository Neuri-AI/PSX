"""Official optional integration with Qyro's public runtime APIs."""

from __future__ import annotations

import importlib
from dataclasses import dataclass

from psx import App, component
from psx.core.errors import PSXError, RendererCapabilityError
from psx.core.hooks import provide_context, use_context
from psx.core.vnode import Box, VNode

try:  # Optional integration: importing PSX core never requires Qyro.
    from qyro.ui.component import Component as _QyroComponent
except ImportError:  # pragma: no cover - exercised by installations without Qyro
    _QyroComponent = object  # type: ignore[assignment,misc]

_QYRO_CONTEXT = object()
_QYRO_CONTAINER = object()

# Qt binding prefixes recognized by the host detection helper, ordered from
# newer to older. The prefix is used as the import module name as well.
_QT_BINDING_PREFIXES = ("PySide6", "PyQt6", "PyQt5", "PySide2")


def QyroProvider(
    child: VNode, *, context: object | None = None, container: object | None = None
) -> VNode:
    """Provide existing Qyro runtime objects without constructing a new engine."""
    if context is None and container is None:
        raise TypeError(
            "QyroProvider requires an existing ApplicationContext or EngineContainer.")
    if container is None:
        container = getattr(context, "container", None)
    _validate_container(container)
    return _QyroProvider(child, context=context, container=container)


@component
def _QyroProvider(
    context: object | None, container: object, children: tuple[object, ...]
) -> VNode:
    provide_context(_QYRO_CONTAINER, container)
    if context is not None:
        provide_context(_QYRO_CONTEXT, context)
    if len(children) != 1 or not isinstance(children[0], VNode):
        raise TypeError("QyroProvider requires exactly one VNode child.")
    return children[0]


def use_qyro_context() -> object:
    try:
        return use_context(_QYRO_CONTEXT)
    except LookupError as exc:
        raise PSXError(
            "use_qyro_context() requires an ancestor QyroProvider(context=...).") from exc


def use_container() -> object:
    try:
        container = use_context(_QYRO_CONTAINER)
    except LookupError as exc:
        raise PSXError(
            "use_container() requires an ancestor QyroProvider.") from exc
    _validate_container(container)
    return container


def use_settings() -> dict[str, object]:
    """Read effective Qyro settings through its existing public container use case."""
    container = use_container()
    metadata = container.load_settings_use_case.execute()
    return metadata.raw_settings


def use_resource(*segments: str, required: bool = True) -> str:
    """Resolve a Qyro resource using its real resolver, including frozen-mode behavior."""
    container = use_container()
    return str(container.resolve_resource_use_case.execute(*segments, required=required))


@dataclass(slots=True)
class PSXMount:
    """Owns a PSX subtree while borrowing, never destroying, its Qyro host."""

    host: object
    app: App
    widget: object
    _central: bool = False
    _packed: bool = False
    _disposed: bool = False

    def unmount(self) -> None:
        if self._disposed:
            return
        self._disposed = True
        if self._central:
            try:
                if getattr(self.host, "centralWidget", lambda: None)() is self.widget:
                    take = getattr(self.host, "takeCentralWidget", None)
                    if callable(take):
                        take()
            except RuntimeError:
                # Qt may emit destroyed after its C++ object is already gone.
                pass
        if self._packed:
            forget = getattr(self.widget, "pack_forget", None)
            if callable(forget):
                forget()
            # A renderer created by ``mount_psx`` for a borrowed Tk host owns
            # only its repeating ``after`` callback, not the host window.
            renderer = self.app.renderer
            if not getattr(renderer, "_owns_root", True):
                close = getattr(renderer, "close", None)
                if callable(close):
                    close()
        self.app.unmount()


class PSXComponent(_QyroComponent):
    """Opt-in Qyro component mixin whose ``render()`` returns one PSX VNode.

    Place it between the native Qt class and ``ApplicationContext`` in the MRO,
    for example ``class Window(QMainWindow, PSXComponent, ApplicationContext)``.
    It reuses Qyro's initialization/lifecycle wrapper and replaces only the
    render commit with a PSX subtree mounted into the existing host.

    Set ``psx_store`` on a subclass to make that existing Pydux store available
    to the class ``render()`` through ``use_selector`` and ``use_dispatch``.
    """

    def __init_subclass__(cls, **kwargs: object) -> None:
        """Adapt Kivy's non-cooperative App initializer behind the mixin."""
        super().__init_subclass__(**kwargs)
        if not _is_kivy_class(cls):
            return
        original_init = cls.__init__
        if getattr(original_init, "_psx_kivy_app_wrapped", False):
            return

        def wrapped_init(self: object, *args: object, **init_kwargs: object) -> None:
            original_init(self, *args, **init_kwargs)
            if not hasattr(self, "built"):
                from kivy.app import App

                App.__init__(self, **init_kwargs)

        wrapped_init._psx_kivy_app_wrapped = True  # type: ignore[attr-defined]
        cls.__init__ = wrapped_init

    def _mount_component_lifecycle(self) -> None:
        if getattr(self, "_component_lifecycle_mounted", False):
            return
        # Kivy's App asks ``build()`` for the root widget after construction.
        # Defer the PSX commit until that point so PSX returns the same native
        # root to Kivy instead of attempting to mount into an App object.
        if _is_kivy_app(self) and not getattr(self, "_psx_building_kivy", False):
            self._psx_kivy_pending = True
            return
        # Qyro's cooperative wrappers can call the Component lifecycle while
        # QMainWindow is still traversing its C++ base initializer.  Commit on
        # the already-existing Qt event loop once the native host is ready.
        try:
            native_ready = not getattr(self, "_in_wrapped_init", False)
            meta_object = getattr(self, "metaObject", None)
            if native_ready and callable(meta_object):
                meta_object()
        except RuntimeError:
            native_ready = False
        if not native_ready:
            if not getattr(self, "_psx_lifecycle_scheduled", False):
                self._psx_lifecycle_scheduled = True
                after = getattr(self, "after", None)
                if callable(after):
                    # Tk host: defer through Tk's event loop.
                    after(0, self._mount_component_lifecycle)
                else:
                    # Qt host: defer through the binding the host itself
                    # already loaded. Mixing PySide and PyQt in one process is
                    # unsupported by Qt, so we must never hardcode one binding.
                    core = _qt_module_for(self, "QtCore")
                    if core is None:
                        raise PSXError(
                            "PSXComponent requires a Tk host with after() or a Qt host."
                        )
                    core.QTimer.singleShot(0, self._mount_component_lifecycle)
            return
        self._component_lifecycle_mounted = True
        self._allow_styled_background()
        self.component_will_mount()
        # Render through one stable PSX function component so class-style Qyro
        # views can use PSX hooks while retaining their familiar ``render`` API.

        @component
        def QyroPSXRoot() -> VNode:
            node = self.render()
            if not isinstance(node, VNode):
                raise TypeError(
                    "PSXComponent.render() must return a PSX VNode.")
            return node

        self._psx_root_component = QyroPSXRoot
        node = QyroPSXRoot()
        store = _store_for_component(self)
        if store is not None:
            from psx.integrations.pydux import StoreProvider

            node = StoreProvider(store=store, child=node)
        # ``ApplicationContext`` may attach its container later in Qyro's
        # cooperative initializer; its public property performs that attach.
        context = self if hasattr(type(self), "container") else None
        self._psx_mount = mount_psx(self, node, context=context)
        self._connect_psx_cleanup()
        self._start_qyro_hot_reload()
        self.component_did_mount()
        self.set_styles()
        self.on_resize()

    def build(self) -> object:
        """Return the PSX-created Kivy root when used before ``kivy.app.App`` in MRO."""
        if not _is_kivy_app(self):
            raise RuntimeError(
                "PSXComponent.build() is only provided for Kivy App hosts.")
        self._psx_building_kivy = True
        try:
            self._mount_component_lifecycle()
        finally:
            self._psx_building_kivy = False
        mounted = getattr(self, "_psx_mount", None)
        if mounted is None:
            raise RuntimeError("PSX Kivy root did not mount during build().")
        return mounted.widget

    def _connect_psx_cleanup(self) -> None:
        if getattr(self, "_psx_cleanup_connected", False):
            return
        destroyed = getattr(self, "destroyed", None)
        connect = getattr(destroyed, "connect", None)
        if callable(connect):
            connect(lambda *_: self.unmount_psx())
            self._psx_cleanup_connected = True
            # Only Qt hosts expose ``destroyed``.  Do not import a Qt binding
            # while mounting a Tkinter application: macOS cannot safely mix
            # both UI runtimes in this process.
            widgets = _qt_module_for(self, "QtWidgets")
            if widgets is not None:
                application = widgets.QApplication.instance()
                about_to_quit = getattr(application, "aboutToQuit", None)
                quit_connect = getattr(about_to_quit, "connect", None)
                if callable(quit_connect):
                    quit_connect(self.unmount_psx)
        protocol = getattr(self, "protocol", None)
        destroy = getattr(self, "destroy", None)
        if callable(protocol) and callable(destroy):
            def close_tk_host() -> None:
                self.unmount_psx()
                destroy()

            protocol("WM_DELETE_WINDOW", close_tk_host)

    def unmount_psx(self) -> None:
        reloader = getattr(self, "_psx_hot_reloader", None)
        if reloader is not None:
            reloader.stop()
            self._psx_hot_reloader = None
        mounted = getattr(self, "_psx_mount", None)
        if mounted is not None:
            mounted.unmount()
            self._psx_mount = None

    def _start_qyro_hot_reload(self) -> None:
        """Enable development refresh automatically when Qyro is not frozen."""
        if getattr(self, "_psx_hot_reloader", None) is not None:
            return
        try:
            from psx.devtools.qyro_reload import QyroComponentReloader

            reloader = QyroComponentReloader(self)
            if reloader.start():
                self._psx_hot_reloader = reloader
        except Exception as exc:
            # Development tooling must never prevent a normal Qyro window
            # from mounting when source inspection is unavailable.
            print(f"[PSX Dev] DISABLED: {exc}")


def mount_psx(
    host: object,
    child: VNode,
    *,
    renderer: str | object | None = None,
    context: object | None = None,
    container: object | None = None,
    providers: tuple[object, ...] = (),
) -> PSXMount:
    """Mount a PSX subtree inside an existing Qyro/native Qt host.

    The host is borrowed. PSX only owns and tears down the subtree widget it
    creates; this function deliberately never invokes Qyro component lifecycle
    hooks.
    """
    if renderer is None and context is not None:
        renderer = _renderer_from_context(context)
    # Qyro already owns the Tk root.  Creating a second ``tk.Tk`` here would
    # produce an empty Qyro window plus a separate PSX window, and gives each
    # one an independent event-loop lifecycle.  Supply the borrowed host to
    # the renderer instead.
    if isinstance(renderer, str) and renderer.strip().lower() == "tkinter":
        from psx.renderers.tkinter import TkinterRenderer

        renderer = TkinterRenderer(root=host)

    inner = Box(child)
    node = (
        QyroProvider(inner, context=context, container=container)
        if context is not None or container is not None
        else inner
    )
    app = App(node, renderer=renderer, providers=providers)
    handle = app.mount()
    widget = getattr(handle, "widget", None)
    if widget is None:
        app.unmount()
        raise RendererCapabilityError(
            "mount_psx() currently requires a renderer handle with a native widget.")
    set_central = getattr(host, "setCentralWidget", None)
    if callable(set_central):
        set_central(widget)
        return PSXMount(host, app, widget, _central=True)
    layout_getter = getattr(host, "layout", None)
    layout = layout_getter() if callable(layout_getter) else None
    add_widget = getattr(layout, "addWidget", None)
    if callable(add_widget):
        add_widget(widget)
        return PSXMount(host, app, widget)
    pack = getattr(widget, "pack", None)
    if callable(pack):
        pack(fill="both", expand=True)
        return PSXMount(host, app, widget, _packed=True)
    if _is_kivy_app(host):
        return PSXMount(host, app, widget)
    app.unmount()
    raise RendererCapabilityError(
        "Host must provide setCentralWidget() or a layout with addWidget().")


def _renderer_from_context(context: object) -> str | None:
    """Prefer the host's actual Qyro container over Qyro's module singleton.

    ``ApplicationContext`` supports subclasses and its module-level convenience
    helper can therefore refer to a different inherited singleton. The mounted
    host is authoritative for this subtree.
    """
    container = getattr(context, "container", None)
    loader = getattr(container, "load_settings_use_case", None)
    execute = getattr(loader, "execute", None)
    if not callable(execute):
        return None
    settings = execute().raw_settings
    binding = settings.get("binding") or settings.get(
        "framework") if isinstance(settings, dict) else None
    return binding if isinstance(binding, str) and binding.strip() else None


def _validate_container(container: object | None) -> None:
    required = ("load_settings_use_case", "resolve_resource_use_case")
    missing = [name for name in required if getattr(
        container, name, None) is None]
    if missing:
        raise TypeError(
            f"Expected a Qyro EngineContainer; missing {', '.join(missing)}.")


def _is_kivy_app(value: object) -> bool:
    """Identify Kivy lazily without importing it in the core integration."""
    return any(base.__module__.startswith("kivy.app") for base in type(value).__mro__)


def _is_kivy_class(value: type[object]) -> bool:
    return any(base.__module__.startswith("kivy.app") for base in value.__mro__)


def _qt_binding_for(host: object) -> str | None:
    """Detect the Qt binding of a host by inspecting its MRO.

    Returns one of ``"PySide6"``, ``"PyQt6"``, ``"PyQt5"``, ``"PySide2"``,
    or ``None`` when the host is not a Qt class. Detection relies only on
    ``__module__`` of each base, so no binding is imported until the caller
    actually asks for a module.
    """
    for cls in type(host).__mro__:
        module = getattr(cls, "__module__", "")
        for prefix in _QT_BINDING_PREFIXES:
            if module.startswith(prefix + "."):
                return prefix
    return None


def _qt_module_for(host: object, submodule: str) -> object | None:
    """Import ``<binding>.<submodule>`` for the host's Qt binding, if any.

    Returns ``None`` when the host is not a Qt class, so Tk and Kivy hosts
    silently skip Qt-only cleanup paths. The binding is detected from the
    host's MRO, never assumed: a PyQt6 host imports ``PyQt6.QtCore`` even
    when PySide6 is also installed in the environment.
    """
    binding = _qt_binding_for(host)
    if binding is None:
        return None
    return importlib.import_module(f"{binding}.{submodule}")


def _store_for_component(component_instance: object) -> object | None:
    """Find the explicit or unambiguous module-level Pydux store for a view.

    A one-store Qyro module is the normal application shape, so wiring it is
    implicit.  An application with multiple stores remains explicit to avoid
    silently subscribing a component to the wrong state container.
    """
    explicit = getattr(component_instance, "psx_store", None)
    if explicit is not None:
        _validate_pydux_store(explicit)
        return explicit
    render = getattr(type(component_instance), "render", None)
    namespace = getattr(render, "__globals__", {})
    candidates = [
        value
        for value in namespace.values()
        if _is_pydux_store(value)
    ]
    unique = {id(value): value for value in candidates}
    if len(unique) <= 1:
        return next(iter(unique.values()), None)
    raise PSXError(
        "More than one Pydux store is declared in this module; select one with ``psx_store``."
    )


def _is_pydux_store(value: object) -> bool:
    return all(callable(getattr(value, name, None)) for name in ("get_state", "dispatch", "select"))


def _validate_pydux_store(store: object) -> None:
    if not _is_pydux_store(store):
        raise TypeError("psx_store must be a Pydux-compatible store.")


__all__ = [
    "PSXMount",
    "PSXComponent",
    "QyroProvider",
    "mount_psx",
    "use_container",
    "use_qyro_context",
    "use_resource",
    "use_settings",
]
