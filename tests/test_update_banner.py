import contextlib
import io
import tempfile
import unittest
from datetime import date
from pathlib import Path

from scripts.update_banner import (
    Event,
    available_banners,
    main,
    parse_events,
    pick_banner,
    set_banner,
)

HALLOWEEN = Event("halloween", (10, 15), (11, 1))
NEW_YEAR = Event("new-year", (12, 31), (1, 2))
ALL_SEASONS = {"default", "spring", "summer", "autumn", "winter"}
README = '<!-- Banner -->\n<img src="./assets/banners/default.png" alt="Banner" width="100%" />\n'


class PickBannerTest(unittest.TestCase):
    def assert_banners(self, events, available, cases):
        for day, expected in cases.items():
            with self.subTest(day=day):
                self.assertEqual(pick_banner(day, events, available), expected)

    def test_season_follows_meteorological_months(self):
        self.assert_banners([], ALL_SEASONS, {
            date(2027, 2, 28): "winter",
            date(2027, 3, 1): "spring",
            date(2027, 5, 31): "spring",
            date(2027, 6, 1): "summer",
            date(2027, 8, 31): "summer",
            date(2027, 9, 1): "autumn",
            date(2027, 11, 30): "autumn",
            date(2027, 12, 1): "winter",
            date(2027, 1, 15): "winter",
        })

    def test_event_bounds_are_inclusive(self):
        self.assert_banners([HALLOWEEN], ALL_SEASONS | {"halloween"}, {
            date(2026, 10, 14): "autumn",
            date(2026, 10, 15): "halloween",
            date(2026, 10, 31): "halloween",
            date(2026, 11, 1): "halloween",
            date(2026, 11, 2): "autumn",
        })

    def test_event_can_span_new_year(self):
        self.assert_banners([NEW_YEAR], ALL_SEASONS | {"new-year"}, {
            date(2026, 12, 30): "winter",
            date(2026, 12, 31): "new-year",
            date(2027, 1, 1): "new-year",
            date(2027, 1, 2): "new-year",
            date(2027, 1, 3): "winter",
        })

    def test_first_matching_event_wins(self):
        spooky = Event("spooky", (10, 1), (10, 31))
        available = ALL_SEASONS | {"spooky", "halloween"}
        self.assertEqual(pick_banner(date(2026, 10, 20), [spooky, HALLOWEEN], available), "spooky")

    def test_event_without_image_falls_back_to_season(self):
        self.assertEqual(pick_banner(date(2026, 10, 31), [HALLOWEEN], ALL_SEASONS), "autumn")

    def test_season_without_image_falls_back_to_default(self):
        self.assertEqual(pick_banner(date(2026, 11, 2), [HALLOWEEN], {"default", "halloween"}), "default")


class ParseEventsTest(unittest.TestCase):
    def test_parses_events(self):
        config = {"events": [{"name": "halloween", "start": "10-15", "end": "11-01"}]}
        self.assertEqual(parse_events(config), [HALLOWEEN])

    def test_missing_events_section_means_no_events(self):
        self.assertEqual(parse_events({}), [])

    def test_accepts_leap_day(self):
        config = {"events": [{"name": "leap", "start": "02-29", "end": "02-29"}]}
        self.assertEqual(parse_events(config), [Event("leap", (2, 29), (2, 29))])

    def test_rejects_invalid_config(self):
        def single(**entry):
            return {"events": [{"name": "spooky", "start": "10-15", "end": "11-01", **entry}]}

        invalid = {
            "path traversal in name": single(name="../evil"),
            "uppercase name": single(name="Halloween"),
            "non-string name": single(name=42),
            "missing name": {"events": [{"start": "10-15", "end": "11-01"}]},
            "wrong date format": single(start="10/15"),
            "non-padded date": single(start="1-05"),
            "non-ASCII digits": single(start="١٠-١٥"),
            "impossible day": single(start="02-30"),
            "missing end": {"events": [{"name": "spooky", "start": "10-15"}]},
            "events not a list": {"events": "halloween"},
            "event not a table": {"events": ["halloween"]},
        }
        for label, config in invalid.items():
            with self.subTest(label):
                with self.assertRaises(ValueError):
                    parse_events(config)


class SetBannerTest(unittest.TestCase):
    def test_replaces_banner(self):
        self.assertEqual(
            set_banner(README, "halloween"),
            '<!-- Banner -->\n<img src="./assets/banners/halloween.png" alt="Banner" width="100%" />\n',
        )

    def test_is_idempotent(self):
        once = set_banner(README, "halloween")
        self.assertEqual(set_banner(once, "halloween"), once)

    def test_requires_exactly_one_banner(self):
        for readme in ("# No banner here\n", README * 2):
            with self.subTest(readme=readme):
                with self.assertRaises(ValueError):
                    set_banner(readme, "halloween")


class AvailableBannersTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.directory = Path(tmp.name)
        (self.directory / "events.toml").write_text("")

    def add_images(self, *names):
        for name in names:
            (self.directory / name).write_bytes(b"")

    def test_lists_png_names(self):
        self.add_images("default.png", "halloween.png")
        self.assertEqual(available_banners(self.directory), {"default", "halloween"})

    def test_requires_default_banner(self):
        self.add_images("halloween.png")
        with self.assertRaises(ValueError):
            available_banners(self.directory)

    def test_rejects_unexpected_files(self):
        for name in ("Winter.png", "winter.PNG", "winter.jpg", "winter"):
            with self.subTest(name=name):
                self.add_images("default.png", name)
                with self.assertRaises(ValueError):
                    available_banners(self.directory)
                (self.directory / name).unlink()

    def test_ignores_hidden_files(self):
        self.add_images("default.png", ".DS_Store")
        self.assertEqual(available_banners(self.directory), {"default"})


class MainTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.banners = self.root / "assets" / "banners"
        self.banners.mkdir(parents=True)
        for name in ("default", "halloween"):
            (self.banners / f"{name}.png").write_bytes(b"")
        (self.banners / "events.toml").write_text(
            '[[events]]\nname = "halloween"\nstart = "10-15"\nend = "11-01"\n'
        )
        self.readme = self.root / "README.md"
        self.readme.write_text(README)

    def run_main(self, *argv):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = main(list(argv), root=self.root)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_updates_readme_and_prints_banner(self):
        code, out, _ = self.run_main("--date", "2026-10-31")
        self.assertEqual((code, out), (0, "halloween\n"))
        self.assertIn('src="./assets/banners/halloween.png"', self.readme.read_text())

    def test_leaves_up_to_date_readme_untouched(self):
        code, out, _ = self.run_main("--date", "2026-11-02")
        self.assertEqual((code, out), (0, "default\n"))
        self.assertEqual(self.readme.read_text(), README)

    def test_warns_about_event_without_image(self):
        with (self.banners / "events.toml").open("a") as file:
            file.write('\n[[events]]\nname = "christmas"\nstart = "12-01"\nend = "12-26"\n')
        code, out, err = self.run_main("--date", "2026-12-10")
        self.assertEqual((code, out), (0, "default\n"))
        self.assertIn("warning: event 'christmas' has no christmas.png", err)

    def test_reports_errors_without_touching_readme(self):
        (self.banners / "events.toml").write_text("events = [broken")
        code, out, err = self.run_main("--date", "2026-10-31")
        self.assertEqual((code, out), (1, ""))
        self.assertIn("error:", err)
        self.assertEqual(self.readme.read_text(), README)


if __name__ == "__main__":
    unittest.main()
