import time
from datetime import datetime
from typing import Any, Dict, List, Tuple
import pandas as pd
from utils.api import api_get, current_season

# Provided constants to the module to configure behavior.
# Primarily to ensure faster processing during development.
# May be adjusted in production.
# TOP_SCAN is how many ADP players to scan for injuries.
# MAX_RESULTS is the maximum number of results to return.
TOP_SCAN = 50          # Provides information on the top 50 players by ADP
MAX_RESULTS = 25       # Limits the number of injury results to 25

# Ran into issues with the API returning inconsistent data due to name formatting.
# Utilized ChatGPT to create a slug function that normalizes player names and avoids common pitfalls.
# This function converts names to lowercase, removes punctuation, and replaces spaces with hyphens.
def _to_slug(name: str) -> str:
    s = name.lower()
    for ch in [".", ",", "'"]:
        s = s.replace(ch, "")
    s = " ".join(s.split())
    return s.replace(" ", "-")

# The API has various injury-related data fields, thus, we need to allow all information to be returned.
# This function extracts the injury text from a player's profile.
# It checks for the presence of "description", "designation", or "status" fields.
def _injury_text_from_profile(profile: Dict[str, Any]) -> str:
    if not isinstance(profile, dict):
        return ""
    inj = profile.get("injury") or {}
    if not isinstance(inj, dict):
        return ""
    return (inj.get("description") or inj.get("designation") or inj.get("status") or "").strip()

# This function fetches a player's profile using their name.
# It uses the API to get player information and returns the first profile found.
# If no profile is found, it returns an empty dictionary.
def _fetch_profile(player_name: str) -> Dict[str, Any]:
    try:
        raw = api_get("getNFLPlayerInfo", {"playerName": _to_slug(player_name), "getStats": "false"})
        body = raw.get("body", [])
        return body[0] if isinstance(body, list) and body else {}
    except Exception:
        return {}

# This function parses the teams list from the API response.
# It checks if the response is a dictionary or a list and extracts the "teams" field
# if it exists. If the response is not in the expected format, it returns an empty list.
def _parse_teams_list(tdata: Any) -> List[Dict[str, Any]]:
    if isinstance(tdata, dict):
        body = tdata.get("body", tdata)
        if isinstance(body, dict) and isinstance(body.get("teams"), list):
            return body["teams"]
        if isinstance(body, list):
            return body
    if isinstance(tdata, list):
        return tdata
    return []


# This function builds an HTML table of injuries for the top N players by ADP.
# It fetches the current season, retrieves the ADP list, and scans the top players
def build_injury_table() -> Tuple[str, str, int, int, int, float]:
    season = current_season()
    t0 = time.time()

    # Use the API to get the ADP list for the current season.
    # The API returns a list of players with their ADP rankings.
    # We limit the scan to the top TOP_SCAN players.
    adp = api_get("getNFLADP", {"season": season, "adpType": "standard"})
    adp_list = (adp.get("body", {}) or {}).get("adpList", [])[:TOP_SCAN]
    names = [p.get("longName") or p.get("name") for p in adp_list if (p.get("longName") or p.get("name"))]

    rows: List[Dict[str, str]] = []
    for nm in names:
        prof = _fetch_profile(nm)
        txt = _injury_text_from_profile(prof)
        if txt:
            rows.append({"Player": nm, "Injury": txt})
            if len(rows) >= MAX_RESULTS:
                break

    if rows:
        df = (
            pd.DataFrame(rows)
            .drop_duplicates(subset=["Player"])
            .sort_values("Player")
            .reset_index(drop=True)
        )
        table_html = df.to_html(index=False, escape=False)
    else:
        table_html = "<p>No injury descriptions found in the scanned range.</p>"

    elapsed = round(time.time() - t0, 2)
    return (table_html, season, TOP_SCAN, MAX_RESULTS, len(rows), elapsed)

# This function builds a small HTML card for a player, including their name, team, jersey number, position, photo, and injury status.
# If the player cannot be found, it returns a message indicating that.
def build_player_card(name: str) -> str:
    prof = _fetch_profile(name)
    if not prof:
        return f'<div class="note">Sorry — couldn’t find “{name}”.</div>'

    team_abv = (prof.get("team") or prof.get("teamAbv") or "").upper()
    jersey = prof.get("jerseyNum") or prof.get("number") or ""
    pos = prof.get("pos") or prof.get("position") or ""
    photo = prof.get("espnHeadshot") or ""
    injury = _injury_text_from_profile(prof) or "(none listed)"
    full_name = prof.get("longName") or prof.get("espnName") or name

    # Due to various team name formats, we need to normalize the team abbreviation to get a constant team name.
    tdata = api_get("getNFLTeams", {"teamStats": "false"})
    teams = _parse_teams_list(tdata)
    tmap = {
        (t.get("teamAbv") or "").upper(): (t.get("teamName") or t.get("teamAbv") or "")
        for t in teams if isinstance(t, dict)
    }
    team_full = tmap.get(team_abv, team_abv)

    img_html = f'<img src="{photo}" width="90" style="border-radius:6px;margin-right:10px">' if photo else ""
    html = f"""
    <div class="card" style="display:flex;align-items:center;gap:10px;padding:10px;border:1px solid #ddd;border-radius:8px;">
      {img_html}
      <div>
        <div><strong>{full_name}</strong>{' — ' + pos if pos else ''}{(' #' + str(jersey)) if jersey else ''}</div>
        <div>{team_full} {f"({team_abv})" if team_abv else ""}</div>
        <div style="margin-top:4px;"><em>{injury}</em></div>
      </div>
    </div>
    """
    return html.strip()