"""Public exceptions raised by the dependency-free PSX core."""


class PSXError(Exception):
    """Base class for PSX errors."""


class InvalidChildError(PSXError, TypeError):
    """Raised when a value cannot be normalized into a VNode child."""


class DuplicateKeyError(PSXError, ValueError):
    """Raised when sibling VNodes reuse a key."""


class DuplicateComponentError(PSXError, ValueError):
    """Raised when a component registry name is registered more than once."""


class UnknownComponentError(PSXError, LookupError):
    """Raised when a component registry cannot resolve a requested name."""


class RendererCapabilityError(PSXError):
    """Raised when a renderer cannot honour a requested operation."""


class RendererConfigurationError(PSXError):
    """Raised when an application cannot select a renderer."""


class HookOrderError(PSXError):
    """Raised when a component calls hooks in a different order between renders."""


class ThreadViolationError(PSXError):
    """Raised when an operation would synchronously mutate UI during rendering."""


class MarkupSyntaxError(PSXError):
    """A PSX markup error with source position information."""

    def __init__(self, message: str, *, filename: str, line: int, column: int) -> None:
        self.filename = filename
        self.line = line
        self.column = column
        super().__init__(f"{filename}:{line}:{column}: {message}")
