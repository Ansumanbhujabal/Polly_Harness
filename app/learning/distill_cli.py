"""CLI entry-point for the incident distiller.

Usage:
    python -m app.learning.distill_cli [--min-age 60] [--batch-size 10]

Called by `make distill`.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="distill_cli",
        description="Distil un-processed incident records into PR-ready proposals.",
    )
    parser.add_argument(
        "--min-age",
        type=int,
        default=60,
        metavar="MINUTES",
        help="Minimum incident age in minutes to be eligible (default: 60).",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=10,
        metavar="N",
        help="Maximum number of incidents to process per run (default: 10).",
    )
    return parser.parse_args(argv)


async def _run(min_age: int, batch_size: int) -> list[dict]:  # type: ignore[type-arg]
    from app.learning.incident_distiller import distill_incidents

    proposals = await distill_incidents(min_age_minutes=min_age, batch_size=batch_size)
    return [p.model_dump(mode="json") for p in proposals]


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    results = asyncio.run(_run(args.min_age, args.batch_size))

    if not results:
        print("No proposals generated (no eligible incidents or empty batch).")
        return

    print(f"\n=== Distiller produced {len(results)} proposal(s) ===\n")
    for i, proposal in enumerate(results, 1):
        print(f"--- Proposal {i}/{len(results)} ---")
        print(f"  Kind        : {proposal['kind']}")
        print(f"  Target file : {proposal['target_file']}")
        print(f"  Incidents   : {', '.join(proposal['source_incident_ids'])}")
        print(f"  Justification: {proposal['justification'][:120]}...")
        print()


if __name__ == "__main__":
    main()
