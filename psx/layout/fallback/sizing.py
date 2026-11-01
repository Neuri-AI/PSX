"""Historical compatibility re-export of shared CSS sizing semantics.

The genuine CSS resolver lives in psx.layout.projection and does not load the
optional Python numerical backend.
"""
from psx.layout.projection.size_resolution import *
