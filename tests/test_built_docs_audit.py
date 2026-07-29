"""Unit tests for documentation rendering regression checks."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def _audit_module():
    path = Path("scripts/check_built_docs.py")
    spec = importlib.util.spec_from_file_location("check_built_docs", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_audit_accepts_prefixed_assets_and_math(tmp_path: Path) -> None:
    module = _audit_module()
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "figure.svg").write_text("<svg></svg>")
    (tmp_path / "javascripts").mkdir()
    (tmp_path / "javascripts" / "mathjax.js").write_text("")
    page = tmp_path / "method" / "index.html"
    page.parent.mkdir()
    page.write_text(
        '<img src="/fipha/assets/figure.svg" alt="Evidence figure">'
        '<script src="/fipha/javascripts/mathjax.js"></script>'
        '<script src="https://cdn.example/tex-mml-chtml.js"></script>'
        '<div class="arithmatex">equation</div>'
    )

    assert module.audit_site(tmp_path, site_prefix="/fipha/") == []


def test_audit_rejects_missing_asset_empty_alt_and_literal_tex(tmp_path: Path) -> None:
    module = _audit_module()
    page = tmp_path / "index.html"
    page.write_text(
        '<img src="assets/missing.svg" alt=""><p>\\mathbf{y} = \\mathbf{A}</p>'
    )

    defects = module.audit_site(tmp_path, site_prefix="/fipha/")

    assert any("missing img asset" in item for item in defects)
    assert any("empty alt text" in item for item in defects)
    assert any("unrendered TeX" in item for item in defects)
