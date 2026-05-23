import unittest

from runtime.classifier.assets import load_industry_manifest, load_template_manifest


class ClassifierAssetsTest(unittest.TestCase):
    def test_load_template_manifest_returns_editable_templates(self):
        manifest = load_template_manifest()
        self.assertTrue(any(item.name == "general-meeting.md" for item in manifest.templates))
        self.assertTrue(all(item.short_description for item in manifest.templates))

    def test_load_industry_manifest_returns_user_visible_summaries(self):
        manifest = load_industry_manifest()
        insurance = next(item for item in manifest.industries if item.name == "insurance-industry.md")
        self.assertIn("保险", insurance.display_name)
        self.assertTrue(insurance.user_visible_summary)
