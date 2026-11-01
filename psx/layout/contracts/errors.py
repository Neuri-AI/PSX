"""Stable diagnostics for SFLE validation and engine capability boundaries."""

from __future__ import annotations

from enum import Enum


class DiagnosticCode(str, Enum):
    UNKNOWN_PROP = "SFLE_UNKNOWN_PROP"
    INVALID_LENGTH = "SFLE_INVALID_LENGTH"
    UNSUPPORTED_FEATURE = "SFLE_UNSUPPORTED_FEATURE"
    UNSUPPORTED_MEASUREMENT = "SFLE_UNSUPPORTED_MEASUREMENT"
    MULTIPLE_ROOTS = "SFLE_MULTIPLE_ROOTS"
    LAYOUT_CONSTRAINT = "SFLE_LAYOUT_CONSTRAINT_ERROR"
    BACKEND_MISMATCH = "SFLE_BACKEND_MISMATCH"
    INVALID_TREE = "SFLE_INVALID_TREE"
    INVALID_SNAPSHOT = "SFLE_INVALID_SNAPSHOT"
    INVALID_WIRE = "SFLE_INVALID_WIRE"


class SFLEError(ValueError):
    """Base error with a stable diagnostic code and optional node identity."""

    def __init__(self, code: DiagnosticCode, message: str, node_id: str | None = None):
        super().__init__(message)
        self.code = code
        self.node_id = node_id


class SFLECapabilityError(SFLEError):
    """Requested feature has no conformant engine/backend implementation."""


class SFLEWireError(SFLEError):
    """Input/output violates the versioned wire representation."""
