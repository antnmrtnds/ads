#!/usr/bin/env python3
"""Rank ads by how long they have been active."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rank ads by the duration they have been active."
    )
    parser.add_argument(
        "input",
        type=Path,
        nargs="?",
        default=Path("company_ads_response_2025-10-02T11-27-48-597Z.json"),
        help="Path to the company ads response JSON file.",
    )
    parser.add_argument(
        "--now",
        type=str,
        default=None,
        help=(
            "Optional ISO 8601 timestamp to use as the current time when an ad is still "
            "active (defaults to the actual current time)."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=(
            "Optional path to write the ranking results. Defaults to creating a file "
            "with a '_ranked.txt' suffix in the same directory as the input file."
        ),
    )
    return parser.parse_args()


def parse_datetime(epoch_value: Optional[int], iso_string: Optional[str]) -> Optional[datetime]:
    if epoch_value is not None:
        try:
            return datetime.fromtimestamp(int(epoch_value), tz=timezone.utc)
        except (ValueError, OSError):
            pass
    if iso_string:
        try:
            if iso_string.endswith("Z"):
                iso_string = iso_string[:-1] + "+00:00"
            return datetime.fromisoformat(iso_string)
        except ValueError:
            pass
    return None


def determine_end_time(ad: Dict[str, Any], default_now: datetime) -> Optional[datetime]:
    end_epoch = ad.get("end_date")
    end_iso = ad.get("end_date_string")
    end_time = parse_datetime(end_epoch, end_iso)
    if end_time is None and ad.get("is_active"):
        return default_now
    return end_time


def iter_ads(data: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    for key in ("data", "results"):
        ads = data.get(key)
        if isinstance(ads, list):
            return ads
    return []


def format_timedelta(delta_seconds: float) -> str:
    days = delta_seconds / 86400
    return f"{days:.2f}"


def main() -> None:
    args = parse_args()
    raw_text = args.input.read_text(encoding="utf-8")
    payload = json.loads(raw_text)

    if args.now:
        now = parse_datetime(None, args.now)
        if now is None:
            raise SystemExit(f"Invalid --now value: {args.now}")
    else:
        now = datetime.now(tz=timezone.utc)

    ranking = []
    for ad in iter_ads(payload):
        start_time = parse_datetime(ad.get("start_date"), ad.get("start_date_string"))
        if start_time is None:
            continue
        end_time = determine_end_time(ad, now)
        if end_time is None:
            continue
        duration_seconds = (end_time - start_time).total_seconds()
        if duration_seconds < 0:
            continue
        ranking.append(
            {
                "ad_archive_id": ad.get("ad_archive_id"),
                "page_name": ad.get("page_name"),
                "start_time": start_time,
                "end_time": end_time,
                "duration_seconds": duration_seconds,
            }
        )

    ranking.sort(key=lambda item: item["duration_seconds"], reverse=True)

    if args.output:
        output_path = args.output
    else:
        output_path = args.input.with_name(f"{args.input.stem}_ranked.txt")

    lines = []
    if not ranking:
        message = "No ads with valid start and end times found."
        print(message)
        lines.append(message)
        output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return

    header = (
        f"{'Rank':>4}  {'Ad Archive ID':<20}  {'Page Name':<30}  "
        f"{'Start (UTC)':<20}  {'End (UTC)':<20}  {'Active Days':>12}"
    )
    separator = "-" * len(header)
    print(header)
    print(separator)
    lines.extend([header, separator])

    for index, item in enumerate(ranking, start=1):
        start_str = item["start_time"].strftime("%Y-%m-%d %H:%M")
        end_str = item["end_time"].strftime("%Y-%m-%d %H:%M")
        active_days = format_timedelta(item["duration_seconds"])
        line = (
            f"{index:>4}  {str(item['ad_archive_id'] or ''):<20}  "
            f"{str(item['page_name'] or ''):<30}  {start_str:<20}  {end_str:<20}  {active_days:>12}"
        )
        print(line)
        lines.append(line)

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
