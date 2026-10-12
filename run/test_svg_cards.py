"""Render both custom cards against sample data and check layout invariants.
Run: python3 run/test_svg_cards.py"""
import xml.etree.ElementTree as ET
from pathlib import Path

from svg_cards import THEME, languages_card, stats_card

DATA = {"contributions": 1027, "commits": 410, "merged_prs": 71,
        "patches_by_repo": [["magpie", 6]],
        "repositories": 12, "stars": 48, "contributed_to": 12, "followers": 6,
        "languages": [["TypeScript", 36.0], ["Python", 22.3], ["JavaScript", 14.2],
                      ["Go", 9.1], ["Java", 7.0], ["Rust", 4.4], ["Vue", 3.1],
                      ["Other", 3.9]]}

s = languages_card(THEME, DATA)
assert "LANGUAGES" in s and "repositories and organizations" in s, s[:400]
assert s.count("<rect") == len(DATA["languages"]) + 1, "one segment per language (+1 clip rect)"
assert "TypeScript 36%" in s and "Other 3.9%" in s, s
ET.fromstring(s)  # well-formed XML

# 8 legend entries must wrap to a second row instead of overflowing the 880px canvas
assert s.count('cy="90.0"') >= 1 and s.count('cy="114.0"') >= 1, "legend did not wrap"

s = stats_card(THEME, DATA)
for label in ("Total Stars Earned", "Total Contributions (last year)", "Total Commits (last year)",
              "Merged Pull Requests", "Upstream Patch Commits", "Contributed to (last year)"):
    assert label in s, label
assert "Followers" not in s and "repositories" not in s.lower(), s
assert "<image" not in s, "no character art in the trimmed card"
assert "third-party repos" not in s and ">maka<" not in s, "per-repo bars removed"
assert 'stroke-dasharray' in s and "rank A · 77 pts" in s, s  # 71 PRs + 6 patches = A
ET.fromstring(s)

no_patches = {k: v for k, v in DATA.items() if k != "patches_by_repo"}
s = stats_card(THEME, no_patches)
assert "Upstream Patch Commits" not in s and "rank A · 71 pts" in s, s

print("all card assertions passed")
Path("build-test.svg").write_text(s, encoding="utf-8")
Path("build-test.svg").unlink()
