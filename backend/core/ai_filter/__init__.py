"""AI Filter: ML model that scores individual trade signals.

  * `ml_filter.apply_ml_filter` — trains LightGBM on **SMC/ICT bar features**
    (`smc_ict_features_without_future_bars.py`, vendored + cached), labels from
    **points** (or pnl), and picks the **notebook threshold**: argmax of Σ points
    on held-out test trades (grid 0.02..0.99 step 0.005). Falls back to an
    SMC-only heuristic if training fails.

  * `filter.AIFilter` (legacy) — original 9-feature heuristic. Kept for tests.
"""
from .filter import AIFilter, FilterResult, build_features, apply_filter
from .ml_filter import apply_ml_filter, FilterModelResult, FilterTrainSummary

__all__ = [
    "AIFilter", "FilterResult", "build_features", "apply_filter",
    "apply_ml_filter", "FilterModelResult", "FilterTrainSummary",
]
