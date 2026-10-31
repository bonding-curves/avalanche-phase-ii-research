"""Exercise the exporter's delivery boundaries using disposable Git repositories."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from export_research_review import MANIFEST, Exporter, ExportError, digest


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.output = self.root / "docs/review"
        self.directory = "content/Review Space"
        self.docs = {f"{self.directory}/{source}.md": target for source, target in (
            ("methodology", "modeling.md"), ("evidence", "evidence.md"), ("results", "results.md"),
        )}
        self.write("methodology.md", "# Model `rules`\n\n[Results](/Review-Space/results#result)\n")
        self.write("results.md", "# Result\n")
        self.write("evidence.md", "# Evidence\n")
        self.write("appendix/_index.md", "---\naliases:\n  - older-route/index\n---\n# Inputs\n")
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        self.track()

    def write(self, name, text, *, root=False):
        path = self.root / name if root else self.root / self.directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text if isinstance(text, bytes) else text.encode())
        return path

    def track(self):
        subprocess.run(["git", "add", "--", "content"], cwd=self.root, check=True)

    def exporter(self):
        return Exporter(self.root, self.output, self.docs)

    def manifest(self):
        return json.loads((self.output / MANIFEST).read_text())

    def test_routes_anchors_source_references_and_code_are_preserved(self):
        source = self.write("evidence.md", """# Evidence

