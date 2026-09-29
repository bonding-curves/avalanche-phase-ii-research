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
        study_page = root / "content/Phase II/Essential Readings/Source/index.md"
        source_page = study_page.parent / "Source Article.md"
        component = study_page.parent / "Reproduction.md"
        source_page.parent.mkdir(parents=True)
        source_page.write_text('---\ntitle: "Source Article"\n---\n\n# Source title\n')
        component.write_text("---\ntitle: Reproduction\n---\n")
        registry = {
            "schema_version": "research-navigation/v3",
            "sources": [{"id": "lit:source", "title": "Source title", "source_type": "article", "canonical_url": "https://example.com/source", "local_page": source_page.relative_to(root).as_posix()}],
            "collections": [{"id": "collection:readings", "title": "Essential Readings", "collection_type": "curated_reading_list", "description": "Fixture", "source_ids": ["lit:source"], "index": "content/Phase II/Essential Readings/index.md"}],
            "studies": [{"id": "study:source", "source_id": "lit:source", "collection_id": "collection:readings", "page": study_page.relative_to(root).as_posix(), "components": [{"title": "Reproduction", "page": component.relative_to(root).as_posix()}]}],
        }
        registry_path = root / "registry.json"
        registry_path.write_text(json.dumps(registry))
        return registry, registry_path

    def test_builds_one_combined_collection_and_source_package(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _, registry_path = self.fixture(root)
            report = collection_navigation.result("build", root, registry_path)
            self.assertEqual(report["status"], "pass")
            self.assertEqual(report["coverage"], [{"collection_id": "collection:readings", "members": 1, "local_editions": 1, "studies": 1}])
            collection_text = (root / "content/Phase II/Essential Readings/index.md").read_text()
            self.assertIn("title: Essential Readings", collection_text)
            self.assertIn("[Source title](/Phase-II/Essential%20Readings/Source/) · Article", collection_text)
            package_text = (root / "content/Phase II/Essential Readings/Source/index.md").read_text()
            self.assertIn("[Source Article](/Phase-II/Essential%20Readings/Source/Source%20Article)", package_text)
            self.assertIn("[Reproduction](/Phase-II/Essential%20Readings/Source/Reproduction)", package_text)
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
            source_page = root / registry["sources"][0]["local_page"]
            source_page.write_text('---\ntitle: "Different title"\n---\n')
            with self.assertRaises(collection_navigation.RegistryError):
                collection_navigation.validate(registry, root)

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
            source_page = root / registry["sources"][0]["local_page"]
            source_page.write_text('---\ntitle: "Source Model Artifact"\n---\n')
            (root / "registry.json").write_text(json.dumps(registry))
            self.assertEqual(collection_navigation.result("build", root, root / "registry.json")["status"], "pass")


if __name__ == "__main__":
    unittest.main()
