from __future__ import annotations

import json
from functools import lru_cache

from runtime.assets import ROOT

from .models import (
    IndustryManifest,
    IndustryManifestItem,
    TemplateManifest,
    TemplateManifestItem,
)


TEMPLATE_MANIFEST_PATH = ROOT / "assets" / "manifests" / "template_manifest.json"
INDUSTRY_MANIFEST_PATH = ROOT / "assets" / "manifests" / "industry_manifest.json"


@lru_cache(maxsize=1)
def load_template_manifest() -> TemplateManifest:
    data = json.loads(TEMPLATE_MANIFEST_PATH.read_text(encoding="utf-8"))
    return TemplateManifest(
        templates=[TemplateManifestItem(**item) for item in data["templates"]]
    )


@lru_cache(maxsize=1)
def load_industry_manifest() -> IndustryManifest:
    data = json.loads(INDUSTRY_MANIFEST_PATH.read_text(encoding="utf-8"))
    return IndustryManifest(
        industries=[IndustryManifestItem(**item) for item in data["industries"]]
    )


def get_fallback_template() -> TemplateManifestItem:
    return next(item for item in load_template_manifest().templates if item.default_for_fallback)
