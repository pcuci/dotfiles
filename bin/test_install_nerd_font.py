"""Exercise only the installer's font function with local archives and fake network tools."""

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile


class NerdFontInstallTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.home = self.root / "home"
        self.home.mkdir()
        self.tmp = self.root / "tmp"
        self.tmp.mkdir()
        self.font_dir = self.home / ".local/share/fonts/NerdFonts/JetBrainsMono"
        self.log = self.root / "commands.log"
        self.archive = self.root / "font.zip"
        self.env = {
            **os.environ,
            "HOME": str(self.home),
            "PATH": str(self.bin),
            "TMPDIR": str(self.tmp),
            "MOCK_LOG": str(self.log),
            "MOCK_ARCHIVE": str(self.archive),
            "MOCK_RELEASE": "v3.5.1",
        }
        self.bash = shutil.which("bash")
        for command in ("sed", "mktemp", "mkdir", "unzip", "cp", "mv", "rm"):
            (self.bin / command).symlink_to(shutil.which(command))
        self.mock_command(
            "curl",
            """import os, shutil, sys
from pathlib import Path
args = sys.argv[1:]
with Path(os.environ['MOCK_LOG']).open('a') as log:
    log.write('curl ' + args[-1] + '\\n')
releases_url = 'https://github.com/ryanoasis/nerd-fonts/releases'
if args[-1] == releases_url + '/latest':
    if os.environ.get('MOCK_LOOKUP_FAIL'):
        sys.exit(22)
    print(os.environ.get('MOCK_LATEST_URL',
        'https://github.com/ryanoasis/nerd-fonts/releases/tag/' + os.environ['MOCK_RELEASE']), end='')
else:
    expected_url = releases_url + '/download/' + os.environ['MOCK_RELEASE'] + '/JetBrainsMono.zip'
    if args[-1] != expected_url:
        raise AssertionError('Unexpected download URL: ' + args[-1])
    if os.environ.get('MOCK_DOWNLOAD_FAIL'):
        sys.exit(22)
    shutil.copyfile(os.environ['MOCK_ARCHIVE'], args[args.index('-o') + 1])
""",
        )
        self.mock_command(
            "fc-cache",
            """import os, sys
from pathlib import Path
with Path(os.environ['MOCK_LOG']).open('a') as log:
    log.write('fc-cache\\n')
sys.exit(int(os.environ.get('MOCK_CACHE_FAIL', '0')))
""",
        )
        # A stale/missing font cache must not force repeated archive downloads.
        self.mock_command("fc-list", "raise RuntimeError('font cache must not be queried')\n")
        install = Path(__file__).resolve().parents[1] / "install"
        source = install.read_text()
        self.function = source.split("install_nerd_font_if_outdated() {", 1)[1].split(
            "\ninstall_nerd_font_if_outdated\n", 1
        )[0]
        self.function = "install_nerd_font_if_outdated() {" + self.function
        self.make_archive()

    def mock_command(self, name, source):
        path = self.bin / name
        path.write_text(f"#!{sys.executable}\n{source}")
        path.chmod(0o755)

    @staticmethod
    def metadata(release):
        return f"# Nerd Fonts\n\nThis is an archived font from the Nerd Fonts release {release}.\n"

    def make_archive(self, release="v3.5.1", include_font=True):
        with zipfile.ZipFile(self.archive, "w") as archive:
            archive.writestr("README.md", self.metadata(release))
            if include_font:
                archive.writestr("JetBrainsMonoNerdFont-Regular.ttf", b"new font fixture")
            archive.writestr("OFL.txt", "license fixture\n")

    def installed(self, release="v3.5.1", include_font=True):
        self.font_dir.mkdir(parents=True)
        if release is not None:
            (self.font_dir / "README.md").write_text(self.metadata(release))
        if include_font:
            (self.font_dir / "JetBrainsMonoNerdFont-Regular.ttf").write_bytes(b"old font fixture")

    def run_font_install(self):
        result = subprocess.run(
            [self.bash, "-c", "set -euo pipefail\n" + self.function + "\ninstall_nerd_font_if_outdated"],
            env=self.env,
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(list(self.tmp.iterdir()), [], "Temporary archive files leaked")
        return result

    def downloads(self):
        return self.log.read_text().count("/download/") if self.log.exists() else 0

    def assert_old_fonts_unchanged(self):
        self.assertEqual((self.font_dir / "README.md").read_text(), self.metadata("v3.4.0"))
        self.assertEqual(
            (self.font_dir / "JetBrainsMonoNerdFont-Regular.ttf").read_bytes(), b"old font fixture"
        )

    def test_latest_installed_skips_download_and_font_cache(self):
        self.installed()
        result = self.run_font_install()
        self.assertIn("already at latest release", result.stdout)
        self.assertEqual(self.downloads(), 0)
        self.assertNotIn("fc-cache", self.log.read_text())

    def test_first_install_then_repeat_downloads_only_once_despite_cache_failure(self):
        self.env["MOCK_CACHE_FAIL"] = "1"
        self.run_font_install()
        self.run_font_install()
        self.assertEqual(self.downloads(), 1)
        self.assertEqual(self.log.read_text().count("fc-cache"), 1)
        self.assertEqual((self.font_dir / "README.md").read_text(), self.metadata("v3.5.1"))
        self.assertEqual(
            (self.font_dir / "JetBrainsMonoNerdFont-Regular.ttf").read_bytes(), b"new font fixture"
        )

    def test_old_release_is_upgraded(self):
        self.installed("v3.4.0")
        self.run_font_install()
        self.assertEqual(self.downloads(), 1)
        self.assertEqual(
            (self.font_dir / "JetBrainsMonoNerdFont-Regular.ttf").read_bytes(), b"new font fixture"
        )

    def test_unversioned_install_is_updated_once(self):
        self.installed(None)
        self.run_font_install()
        self.run_font_install()
        self.assertEqual(self.downloads(), 1)

    def test_metadata_without_fonts_does_not_skip_install(self):
        self.installed(include_font=False)
        self.run_font_install()
        self.assertEqual(self.downloads(), 1)


    def test_lookup_failure_preserves_installed_fonts(self):
        self.installed("v3.4.0")
        self.env["MOCK_LOOKUP_FAIL"] = "1"
        result = self.run_font_install()
        self.assertIn("could not determine latest", result.stderr)
        self.assertEqual(self.downloads(), 0)
        self.assert_old_fonts_unchanged()

    def test_invalid_redirect_does_not_select_download_url(self):
        self.env["MOCK_LATEST_URL"] = "https://example.invalid/releases/tag/v3.5.1"
        result = self.run_font_install()
        self.assertIn("could not determine latest", result.stderr)
        self.assertEqual(self.downloads(), 0)

    def test_download_failure_preserves_installed_fonts(self):
        self.installed("v3.4.0")
        self.env["MOCK_DOWNLOAD_FAIL"] = "1"
        result = self.run_font_install()
        self.assertIn("failed to download", result.stderr)
        self.assert_old_fonts_unchanged()

    def test_corrupt_archive_preserves_installed_fonts(self):
        self.installed("v3.4.0")
        self.archive.write_bytes(b"not a ZIP archive")
        result = self.run_font_install()
        self.assertIn("failed to extract", result.stderr)
        self.assert_old_fonts_unchanged()

    def test_mismatched_release_preserves_installed_fonts(self):
        self.installed("v3.4.0")
        self.make_archive(release="v3.4.0")
        result = self.run_font_install()
        self.assertIn("mismatched release", result.stderr)
        self.assert_old_fonts_unchanged()

    def test_archive_without_fonts_preserves_installed_fonts(self):
        self.installed("v3.4.0")
        self.make_archive(include_font=False)
        result = self.run_font_install()
        self.assertIn("missing or mismatched", result.stderr)
        self.assert_old_fonts_unchanged()

    def test_partial_copy_failure_keeps_old_release_and_allows_retry(self):
        self.installed("v3.4.0")
        (self.bin / "cp").unlink()
        self.mock_command(
            "cp",
            """import shutil, sys
from pathlib import Path
source = Path(sys.argv[-2])
destination = Path(sys.argv[-1])
shutil.copyfile(source / 'JetBrainsMonoNerdFont-Regular.ttf',
                destination / 'JetBrainsMonoNerdFont-Regular.ttf')
raise SystemExit(1)
""",
        )
        result = self.run_font_install()
        self.assertIn("failed to install", result.stderr)
        self.assertEqual((self.font_dir / "README.md").read_text(), self.metadata("v3.4.0"))
        self.assertEqual(
            (self.font_dir / "JetBrainsMonoNerdFont-Regular.ttf").read_bytes(), b"new font fixture"
        )
        self.assertFalse((self.font_dir / "OFL.txt").exists())
        (self.bin / "cp").unlink()
        (self.bin / "cp").symlink_to(shutil.which("cp"))
        self.run_font_install()
        self.assertEqual(self.downloads(), 2)
        self.assertEqual((self.font_dir / "README.md").read_text(), self.metadata("v3.5.1"))
        self.assertEqual((self.font_dir / "OFL.txt").read_text(), "license fixture\n")


if __name__ == "__main__":
    unittest.main()
