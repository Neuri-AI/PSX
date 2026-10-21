"""Internal, dependency-free CSS foundation types.

No public stylesheet API or renderer integration is promised by this package.
"""

from .properties import CssDeclaration, CssDiagnostic, CssProperty, CssPropertyRegistry, CssValidationError, foundation_registry

__all__ = (
    "CssDeclaration", "CssDiagnostic", "CssProperty", "CssPropertyRegistry",
    "CssValidationError", "foundation_registry",
)
