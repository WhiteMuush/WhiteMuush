"""Point the README banner at assets/banners/<name>.png, or validate the current one."""

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Names end up in file paths and in the README, so keep them to a safe charset.
NAME = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
BANNER_SRC = re.compile(r'src="\./assets/banners/([a-z0-9-]+)\.png"')


def available_banners(directory: Path) -> set[str]:
    names = set()
    for path in directory.iterdir():
        if path.name.startswith("."):
            continue
        if path.suffix != ".png" or not NAME.fullmatch(path.stem):
            raise ValueError(
                f"unexpected file {path.name!r} in {directory}: banners must be"
                " <name>.png with lowercase letters, digits and dashes"
            )
        names.add(path.stem)
    return names


def current_banner(readme: str) -> str:
    found = BANNER_SRC.findall(readme)
    if len(found) != 1:
        raise ValueError(f"expected exactly one banner image in the README, found {len(found)}")
    return found[0]


def set_banner(readme: str, banner: str) -> str:
    current_banner(readme)
    return BANNER_SRC.sub(lambda _: f'src="./assets/banners/{banner}.png"', readme)


def main(argv: list[str] | None = None, root: Path = ROOT) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("banner", nargs="?", help="banner to show, e.g. halloween; omit to validate the current setup")
    args = parser.parse_args(argv)
    banners_dir = root / "assets" / "banners"
    readme_path = root / "README.md"

    try:
        available = available_banners(banners_dir)
        readme = readme_path.read_text(encoding="utf-8")
        if args.banner is None:
            banner = current_banner(readme)
            if banner not in available:
                raise ValueError(f"the README shows {banner}.png, which is not in {banners_dir}")
        else:
            banner = args.banner
            if banner not in available:
                raise ValueError(f"no banner named {banner!r}, available: {', '.join(sorted(available))}")
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
