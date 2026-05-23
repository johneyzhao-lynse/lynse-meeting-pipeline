import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class ManifestAssetsTest(unittest.TestCase):
    def test_template_manifest_has_required_fallback_and_known_templates(self):
        data = json.loads((ROOT / "assets/manifests/template_manifest.json").read_text(encoding="utf-8"))
        names = {item["name"] for item in data["templates"]}
        fallback = [item for item in data["templates"] if item.get("default_for_fallback")]
        self.assertIn("general-meeting.md", names)
        self.assertIn("insurance-claim-communication.md", names)
        self.assertEqual([item["name"] for item in fallback], ["general-meeting.md"])

    def test_industry_manifest_has_known_industries_and_sensitive_risk(self):
        data = json.loads((ROOT / "assets/manifests/industry_manifest.json").read_text(encoding="utf-8"))
        names = {item["name"] for item in data["industries"]}
        self.assertIn("insurance-industry.md", names)
        self.assertNotIn("sensitive-content-neutral-summary.md", names)
