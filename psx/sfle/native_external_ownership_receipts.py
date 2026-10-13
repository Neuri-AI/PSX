"""Deprecated compatibility import for internal Native layout certification tooling.

Canonical module: tests.certification.native_external_ownership_receipts
Do not add new certification implementation under psx.sfle.
"""
from tests.certification.native_external_ownership_receipts import *  # noqa: F401,F403
from tests.certification.native_external_ownership_receipts import main

if __name__ == "__main__":
    main()