[Model](/Review-Space/methodology#model-rules)
[Appendix](/older-route#inputs)
[Index](/Review-Space/appendix)
[Source](https://example.org/article?q=1#part)
[Second heading](/Review-Space/results#result-1)
[Reference][model]

[model]: /Review-Space/methodology#model-rules "Model description"

`[Not a link](/does-not-exist)`
```
[Nor this](/unknown)
```
""")
        self.write("results.md", "# Result\n\n# Result\n")
        original = source.read_bytes()
        result = self.exporter().run()
        self.assertEqual(result["documents"], 3)
        self.assertEqual(result["repository_references"], 1)
        exported = (self.output / "evidence.md").read_text()
        self.assertIn("(modeling.md#model-rules)", exported)
        self.assertIn("../../content/Review%20Space/appendix/_index.md#inputs", exported)
        self.assertIn("(results.md#result-1)", exported)
        self.assertIn('[model]: modeling.md#model-rules "Model description"', exported)
        self.assertIn("`[Not a link](/does-not-exist)`", exported)
        self.assertIn("https://example.org/article?q=1#part", exported)
        self.assertEqual(source.read_bytes(), original)
        self.assertEqual(self.exporter().run(check=True)["status"], "pass")
        self.assertFalse((self.output / "_index.md").exists())

    def test_recursive_assets_svg_counterpart_generator_and_provenance(self):
        self.write("evidence.md", "# Evidence\n\n[Receipt](assets/manifest.json)\n")
        self.write("assets/manifest.json", json.dumps({
            "figures": [{"file": "figure.png", "editable_file": "figure.svg"}],
            "source_receipt": "sources.json",
        }))
        self.write("assets/figure.png", b"PNG bytes")
        self.write("assets/figure.svg", '<svg xmlns="http://www.w3.org/2000/svg"><g id="chart"/></svg>')
        self.write("assets/sources.json", json.dumps({
            "generator": "scripts/figure.py", "inputs_file": "inputs.json",
            "historical_result": {"artifact": "not-delivered.parquet", "sha256": "abc"},
            "pin_relative_path": "data/pins/not-distributed.json",
        }))
        self.write("assets/inputs.json", '{"values": [1, 2]}')
        self.write("scripts/figure.py", "print('figure')\n", root=True)
        result = self.exporter().run()
        self.assertEqual(result["assets"], 6)
        assets = self.output / "assets" / self.directory / "assets"
        exported = json.loads((assets / "sources.json").read_text())
        generator = (assets / exported["generator"]).resolve()
        self.assertEqual(generator.read_text(), "print('figure')\n")
        self.assertTrue(generator.is_relative_to(self.output))
        self.assertEqual(exported["historical_result"]["artifact"], "not-delivered.parquet")
        self.assertEqual((assets / "figure.png").read_bytes(), b"PNG bytes")
        self.assertTrue((assets / "figure.svg").is_file())
        provenance = self.manifest()["upstream_artifacts"]
        self.assertEqual({item["status"] for item in provenance}, {"not-delivered"})
        self.assertEqual(len(provenance), 2)
        self.assertEqual(self.exporter().run(check=True)["status"], "pass")

    def test_frontmatter_becomes_review_heading_without_changing_source_or_routes(self):
        original = '''---
title: "Modeling Avalanche's staking economy"
status: draft
aliases:
  - model-alias
---

## Decisions

[Evidence](/Review-Space/evidence)
'''
        source = self.write("methodology.md", original)
        self.write("evidence.md", "# Evidence\n\n[Model](/model-alias#decisions)\n")
        self.exporter().run()
        exported = (self.output / "modeling.md").read_text()
        self.assertTrue(exported.startswith("# Modeling Avalanche's staking economy\n\n*Draft for review.*\n\n"))
        self.assertIn("## Decisions\n\n[Evidence](evidence.md)", exported)
        self.assertNotIn("title:", exported)
        self.assertNotIn("status: draft", exported)
        self.assertEqual(source.read_text(), original)
        self.assertIn("(modeling.md#decisions)", (self.output / "evidence.md").read_text())
        entry = next(item for item in self.manifest()["files"] if item["source"].endswith("methodology.md"))
        self.assertEqual(entry["source_sha256"], digest(original.encode()))
        self.assertEqual(entry["export_sha256"], digest(exported.encode()))
        self.assertTrue((self.output / "evidence.md").read_text().startswith("# Evidence\n\n[Model]"))
        self.assertEqual(self.exporter().run(check=True)["status"], "pass")

    def test_same_named_assets_from_different_directories_do_not_collide(self):
        self.write("evidence.md", "[A](assets/a/figure.png)\n[B](assets/b/figure.png)\n")
        self.write("assets/a/figure.png", b"one")
        self.write("assets/b/figure.png", b"two")
        self.exporter().run()
        self.assertEqual((self.output / "assets" / self.directory / "assets/a/figure.png").read_bytes(), b"one")
        self.assertEqual((self.output / "assets" / self.directory / "assets/b/figure.png").read_bytes(), b"two")

    def test_embedded_svg_rasters_are_already_delivered(self):
        self.write("evidence.md", "![Image](assets/figure.svg)\n")
        image = '<svg><image href="data:image/png;base64,cG5n"/></svg>'
        self.write("assets/figure.svg", image)
        self.assertEqual(self.exporter().run()["assets"], 1)
        self.assertEqual((self.output / "assets" / self.directory / "assets/figure.svg").read_text(), image)

    def test_executable_url_scheme_is_rejected(self):
        self.write("evidence.md", '[Bad](javascript:alert)\n')
        with self.assertRaisesRegex(ExportError, "unsupported URL scheme"):
            self.exporter().run()

    def test_undefined_reference_and_code_only_anchor_are_rejected(self):
        self.write("evidence.md", "[Missing][undefined]\n")
        with self.assertRaisesRegex(ExportError, "undefined Markdown reference"):
            self.exporter().run()
        self.write("results.md", '# Result\n\n```html\n<div id="only-code"/>\n```\n')
        self.write("evidence.md", "[Missing](/Review-Space/results#only-code)\n")
        with self.assertRaisesRegex(ExportError, "missing fragment"):
            self.exporter().run()

    def test_svg_root_fallback_cannot_create_broken_export_pointer(self):
        self.write("evidence.md", "![Figure](assets/figure.svg)\n")
        self.write("assets/figure.svg", '<svg><image href="images/image.png"/></svg>')
        self.write("images/image.png", b"root image", root=True)
        with self.assertRaisesRegex(ExportError, "SVG dependencies must be relative"):
            self.exporter().run()

    def test_unknown_route_fails_without_writing(self):
        self.write("evidence.md", "[Missing](/Review-Space/missing)\n")
        with self.assertRaisesRegex(ExportError, "unknown or ambiguous route"):
            self.exporter().run()
        self.assertFalse(self.output.exists())

    def test_github_rejected_math_fails_before_writing(self):
        self.write("evidence.md", r"$$\operatorname{Var}(X)=1$$" + "\n")
        with self.assertRaisesRegex(ExportError, "GitHub rejects operatorname"):
            self.exporter().run()
        self.assertFalse(self.output.exists())
        self.write("evidence.md", r"$$\mathrm{Var}(X)=1$$" + "\n")
        self.assertEqual(self.exporter().run()["status"], "pass")

    def test_documented_macro_in_code_is_not_rendered_math(self):
        self.write("evidence.md", r"Use `\operatorname` in TeX." + "\n\n```tex\n"
                   + r"\operatorname{Var}(X)" + "\n```\n")
        self.assertEqual(self.exporter().run()["status"], "pass")

    def test_historical_editions_keep_their_distinct_status(self):
        self.write("evidence.md", '---\ntitle: "Earlier work"\nkind: archival-edition\n---\nHistorical claims.\n')
        self.exporter().run()
        exported = (self.output / "evidence.md").read_text()
        self.assertTrue(exported.startswith("# Earlier work\n\nHistorical claims."))
        self.assertNotIn("Draft for review", exported)

    def test_ambiguous_alias_fails(self):
        self.write("results.md", "---\naliases: [older-route]\n---\n# Result\n")
        self.write("evidence.md", "[Ambiguous](/older-route)\n")
        with self.assertRaisesRegex(ExportError, "unknown or ambiguous route"):
            self.exporter().run()

    def test_missing_fragment_fails(self):
        self.write("evidence.md", "[Missing](/Review-Space/results#not-a-heading)\n")
        with self.assertRaisesRegex(ExportError, "missing fragment"):
            self.exporter().run()

    def test_missing_recursive_dependency_fails_without_writing(self):
        self.write("evidence.md", "[Manifest](assets/manifest.json)\n")
        self.write("assets/manifest.json", '{"editable_file": "missing.svg"}')
        with self.assertRaisesRegex(ExportError, "missing.svg"):
            self.exporter().run()
        self.assertFalse(self.output.exists())

    def test_untracked_other_markdown_reference_fails(self):
        self.write("not-tracked.md", "# Appendix\n")
        self.write("evidence.md", "[Other](/Review-Space/not-tracked)\n")
        with self.assertRaisesRegex(ExportError, "not tracked"):
            self.exporter().run()

    def test_traversal_in_links_and_manifest_pointers_is_rejected(self):
        for href in ("../results.md", "%2e%2e/results.md", "/Review-Space/../results", "..\\results.md"):
            with self.subTest(href=href):
                self.write("evidence.md", f"[Escape]({href})\n")
                with self.assertRaisesRegex(ExportError, "traversal"):
                    self.exporter().run()
        self.write("evidence.md", "[Manifest](assets/manifest.json)\n")
        self.write("assets/manifest.json", '{"file": "../../outside.png"}')
        with self.assertRaisesRegex(ExportError, "traversal"):
            self.exporter().run()

    def test_symlink_escape_and_outside_output_are_rejected(self):
        with tempfile.TemporaryDirectory() as outside:
            external = Path(outside) / "secret.png"
            external.write_bytes(b"outside")
            link = self.root / self.directory / "outside.png"
            link.symlink_to(external)
            self.write("evidence.md", "[Escape](outside.png)\n")
            with self.assertRaisesRegex(ExportError, "escapes project"):
                self.exporter().run()
            with self.assertRaisesRegex(ExportError, "escapes project"):
                Exporter(self.root, Path(outside), self.docs)

    def test_changed_asset_or_source_is_detected_in_check_mode(self):
        self.write("evidence.md", "![Image](assets/image.png)\n")
        self.write("assets/image.png", b"original")
        self.exporter().run()
        exported = self.output / "assets" / self.directory / "assets/image.png"
        exported.write_bytes(b"tampered")
        with self.assertRaisesRegex(ExportError, "missing or changed"):
            self.exporter().run(check=True)
        exported.write_bytes(b"original")
        self.write("assets/image.png", b"new source")
        with self.assertRaisesRegex(ExportError, "missing or changed"):
            self.exporter().run(check=True)

    def test_forged_export_hash_and_mapping_are_detected(self):
        self.exporter().run()
        exported = self.output / "modeling.md"
        exported.write_bytes(b"forged")
        manifest = self.manifest()
        entry = next(item for item in manifest["files"] if item.get("export") == "modeling.md")
        entry["export_sha256"] = digest(b"forged")
        entry["source"] = f"{self.directory}/results.md"
        (self.output / MANIFEST).write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        with self.assertRaisesRegex(ExportError, "missing or changed"):
            self.exporter().run(check=True)

    def test_stale_unlisted_export_file_is_detected(self):
        self.exporter().run()
        (self.output / "stale.png").write_bytes(b"obsolete")
        with self.assertRaisesRegex(ExportError, "unexpected export files"):
            self.exporter().run(check=True)


if __name__ == "__main__":
    unittest.main()
