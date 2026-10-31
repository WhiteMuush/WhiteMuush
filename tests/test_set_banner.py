import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from scripts.set_banner import available_banners, current_banner, main, set_banner

README = '<!-- Banner -->\n<img src="./assets/banners/default.png" alt="Banner" width="100%" />\n'


class AvailableBannersTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.directory = Path(tmp.name)

    def add_files(self, *names):
        for name in names:
            (self.directory / name).write_bytes(b"")

    def test_lists_png_names(self):
        self.add_files("default.png", "halloween.png")
        self.assertEqual(available_banners(self.directory), {"default", "halloween"})

    def test_rejects_unexpected_files(self):
        for name in ("Winter.png", "winter.PNG", "winter.jpg", "winter", "new_year.png"):
            with self.subTest(name=name):
                self.add_files("default.png", name)
                with self.assertRaises(ValueError):
                    available_banners(self.directory)
                (self.directory / name).unlink()

    def test_ignores_hidden_files(self):
        self.add_files("default.png", ".DS_Store")
        self.assertEqual(available_banners(self.directory), {"default"})


class ReadmeBannerTest(unittest.TestCase):
    def test_reads_current_banner(self):
        self.assertEqual(current_banner(README), "default")

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
                    current_banner(readme)
                with self.assertRaises(ValueError):
                    set_banner(readme, "halloween")


class MainTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.banners = self.root / "assets" / "banners"
        self.banners.mkdir(parents=True)
        for name in ("default", "halloween"):
            (self.banners / f"{name}.png").write_bytes(b"")
        self.readme = self.root / "README.md"
        self.readme.write_text(README)

    def run_main(self, *argv):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = main(list(argv), root=self.root)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_sets_requested_banner(self):
        code, out, _ = self.run_main("halloween")
        self.assertEqual((code, out), (0, "halloween\n"))
        self.assertEqual(current_banner(self.readme.read_text()), "halloween")

    def test_leaves_readme_untouched_when_already_set(self):
        code, out, err = self.run_main("default")
        self.assertEqual((code, out), (0, "default\n"))
        self.assertIn("already", err)
        self.assertEqual(self.readme.read_text(), README)

    def test_rejects_unknown_banner_without_touching_readme(self):
        code, out, err = self.run_main("christmas")
        self.assertEqual((code, out), (1, ""))
        self.assertIn("error: no banner named 'christmas'", err)
        self.assertEqual(self.readme.read_text(), README)

    def test_without_argument_validates_current_setup(self):
        code, out, _ = self.run_main()
        self.assertEqual((code, out), (0, "default\n"))
        self.assertEqual(self.readme.read_text(), README)

    def test_validation_fails_when_readme_points_to_missing_image(self):
        (self.banners / "default.png").unlink()
        code, out, err = self.run_main()
        self.assertEqual((code, out), (1, ""))
        self.assertIn("default.png", err)

    def test_reports_invalid_banner_files(self):
        (self.banners / "Noel.PNG").write_bytes(b"")
        code, out, err = self.run_main("halloween")
        self.assertEqual((code, out), (1, ""))
        self.assertIn("Noel.PNG", err)
        self.assertEqual(self.readme.read_text(), README)


if __name__ == "__main__":
    unittest.main()
