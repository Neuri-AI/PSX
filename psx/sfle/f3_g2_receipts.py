"""Deprecated compatibility import for internal F3 certification tooling.

Canonical module: tests.certification.f3_g2_receipts
Do not add new certification implementation under psx.sfle.
"""
from tests.certification.f3_g2_receipts import *  # noqa: F401,F403
from tests.certification.f3_g2_receipts import main

if __name__ == "__main__":
    main()
