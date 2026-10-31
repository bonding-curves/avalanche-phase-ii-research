"""Exercise source fidelity and publication distinctions on the delivered archive."""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from research_history import DIRECTORY, START, verify

ROOT = Path(__file__).resolve().parents[1]


class HistoricalEditionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.manifest = json.loads((ROOT / DIRECTORY / "manifest.json").read_text())
        names = {f"{DIRECTORY}/manifest.json"}
        for entry in self.manifest["entries"]:
            names.add(entry["page"])
            if entry["original"]:
                names.add(entry["original"])
            names.update(asset["file"] for asset in entry["assets"])
        for name in names:
            destination = self.root / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, destination)

    def entry(self, form):
        return next(e for e in self.manifest["entries"] if e.get("source_form", "original") == form)

    def test_complete_collection_distinguishes_supplied_source_forms(self):
        result = verify(self.root)
        self.assertEqual(result["entries"], 8)
        self.assertEqual(result["figures"], 12)
        self.assertEqual(result["source_forms"], {"original": 4, "redacted": 3, "metadata-only": 1})

    def test_redacted_text_tampering_fails(self):
        source = self.root / self.entry("redacted")["original"]
        source.write_bytes(source.read_bytes() + b"additional assertion\n")
        with self.assertRaisesRegex(ValueError, "original bytes differ"):
            verify(self.root)

    def test_removing_visible_redaction_status_fails(self):
        page = self.root / self.entry("redacted")["page"]
        page.write_text(page.read_text().replace("Redacted source edition", "Source text"))
        with self.assertRaisesRegex(ValueError, "redacted status"):
            verify(self.root)

    def test_metadata_record_cannot_silently_gain_a_source_body(self):
        page = self.root / self.entry("metadata-only")["page"]
        page.write_text(page.read_text() + START + "unqualified claims\n")
        with self.assertRaisesRegex(ValueError, "must not contain an original body"):
            verify(self.root)

    def test_metadata_only_status_must_remain_visible(self):
        page = self.root / self.entry("metadata-only")["page"]
        page.write_text(page.read_text().replace("Metadata record only", "Earlier research"))
        with self.assertRaisesRegex(ValueError, "must be visible"):
            verify(self.root)

    def test_changed_historical_figure_route_fails(self):
        entry = next(e for e in self.manifest["entries"] if e["assets"])
        page = self.root / entry["page"]
        page.write_text(page.read_text().replace("/figures/07-differential-spec.png", "/figures/missing.png"))
        with self.assertRaisesRegex(ValueError, "figure routes differ"):
            verify(self.root)

    def test_source_identity_mismatch_fails(self):
        entry = self.entry("metadata-only")
        page = self.root / entry["page"]
        page.write_text(page.read_text().replace(entry["id"], "00000000-0000-0000-0000-000000000000"))
        with self.assertRaisesRegex(ValueError, "source identity differs"):
            verify(self.root)


if __name__ == "__main__":
    unittest.main()
