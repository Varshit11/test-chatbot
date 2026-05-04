"""Ingest CLI entrypoint.

    python -m backend.ingest.runner --once
    python -m backend.ingest.runner --loop --every 60
    python -m backend.ingest.runner --backfill 90 --symbol XAUUSD
    python -m backend.ingest.runner --backfill 30 --symbol XAUUSD --skip-features

Designed to be the only thing a cron / systemd / EventBridge / Windows Task
Scheduler invocation needs to fire.
"""
from __future__ import annotations

import argparse
import logging
import sys

from .pipeline import DEFAULT_CATALOG, backfill, run_cycle, run_loop


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s | %(message)s",
        stream=sys.stdout,
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="backend.ingest.runner")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--once", action="store_true", help="Run a single ingest cycle and exit.")
    g.add_argument("--loop", action="store_true", help="Run cycles forever; sleep --every seconds between.")
    g.add_argument("--backfill", type=int, metavar="DAYS",
                   help="Backfill N days of 1m history for --symbol (or all in catalog).")
    p.add_argument("--every", type=int, default=60, help="Loop cadence in seconds (default: 60).")
    p.add_argument("--symbol", type=str, default=None,
                   help="Restrict to a single symbol (default: every symbol in catalog).")
    p.add_argument("--asset-class", type=str, default="forex",
                   help="Only used with --backfill --symbol if symbol isn't in catalog.")
    p.add_argument("--max-cycles", type=int, default=None, help="Stop --loop after N cycles (testing).")
    p.add_argument("--skip-features", action="store_true",
                   help="Don't recompute SMC/TI features (just OHLCV refresh).")
    p.add_argument("--log-level", type=str, default="INFO")
    args = p.parse_args(argv)

    _setup_logging(args.log_level)

    if args.backfill is not None:
        symbols = [args.symbol] if args.symbol else list(DEFAULT_CATALOG.keys())
        for sym in symbols:
            meta = DEFAULT_CATALOG.get(sym, {})
            ac = meta.get("asset_class") or args.asset_class
            backfill(
                sym,
                asset_class=ac,
                days=args.backfill,
                primary=meta.get("primary"),
                derived=meta.get("derived"),
                feature_tfs=meta.get("feature_tfs"),
                rebuild_features=not args.skip_features,
            )
        return 0

    catalog = None
    if args.symbol:
        if args.symbol in DEFAULT_CATALOG:
            catalog = {args.symbol: DEFAULT_CATALOG[args.symbol]}
        else:
            catalog = {args.symbol: {"asset_class": args.asset_class, "timeframes": ["5m", "15m", "1h", "4h"]}}

    if args.once:
        summary = run_cycle(catalog, skip_features=args.skip_features)
        logging.getLogger(__name__).info("done: %s", summary)
        return 0
    if args.loop:
        run_loop(args.every, catalog=catalog, max_cycles=args.max_cycles)
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
