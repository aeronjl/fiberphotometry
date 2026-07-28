"""Fail when a built MkDocs site contains broken local assets or unrendered math."""

from __future__ import annotations

import argparse
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse


class AssetParser(HTMLParser):
    """Collect local assets, image alternatives, and rendered math containers."""

    def __init__(self) -> None:
        super().__init__()
        self.assets: list[tuple[str, str]] = []
        self.images: list[tuple[str, str]] = []
        self.has_math = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        source = values.get("src")
        href = values.get("href")
        if tag in {"img", "script", "source"} and source:
            self.assets.append((tag, source))
        if tag == "link" and href:
            self.assets.append((tag, href))
        if tag == "img" and source:
            self.images.append((source, values.get("alt") or ""))
        classes = set((values.get("class") or "").split())
        self.has_math |= "arithmatex" in classes


def resolve_local_asset(
    *, page: Path, site: Path, reference: str, site_prefix: str
) -> Path | None:
    """Resolve a browser-local reference to its expected built-site path."""
    parsed = urlparse(reference)
    if parsed.scheme or parsed.netloc or reference.startswith(("data:", "//", "#")):
        return None
    path = unquote(parsed.path)
    normalized_prefix = "/" + site_prefix.strip("/") + "/"
    if path.startswith(normalized_prefix):
        return site / path.removeprefix(normalized_prefix)
    if path.startswith("/"):
        return site / path.lstrip("/")
    return page.parent / path


def audit_site(site: Path, *, site_prefix: str) -> list[str]:
    """Return human-readable build defects; an empty list means the audit passed."""
    defects: list[str] = []
    for page in sorted(site.rglob("*.html")):
        parser = AssetParser()
        source = page.read_text(encoding="utf-8", errors="replace")
        parser.feed(source)
        relative_page = page.relative_to(site)
        for tag, reference in parser.assets:
            target = resolve_local_asset(
                page=page,
                site=site,
                reference=reference,
                site_prefix=site_prefix,
            )
            if target is not None and not target.resolve().is_relative_to(
                site.resolve()
            ):
                defects.append(f"{relative_page}: {tag} escapes site root: {reference}")
            elif target is not None and not target.exists():
                defects.append(f"{relative_page}: missing {tag} asset: {reference}")
        for reference, alternative in parser.images:
            if not alternative.strip():
                defects.append(
                    f"{relative_page}: image has empty alt text: {reference}"
                )
        if parser.has_math and (
            "tex-mml-chtml.js" not in source or "javascripts/mathjax.js" not in source
        ):
            defects.append(f"{relative_page}: math container has no MathJax scripts")
        literal_tex = re.search(
            r"<p>[^<]*(?:\\mathbf|\\mathrm|\\times)[^<]*</p>", source
        )
        if literal_tex:
            defects.append(f"{relative_page}: probable unrendered TeX in paragraph")
    return defects


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("site", type=Path)
    parser.add_argument("--site-prefix", default="/fiberphotometry/")
    args = parser.parse_args()
    defects = audit_site(args.site, site_prefix=args.site_prefix)
    if defects:
        raise SystemExit("\n".join(defects))
    print(f"documentation asset and math audit passed: {args.site}")


if __name__ == "__main__":
    main()
