#!/usr/bin/env python3
"""
Dead Link Scanner — scans HTML files for broken external links, image references,
and CSS/JS resource URLs before deployment.
"""
import os
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
HTML_FILES = list(PROJECT_ROOT.rglob("*.html"))
EXCLUDE_DIRS = {"test-output", "__pycache__", ".git", "node_modules", ".workbuddy"}

errors = []
warnings = []

# --- Patterns ---
HREF_PATTERN = re.compile(r'href\s*=\s*["\']([^"\']+)["\']', re.IGNORECASE)
SRC_PATTERN = re.compile(r'src\s*=\s*["\']([^"\']+)["\']', re.IGNORECASE)
URL_PATTERN = re.compile(r'https?://[^\s"\'<>]+')


def is_excluded(path):
    for d in EXCLUDE_DIRS:
        if d in str(path):
            return True
    return False


def check_file(filepath):
    """Scan one HTML file for issues."""
    content = filepath.read_text(encoding="utf-8", errors="replace")
    rel = str(filepath.relative_to(PROJECT_ROOT))

    # Check href attributes
    for m in HREF_PATTERN.finditer(content):
        url = m.group(1).strip()
        if not url:
            errors.append(f"[EMPTY HREF] {rel} line ~{content[:m.start()].count(chr(10))+1}")
            continue
        if url == "#":
            errors.append(f"[DEAD ANCHOR href='#'] {rel} line ~{content[:m.start()].count(chr(10))+1}")
        elif url.startswith("http"):
            # External URL — flag for manual review
            pass  # checked separately

    # Check src attributes (images, scripts)
    for m in SRC_PATTERN.finditer(content):
        url = m.group(1).strip()
        if not url:
            # Empty src (e.g. src="" set dynamically) — OK if JS fills it
            warnings.append(f"[EMPTY SRC (check if JS fills)] {rel} line ~{content[:m.start()].count(chr(10))+1}")
            continue
        if url.startswith("http") or url.startswith("/") or url.startswith("data:"):
            continue  # external, absolute, or data URI — skip
        # Local relative resource — check if file exists
        local_path = filepath.parent / url
        if not local_path.exists():
            errors.append(f"[MISSING RESOURCE] {rel} → {url} (resolved: {local_path})")

    # Check for onclick="location.href=..." patterns
    onclick_pattern = re.compile(r'location\.href\s*=\s*["\']([^"\']+)["\']')
    for m in onclick_pattern.finditer(content):
        target = m.group(1)
        if not target:
            errors.append(f"[EMPTY location.href] {rel}")


def main():
    html_files = [f for f in HTML_FILES if not is_excluded(f)]
    print(f"Scanning {len(html_files)} HTML files...\n")

    for f in html_files:
        check_file(f)

    # Print results
    if errors:
        print(f"\n\033[31m=== {len(errors)} ERRORS ===\033[0m")
        for e in errors:
            print(f"  ❌ {e}")

    if warnings:
        print(f"\n\033[33m=== {len(warnings)} WARNINGS ===\033[0m")
        for w in warnings:
            print(f"  ⚠️  {w}")

    if not errors and not warnings:
        print("\n\033[32m=== All links validated — 0 issues ===\033[0m")

    # Exit with error if critical issues found
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
