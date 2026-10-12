"""Build the languages and stats SVG cards.

Card 1 (profile-details) is rendered by the official github-profile-summary-cards
action in the workflow; card 4 (snake) comes from the Platane/snk step — neither
runs here. This script renders cards 2 and 3 from live GitHub data. Any failure
aborts the build — stale cards are never silently refreshed.
"""
import json
import os
from pathlib import Path

from github_stats import USERNAME, fetch_data
from svg_cards import THEME, languages_card, stats_card

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"


def main():
    token = os.environ.get("PROFILE_TOKEN")
    if not token:
        raise SystemExit("PROFILE_TOKEN is required: set it to the GitHub token with read access to your organizations")
    username = os.environ.get("GITHUB_USERNAME", USERNAME)

    data = fetch_data(token, username)
    print(json.dumps(data, ensure_ascii=False)[:500])
    ASSETS.mkdir(exist_ok=True)
    (ASSETS / "languages.svg").write_text(languages_card(THEME, data), encoding="utf-8")
    (ASSETS / "stats.svg").write_text(stats_card(THEME, data), encoding="utf-8")


if __name__ == "__main__":
    main()
