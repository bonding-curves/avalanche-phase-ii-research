"""Exercise the static figure gallery using disposable client checkouts."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from figure_gallery import DIRECTORY, collect, digest, links, run


class GalleryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        self.page = "content/Research Space/index.md"
        self.write(self.page, '---\ntitle: "Observed record"\ndate: 2026-10-30\n---\n'
                   '![Observed alpha](/Research-Space/images/alpha.png)\n*Figure 1. Recorded values.*\n')
        self.write("content/Research Space/images/alpha.png", b"png-alpha")
        self.write("content/Research Space/images/alpha.svg", b"svg-alpha")
        self.write("content/Research Space/images/alpha.csv", "date,value\n1,2\n")
        self.write("content/Other/copy.png", b"png-alpha")
        self.write("content/Other/index.md", '---\ntitle: Second use\n---\n![Copy](copy.png)\n')
        self.write("src/avalanche_research/model/images/diagram.png", b"png-code-diagram")
        self.registry = {"rules": [{"prefix": "content/Research Space/", "models": ["Empirical"],
                                   "family": "Time series", "evidence": "Empirical (descriptive)",
                                   "horizons": ["Observed window"], "sources": [self.page],
                                   "classification_basis": "Source document describes observed values."}],
                         "legacy_ids_by_sha256": {digest(b"png-alpha"): ["f123"]}, "figures": {}}
        self.write(DIRECTORY + "/registry.json", json.dumps(self.registry))
        self.write(DIRECTORY + "/gallery.template.html",
                   '<!doctype html><!-- GALLERY_CARDS --><script>const manifest=/* GALLERY_DATA */;</script>')
        self.track()

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text if isinstance(text, bytes) else text.encode())
        return path

    def track(self):
        subprocess.run(["git", "add", "."], cwd=self.root, check=True)

    def test_all_images_are_preserved_with_ids_companions_downloads_and_usage(self):
        manifest, copies = collect(self.root)
        self.assertEqual(manifest["inventory_images"], 4)
        self.assertEqual(len(manifest["figures"]), 2)
        figure = next(f for f in manifest["figures"] if f["ids"] == ["f123"])
        self.assertEqual(len(figure["assets"]), 3)
        self.assertEqual({a["format"] for a in figure["downloads"]}, {"PNG", "SVG", "CSV"})
        self.assertEqual(len(figure["downloads"]), 3)
        self.assertEqual({u["title"] for u in figure["usages"]}, {"Observed record", "Second use"})
        self.assertEqual(figure["models"], ["Empirical"])
        self.assertIn("Recorded values", " ".join(u["caption"] for u in figure["usages"]))
        self.assertTrue(all(name.startswith(DIRECTORY + "/assets/") for name in copies))
        self.assertEqual(len(copies), 1)

    def test_missing_classification_is_explicit_and_not_guessed_from_dates(self):
        self.registry["rules"] = []
        self.write(DIRECTORY + "/registry.json", json.dumps(self.registry))
        manifest, _ = collect(self.root)
        for figure in manifest["figures"]:
            self.assertEqual(figure["models"], ["Unspecified"])
            self.assertIn("models not recorded", figure["metadata_gaps"])
            self.assertIn("producing command not recorded", figure["metadata_gaps"])

    def test_new_tracked_image_appears_and_untracked_or_ignored_does_not(self):
        self.write(".gitignore", "*.secret.png\n")
        self.write("content/new.png", b"new")
        self.write("content/ignored.secret.png", b"secret")
        self.assertEqual(collect(self.root)[0]["inventory_images"], 4)
        subprocess.run(["git", "add", "content/new.png"], cwd=self.root, check=True)
        self.assertEqual(collect(self.root)[0]["inventory_images"], 5)

    def test_missing_tracked_image_fails_instead_of_advertising_it(self):
        (self.root / "content/Other/copy.png").unlink()
        with self.assertRaisesRegex(ValueError, "image is missing"):
            collect(self.root)

    def test_html_wiki_and_relative_image_uses_are_resolved_but_plain_links_are_not(self):
        self.write(self.page, '<img src="images/alpha.png" alt="HTML record">\n'
                   '![[images/alpha.svg|Vector record]]\n[Download](images/alpha.png)\n')
        manifest, _ = collect(self.root)
        figure = next(f for f in manifest["figures"] if f["ids"])
        self.assertEqual(len(figure["usages"]), 2)
        self.write(self.page, '[Download](images/alpha.png)\n')
        manifest, _ = collect(self.root)
        figure = next(f for f in manifest["figures"] if f["ids"])
        self.assertEqual([u["title"] for u in figure["usages"]], ["Second use"])

    def test_build_check_detects_changed_caption_or_image_and_check_does_not_write(self):
        run(self.root)
        def snapshot():
            return {str(p.relative_to(self.root)): (p.stat().st_mtime_ns, digest(p.read_bytes()))
                    for p in self.root.rglob("*") if p.is_file()}
        before = snapshot()
        run(self.root, check=True)
        self.assertEqual(snapshot(), before)
        self.write(self.page, '![Changed caption](/Research-Space/images/alpha.png)\n')
        with self.assertRaisesRegex(ValueError, "Gallery is stale"):
            run(self.root, check=True)
        run(self.root)
        self.write("content/Other/copy.png", b"new bytes")
        with self.assertRaisesRegex(ValueError, "Gallery is stale"):
            run(self.root, check=True)

    def test_build_is_portable_and_writes_only_gallery_paths(self):
        before = {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        result = run(self.root)
        after = {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        self.assertTrue(all(name.startswith(DIRECTORY + "/") for name in result["outputs"]))
        self.assertTrue(all(after[name] == body for name, body in before.items()))
        content = after[DIRECTORY + "/gallery.html"].decode()
        self.assertIn("data-file-href", content)
        self.assertIn("../Research-Space/images/alpha.png", content)
        self.assertNotIn(str(self.root), content)
        self.assertNotIn("/home/", content)
        self.assertNotIn("/* GALLERY_DATA */", content)
        self.assertEqual(links(self.page, page=True)["file_href"], "../../../Research%20Space/index.md")

    def test_symlink_asset_or_registry_source_escape_is_rejected(self):
        outside = Path(self.temporary.name).parent / (self.root.name + "-outside")
        outside.write_bytes(b"outside")
        self.addCleanup(outside.unlink)
        (self.root / "content/escape.png").symlink_to(outside)
        self.track()
        with self.assertRaisesRegex(ValueError, "leaves the repository"):
            collect(self.root)
        (self.root / "content/escape.png").unlink()
        subprocess.run(["git", "rm", "--cached", "content/escape.png"], cwd=self.root,
                       check=True, capture_output=True)
        self.registry["rules"][0]["sources"] = ["../outside.json"]
        self.write(DIRECTORY + "/registry.json", json.dumps(self.registry))
        with self.assertRaisesRegex(ValueError, "not delivered"):
            collect(self.root)

    def test_generated_html_escapes_caption_and_embedded_json(self):
        self.write(self.page, '![</script><script>alert(1)</script>](/Research-Space/images/alpha.png)\n')
        run(self.root)
        content = (self.root / DIRECTORY / "gallery.html").read_text()
        self.assertNotIn("</script><script>alert(1)", content)
        self.assertIn("&lt;/script&gt;", content)
        self.assertIn("\\u003c/script>", content)


if __name__ == "__main__":
    unittest.main()
