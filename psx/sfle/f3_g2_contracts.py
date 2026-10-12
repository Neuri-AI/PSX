"""C2 executable certification policy for every registered PSX component.

A reference is never a PASS. Required operations without implemented probes
are explicit C3/C4/C5 obligations, not implicit backend-level certifications.
"""
from __future__ import annotations
from dataclasses import dataclass
from types import MappingProxyType

from .f3_g2_evidence import COMPONENT_OPERATION_TESTS
from .f3_g2_matrix import OPERATIONS, g2_certification_matrix

# Reviewer-approved semantic exclusions, not a blanket skip on failures.
EVENTLESS = frozenset({
    "Text", "Spacer", "Divider", "ProgressBar", "Badge", "Image", "Box",
    "Flex", "RadioGroup",
})
# Component-owned callbacks are not defined on these decoration hosts.
# RadioGroup has on_change and is therefore NOT eventless.
EVENTLESS = EVENTLESS - {"RadioGroup"}
OWNER_BLOCK = MappingProxyType({
    "create": "C3", "update": "C3", "reorder": "C3",
    "unmount": "C3", "event_rebind": "C3",
    "borrowed_ownership": "C4", "rollback": "C3",
    "invalidation": "C5",
})


@dataclass(frozen=True, slots=True)
class OperationContract:
    backend: str
    component: str
    operation: str
    applicability: str
    mechanism: str
    reference: str | None
    reason: str

    @property
    def key(self) -> tuple[str, str, str]:
        return self.backend, self.component, self.operation


def g2_operation_contracts() -> tuple[OperationContract, ...]:
    result = []
    for cell in g2_certification_matrix():
        for op in OPERATIONS:
            reference = COMPONENT_OPERATION_TESTS.get((cell.backend, cell.component, op))
            if cell.status != "native":
                applicable = "not_applicable"
                mechanism = "exclusion"
                reason = f"Renderer classification: {cell.status}"
            elif op == "event_rebind" and cell.component in EVENTLESS:
                applicable = "not_applicable"
                mechanism = "exclusion"
                reason = f"{cell.component} has no component-owned event callback"
            elif op == "borrowed_ownership":
                # Borrowed widget ownership is a property of the external Native
                # bridge, not an ordinary built-in. Native is audited by C4.
                applicable = "not_applicable"
                mechanism = "exclusion"
                reason = "Builtin widgets are owned; borrowed Native is a separate C4 port"
            else:
                applicable = "required"
                mechanism = "pytest_reference" if reference else "pending_probe"
                reason = ("Specific native test reference; execution not yet verified"
                          if reference else f"Executable behavioral assertion due in {OWNER_BLOCK[op]}")
            if applicable == "not_applicable" and reference is not None:
                raise ValueError(f"An N/A operation cannot claim evidence: {cell.backend}/{cell.component}/{op}")
            result.append(OperationContract(
                cell.backend, cell.component, op, applicable, mechanism,
                reference, reason,
            ))
    return tuple(result)


def g2_contract_summary() -> dict[str, dict[str, int]]:
    return {
        backend: {
            status: sum(
                c.backend == backend and
                (("not_applicable" if c.applicability == "not_applicable"
                  else "referenced" if c.reference else "pending") == status)
                for c in g2_operation_contracts()
            )
            for status in ("referenced", "pending", "not_applicable")
        }
        for backend in ("qt", "tk", "kivy", "headless")
    }
