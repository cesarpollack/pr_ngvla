#!/usr/bin/env python3
"""
scripts/phase2_exceedance.py
=============================
Phase 2 — Hourly exceedance climatology (orquestador).

Usage
-----
    python scripts/phase2_exceedance.py --var rh
    python scripts/phase2_exceedance.py --var wind
    python scripts/phase2_exceedance.py --var precip
    python scripts/phase2_exceedance.py --var pwv
    python scripts/phase2_exceedance.py --var all

Options
-------
    --var       Variable to process: rh | wind | precip | pwv | all
    --no-maria  Include Hurricane Maria months (default: excluded)
"""

import argparse

from pr_ngvla.analysis.exceedance import (
    monthly_exceedance_climatology,
    save_exceedance,
)

SUPPORTED = ["rh", "wind", "precip", "pwv"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Phase 2 — Exceedance climatology"
    )
    parser.add_argument(
        "--var",
        required=True,
        choices=SUPPORTED + ["all"],
        help="Variable to process",
    )
    parser.add_argument(
        "--no-maria",
        action="store_true",
        default=False,
        help="Include Hurricane Maria months (default: excluded)",
    )
    return parser.parse_args()


def run(var: str, exclude_maria: bool) -> None:
    print("=" * 60)
    print(f"Phase 2 — Exceedance climatology: {var.upper()}")
    print(f"Maria exclusion: {exclude_maria}")
    print("=" * 60)
    ds_out = monthly_exceedance_climatology(var, exclude_maria=exclude_maria)
    save_exceedance(ds_out, var)
    print(f"[DONE] {var}\n")


def main() -> None:
    args = parse_args()
    exclude_maria = not args.no_maria

    if args.var == "all":
        for var in SUPPORTED:
            run(var, exclude_maria)
    else:
        run(args.var, exclude_maria)


if __name__ == "__main__":
    main()
