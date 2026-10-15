"""G2 structural checks for Mintlify navigation, page metadata and local links.

This deliberately complements (does not replace) pinned `mint validate`.
Run from any directory: python scripts/docs/validate_public_site.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[2] / "docs" / "public"
TEMPLATE_DIR = ROOT / "_templates"
FRONTMATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)
LINK = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
IMAGE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
TEMPLATE_FAMILIES = {
    "introduction", "beginner-guide", "concept", "api-reference",
    "component-reference", "reproducible-example",
}


def nav_pages(node: object) -> list[str]:
    if isinstance(node, str):
        return [node]
    if isinstance(node, list):
        return [page for item in node for page in nav_pages(item)]
    if isinstance(node, dict):
        return [
            page for key in ("pages", "groups", "tabs", "products", "anchors")
            for page in nav_pages(node.get(key, []))
        ]
    raise ValueError(f"Invalid navigation value: {node!r}")


def check(root: Path = ROOT) -> list[str]:
    problems: list[str] = []
    config = json.loads((root / "docs.json").read_text(encoding="utf-8"))
    if config.get("$schema") != "https://mintlify.com/docs.json":
        problems.append("Missing canonical Mintlify docs.json schema")
    if not all((config.get("name"), config.get("theme"),
                config.get("colors", {}).get("primary"))):
        problems.append("Missing required Mintlify site metadata")
    pages = nav_pages(config.get("navigation", {}))
    if len(pages) != len(set(pages)):
        problems.append("Duplicate navigation slugs")
    if not pages or "introduction" not in pages:
        problems.append("Navigation must include introduction")
    missing_templates = TEMPLATE_FAMILIES - {p.stem for p in (root / "_templates").glob("*.mdx")}
    if missing_templates:
        problems.append(f"Missing page templates: {sorted(missing_templates)}")
    all_pages = sorted(root.rglob("*.mdx"))
    for slug in pages:
        if not (root / (slug + ".mdx")).is_file():
            problems.append(f"Navigation page not found: {slug}")
    for page in all_pages:
        content = page.read_text(encoding="utf-8")
        rel = page.relative_to(root).as_posix()
        match = FRONTMATTER.match(content)
        if not match:
            problems.append(f"{rel}: missing YAML frontmatter")
        else:
            for field in ("title", "description"):
                if not re.search(rf"(?m)^{field}:\s*[^\s].*$", match.group(1)):
                    problems.append(f"{rel}: missing {field}")
        if page.parent != root / "_templates" and "[Write verified" in content:
            problems.append(f"{rel}: unfilled editorial template")
        for alt, _ in IMAGE.findall(content):
            if not alt.strip():
                problems.append(f"{rel}: image without alternative text")
        for destination in LINK.findall(content) + [path for _, path in IMAGE.findall(content)]:
            target = urlsplit(unquote(destination.strip().split()[0]))
            if target.scheme or destination.startswith(("#", "mailto:")):
                continue
            local = target.path
            if not local:
                continue
            if local.startswith("/"):
                candidate = root / local.lstrip("/")
            else:
                candidate = page.parent / local
            choices = [candidate, candidate.with_suffix(".mdx")]
            if not any(p.is_file() for p in choices):
                problems.append(f"{rel}: unresolved local link {destination}")
    for slug in pages:
        if (root / (slug + ".mdx")).is_file() and "_templates" in slug:
            problems.append(f"Editorial template must not be navigable: {slug}")
    return problems


def main() -> None:
    errors = check()
    if errors:
        print("\n".join(errors), file=sys.stderr)
        raise SystemExit(1)
    print("Mintlify structural navigation, frontmatter and local links: PASS")


if __name__ == "__main__":
    main()
