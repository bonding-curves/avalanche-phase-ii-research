import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_site


class ClientSiteCheckTest(unittest.TestCase):
    def fixture(self, root: Path) -> None:
        for relative in check_site.REQUIRED_CONTENT + check_site.REQUIRED_PUBLIC:
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("# Fixture\n")
        for relative, required_values in check_site.REQUIRED_TEXT.items():
            path = root / relative
            path.write_text(path.read_text() + "\n".join(required_values) + "\n")

    def test_accepts_complete_client_fixture(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.fixture(root)
            self.assertEqual(check_site.check(root)["status"], "pass")

    def test_rejects_private_reference(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.fixture(root)
            target = root / check_site.REQUIRED_CONTENT[0]
            private_reference = ".co" + "dex/resources"
            target.write_text(f"See {private_reference} for details.\n")
            result = check_site.check(root)
            self.assertEqual(result["status"], "fail")
            self.assertTrue(result["forbidden_text_matches"])

    def test_rejects_missing_local_image(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.fixture(root)
            target = root / check_site.REQUIRED_CONTENT[0]
            target.write_text(target.read_text() + "\n![Missing](/missing.png)\n")
            result = check_site.check(root)
            self.assertEqual(result["status"], "fail")
            self.assertEqual(result["missing_local_assets"][0]["target"], "/missing.png")

    def test_rejects_missing_required_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.fixture(root)
            (root / check_site.REQUIRED_PUBLIC[0]).unlink()
            result = check_site.check(root)
            self.assertEqual(result["status"], "fail")
            self.assertIn(check_site.REQUIRED_PUBLIC[0], result["missing_required_files"])

    def test_rejects_missing_reciprocal_link(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.fixture(root)
            target = root / next(iter(check_site.REQUIRED_TEXT))
            target.write_text("# Link removed\n")
            result = check_site.check(root)
            self.assertEqual(result["status"], "fail")
            self.assertTrue(result["missing_required_text"])


if __name__ == "__main__":
    unittest.main()
