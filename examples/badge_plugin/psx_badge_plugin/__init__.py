"""Example third-party PSX package; install it with a ``psx.plugins`` entry point."""

from psx import Text


def Badge(*, label: str, key=None):
    return Text(label, bold=True, key=key)


class BadgePlugin:
    def register(self, api) -> None:
        api.component("Badge", Badge)
