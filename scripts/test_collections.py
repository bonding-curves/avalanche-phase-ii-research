import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parent / "research_navigation.py"
SPEC = importlib.util.spec_from_file_location("research_collections", MODULE_PATH)
assert SPEC and SPEC.loader
collection_navigation = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(collection_navigation)


class CollectionNavigationTest(unittest.TestCase):
    def fixture(self, root: Path) -> tuple[dict, Path]:
        source_page = root / "content/Wiki/Avalanche/Essential Readings/Source/index.md"
        study_page = root / "content/Phase II/Studies/Essential Readings/Source/index.md"
        component = study_page.parent / "Reproduction.md"
        source_page.parent.mkdir(parents=True)
        study_page.parent.mkdir(parents=True)
        source_page.write_text('---\ntitle: "Source title"\n---\n\n# Source title\n\n/Phase-II/Studies/Essential%20Readings/Source/\n')
        study_page.write_text('---\ntitle: "Source title"\n---\n\n# Source title\n\n/Wiki/Avalanche/Essential%20Readings/Source/\n')
        component.write_text("---\ntitle: Reproduction\n---\n")
        registry = {
            "schema_version": "research-navigation/v2",
            "sources": [{"id": "lit:source", "title": "Source title", "source_type": "article", "canonical_url": "https://example.com/source", "local_page": source_page.relative_to(root).as_posix()}],
            "collections": [{"id": "collection:readings", "title": "Essential Readings", "collection_type": "curated_reading_list", "description": "Fixture", "source_ids": ["lit:source"], "wiki_index": "content/Wiki/Avalanche/Essential Readings/index.md", "studies_index": "content/Phase II/Studies/Essential Readings/index.md"}],
            "studies": [{"id": "study:source", "source_id": "lit:source", "collection_id": "collection:readings", "page": study_page.relative_to(root).as_posix(), "components": [{"title": "Reproduction", "page": component.relative_to(root).as_posix()}]}],
        }
        registry_path = root / "registry.json"
        registry_path.write_text(json.dumps(registry))
        return registry, registry_path

    def test_builds_both_contextual_views_from_one_title(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _, registry_path = self.fixture(root)
            report = collection_navigation.result("build", root, registry_path)
            self.assertEqual(report["status"], "pass")
            self.assertEqual(report["coverage"], [{"collection_id": "collection:readings", "members": 1, "local_editions": 1, "studies": 1}])
            for relative in (
                "content/Wiki/Avalanche/Essential Readings/index.md",
                "content/Phase II/Studies/Essential Readings/index.md",
            ):
                text = (root / relative).read_text()
                self.assertIn("title: Essential Readings", text)
            wiki_text = (root / "content/Wiki/Avalanche/Essential Readings/index.md").read_text()
            self.assertIn("[Source title](Source/) · Article", wiki_text)
            studies_text = (root / "content/Phase II/Studies/Essential Readings/index.md").read_text()
            self.assertIn("[Source title](Source/)", studies_text)
            self.assertEqual(collection_navigation.result("check", root, registry_path)["status"], "pass")

    def test_rejects_missing_collection_member(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            registry, _ = self.fixture(root)
            registry["collections"][0]["source_ids"].append("lit:missing")
            with self.assertRaises(collection_navigation.RegistryError):
                collection_navigation.validate(registry, root)

    def test_rejects_source_title_drift(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            registry, _ = self.fixture(root)
            changed = copy.deepcopy(registry)
            changed["sources"][0]["title"] = "Different title"
            with self.assertRaises(collection_navigation.RegistryError):
                collection_navigation.validate(changed, root)

    def test_rejects_unknown_source_type(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            registry, _ = self.fixture(root)
            registry["sources"][0]["source_type"] = "unknown"
            with self.assertRaises(collection_navigation.RegistryError):
                collection_navigation.validate(registry, root)

    def test_allows_local_model_artifact_without_external_url(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            registry, _ = self.fixture(root)
            registry["sources"][0]["source_type"] = "model_artifact"
            registry["sources"][0]["canonical_url"] = None
            (root / "registry.json").write_text(json.dumps(registry))
            self.assertEqual(collection_navigation.result("build", root, root / "registry.json")["status"], "pass")


if __name__ == "__main__":
    unittest.main()
