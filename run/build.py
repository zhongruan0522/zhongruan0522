"""Build the profile SVG assets.

Card 1 (profile-details) is downloaded from the public github-profile-summary-cards
API with the transparent theme; cards 2 (languages) and 3 (stats) are rendered from
live GitHub data. Card 4 (snake) is produced by the Platane/snk workflow step, not
here. Any failure aborts the build — stale cards are never silently refreshed.
"""
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

from github_stats import USERNAME, fetch_data
from svg_cards import THEME, languages_card, stats_card

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
PROFILE_DETAILS_API = "https://github-profile-summary-cards.vercel.app/api/cards/profile-details"


def download_profile_details(username):
    """The public API serves the horizontal transparent-theme card directly."""
    url = f"{PROFILE_DETAILS_API}?username={username}&theme=transparent"
    request = urllib.request.Request(url, headers={"User-Agent": f"{username}-profile"})
    with urllib.request.urlopen(request, timeout=60) as response:
        svg = response.read().decode()
    if "</svg>" not in svg or "ERROR!!!" in svg:
        raise RuntimeError(f"profile-details API did not return a usable card for {username}: {svg[:200]}")
    return svg


def main():
    token = os.environ.get("PROFILE_TOKEN")
    if not token:
        raise SystemExit("PROFILE_TOKEN is required: set it to the GitHub token with read access to your organizations")
    username = os.environ.get("GITHUB_USERNAME", USERNAME)

    ASSETS.mkdir(exist_ok=True)
    (ASSETS / "profile-details.svg").write_text(download_profile_details(username), encoding="utf-8")

    data = fetch_data(token, username)
    print(json.dumps(data, ensure_ascii=False)[:500])
    (ASSETS / "languages.svg").write_text(languages_card(THEME, data), encoding="utf-8")
    (ASSETS / "stats.svg").write_text(stats_card(THEME, data), encoding="utf-8")


if __name__ == "__main__":
    main()
