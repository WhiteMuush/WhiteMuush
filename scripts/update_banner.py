"""Point the README banner at the image for today's event or season."""

import argparse
import re
import sys
import tomllib
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
TIMEZONE = ZoneInfo("Europe/Paris")
DEFAULT_BANNER = "default"
SEASONS = {
    12: "winter", 1: "winter", 2: "winter",
    3: "spring", 4: "spring", 5: "spring",
    6: "summer", 7: "summer", 8: "summer",
    9: "autumn", 10: "autumn", 11: "autumn",
}
# Names end up in file paths and in the README, so keep them to a safe charset.
NAME = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
MONTH_DAY = re.compile(r"(\d{2})-(\d{2})")
BANNER_SRC = re.compile(r'src="\./assets/banners/[a-z0-9-]+\.png"')


@dataclass(frozen=True)
class Event:
    name: str
    start: tuple[int, int]
    end: tuple[int, int]

    def is_active(self, day: date) -> bool:
        today = (day.month, day.day)
        if self.start <= self.end:
            return self.start <= today <= self.end
        return today >= self.start or today <= self.end


def parse_month_day(value: object) -> tuple[int, int]:
    match = MONTH_DAY.fullmatch(value) if isinstance(value, str) else None
    if match is None:
        raise ValueError(f"expected a MM-DD date, got {value!r}")
    month, day = int(match[1]), int(match[2])
    try:
        date(2000, month, day)  # leap year, so 02-29 is accepted
    except ValueError:
        raise ValueError(f"no such day: {value!r}") from None
    return month, day


def parse_events(config: dict) -> list[Event]:
    entries = config.get("events", [])
    if not isinstance(entries, list) or not all(isinstance(entry, dict) for entry in entries):
        raise ValueError("'events' must be a list of [[events]] tables")
    events = []
    for entry in entries:
        name = entry.get("name")
        if not isinstance(name, str) or not NAME.fullmatch(name):
            raise ValueError(f"invalid event name: {name!r}")
        start = parse_month_day(entry.get("start"))
        end = parse_month_day(entry.get("end"))
        events.append(Event(name, start, end))
    return events


def pick_banner(day: date, events: list[Event], available: set[str]) -> str:
    for event in events:
        if event.is_active(day) and event.name in available:
            return event.name
    season = SEASONS[day.month]
    return season if season in available else DEFAULT_BANNER


def available_banners(directory: Path) -> set[str]:
    names = {path.stem for path in directory.glob("*.png")}
    invalid = sorted(name for name in names if not NAME.fullmatch(name))
    if invalid:
        raise ValueError(f"invalid banner file names in {directory}: {invalid}")
    if DEFAULT_BANNER not in names:
        raise ValueError(f"missing fallback banner {directory / (DEFAULT_BANNER + '.png')}")
    return names


def set_banner(readme: str, banner: str) -> str:
    found = len(BANNER_SRC.findall(readme))
    if found != 1:
        raise ValueError(f"expected exactly one banner image in the README, found {found}")
    return BANNER_SRC.sub(lambda _: f'src="./assets/banners/{banner}.png"', readme)


def main(argv: list[str] | None = None, root: Path = ROOT) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--date", type=date.fromisoformat, help="use this YYYY-MM-DD date instead of today (Europe/Paris)"
    )
    args = parser.parse_args(argv)
    day = args.date or datetime.now(TIMEZONE).date()
    banners_dir = root / "assets" / "banners"
    readme_path = root / "README.md"

    try:
        with (banners_dir / "events.toml").open("rb") as file:
            events = parse_events(tomllib.load(file))
        banner = pick_banner(day, events, available_banners(banners_dir))
        readme = readme_path.read_text(encoding="utf-8")
        updated = set_banner(readme, banner)
        if updated != readme:
            readme_path.write_text(updated, encoding="utf-8")
            print(f"README now shows the {banner} banner", file=sys.stderr)
        else:
            print(f"README already shows the {banner} banner", file=sys.stderr)
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    print(banner)
    return 0


if __name__ == "__main__":
    sys.exit(main())
