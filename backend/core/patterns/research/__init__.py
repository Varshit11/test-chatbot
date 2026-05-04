"""
Research-grade chart patterns vendored for QuantFlow codegen.

Canonical implementations (rectangle, wedge, triangle, harmonics, …) live under:
  ``TradeXpert/marketapi_data_fetcher/algo_methods/patterns/``

This subpackage ports a **subset** that runs in the dynamic-strategy sandbox
(numpy / pandas only; **no** ``import`` in user ``GeneratedStrategy`` code):

- **head_shoulders** — from ``head_and_shoulders.py`` (plotting / mplfinance stripped).
- **doubles** — from ``doubles.py`` + pivot logic from ``pivot_points.py`` (tqdm / plotly
  stripped; lookback uses integer row positions so DatetimeIndex is safe).

Modules such as ``rectangle.py`` often depend on scipy or mplfinance; use the originals
in marketapi for full parity until ported here.
"""

from .head_shoulders import (
    HSPattern,
    find_hs_patterns,
    hs_pattern_return,
)
from .doubles_chart import find_all_pivot_points, find_doubles_pattern

__all__ = [
    "HSPattern",
    "find_hs_patterns",
    "hs_pattern_return",
    "find_all_pivot_points",
    "find_doubles_pattern",
]
