#!/usr/bin/env python3
"""
Anchor Validator — checks that all <a href="#id"> links have matching id="" elements.
Also verifies no empty/dead anchor patterns exist.
"""
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
HTML_FILES = list(PROJECT_ROOT.rglob("*.html"))
EXCLUDE_DIRS = {"test-output", "__pycache__", ".git", "node_modules", ".workbuddy"}
EXCLUDE_PATTERNS = ["backup", "_backup", "fixed-backup"]


def is_excluded(path):
    name = path.name.lower()
    for d in EXCLUDE_DIRS:
        if d in str(path):
            return True
    for p in EXCLUDE_PATTERNS:
        if p.lower() in name:
            return True
    return False


def validate(filepath):
    content = filepath.read_text(encoding="utf-8", errors="replace")
    rel = str(filepath.relative_to(PROJECT_ROOT))

    # Collect all IDs in the file
    id_pattern = re.compile(r'\bid\s*=\s*["\']([^"\']+)["\']', re.IGNORECASE)
    all_ids = set(m.group(1) for m in id_pattern.finditer(content))

    # Collect all fragment links
    anchor_pattern = re.compile(r'href\s*=\s*["\']#([^"\']*)["\']', re.IGNORECASE)
    anchors = [m.group(1) for m in anchor_pattern.finditer(content)]

    errors = []
    for anchor in anchors:
        if not anchor:
            errors.append(f"[EMPTY ANCHOR] href='#' at {rel}")
        elif anchor not in all_ids:
            errors.append(f"[BROKEN ANCHOR] #{anchor} not found in {rel}")

    if errors:
        print(f"\n\033[31m{rel}: {len(errors)} anchor issues\033[0m")
        for e in errors:
            print(f"  ❌ {e}")
        return errors

    return []


def main():
    html_files = [f for f in HTML_FILES if not is_excluded(f)]
    all_errors = []

    for f in html_files:
        all_errors.extend(validate(f))

    total_ids = sum(len(set(
        re.findall(r'\bid\s*=\s*["\']([^"\']+)["\']',
                   f.read_text(encoding="utf-8", errors="replace"), re.IGNORECASE)
    )) for f in html_files)

    total_anchors = sum(len(
        re.findall(r'href\s*=\s*["\']#[^"\']*["\']',
                   f.read_text(encoding="utf-8", errors="replace"), re.IGNORECASE)
    ) for f in html_files)

    print(f"\n📊 Stats: {total_ids} IDs, {total_anchors} anchors across {len(html_files)} files")

    if all_errors:
        print(f"\n\033[31m=== {len(all_errors)} anchor errors found ===\033[0m")
        sys.exit(1)
    else:
        print("\n\033[32m=== All anchors validated — 0 issues ===\033[0m")


if __name__ == "__main__":
    main()
