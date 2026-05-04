"""
Build offline SMC feature files for every (symbol, timeframe) in data/instruments.py.

Outputs:
  backend/data/prebuilt_features/{SYMBOL}_{tf}_smc.parquet (or .pkl if pyarrow missing)

Run once locally (can take several minutes per series — then AI filter only reads Parquet):

  cd chatbot/quantflow/backend
  python materialize_prebuilt_features.py

Later: run the same entrypoint from a cron / worker every N minutes after API ingest.
"""
from __future__ import annotations

import logging
import os
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(name)s %(message)s",
)

_QUANTFLOW = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, _QUANTFLOW)

from backend.core.features.smc_cached import materialize_prebuilt_for_catalog  # noqa: E402


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(line_buffering=True)
        except Exception:
            pass
    print("Materializing prebuilt SMC features (this is slow; AI filter will be fast after)…", flush=True)
    done, failed = materialize_prebuilt_for_catalog()
    print(f"Finished OK ({len(done)}): {done}", flush=True)
    if failed:
        print(f"FAILED ({len(failed)}): {failed}", flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
