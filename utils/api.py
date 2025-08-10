# utils/api.py
import os
import re
import requests
from datetime import datetime
from functools import lru_cache
from typing import Dict, List, Tuple, Optional, Any

# API Configuration
# Ensure you have the X_RAPIDAPI_KEY set in your environment or .env file
# Example: export X_RAPIDAPI_KEY="your_api_key_here"
BASE_URL = "https://tank01-nfl-live-in-game-real-time-statistics-nfl.p.rapidapi.com"
API_KEY = os.getenv("X_RAPIDAPI_KEY", "")
HEADERS = {
    "x-rapidapi-host": "tank01-nfl-live-in-game-real-time-statistics-nfl.p.rapidapi.com",
    "x-rapidapi-key": API_KEY or "",
}

# Ensure API_KEY is set before making requests
def _require_key() -> None:
    if not API_KEY:
        raise RuntimeError("X_RAPIDAPI_KEY is not set. Put it in your .env or shell environment.")

# Get the current season year
# This is used to determine the current NFL season based on the year.
def current_season() -> str:
    return str(datetime.today().year)

def api_get(ep: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    _require_key()
    r = requests.get(f"{BASE_URL}/{ep}", headers=HEADERS, params=params or {}, timeout=20)
    r.raise_for_status()
    return r.json()

# Canonical team abbreviations and aliases
# This dictionary maps common team abbreviations to their canonical forms.
# It helps in normalizing team codes across different feeds and aliases.
CANON = {"JAC":"JAX","WAS":"WSH","SFO":"SF","TAM":"TB","NOR":"NO","LA":"LAR","OAK":"LV","STL":"LAR","SD":"LAC"}

def canon_abv(abv: str, known: Optional[set] = None) -> str:
    a = (abv or "").upper()
    a = CANON.get(a, a)
    if known and a not in known:
        return CANON.get(a, a)
    return a

# Expand team abbreviations to include aliases
def expand_aliases(abv: str) -> set:
    a = (abv or "").upper()
    outs = {a}
    for k, v in CANON.items():
        if v == a:
            outs.add(k)
        if k == a:
            outs.add(v)
    return outs

# Normalize a team abbreviation by removing common prefixes and suffixes
def normalize_list(raw, key: str | None = None):
    if isinstance(raw, dict):
        body = raw.get("body", raw)
        if key and isinstance(body, dict):
            items = body.get(key, [])
        elif isinstance(body, list):
            items = body
        else:
            items = raw.get(key, []) if key else []
    elif isinstance(raw, list):
        items = raw
    else:
        items = []

    # If items are strings, convert them to a dict with teamAbv and teamName
    if items and isinstance(items[0], str):
        return [{"teamAbv": s, "teamName": s} for s in items]
    return items

# Normalize a team abbreviation by removing common prefixes and suffixes
def _to_float(x) -> Optional[float]:
    try:
        return float(x)
    except Exception:
        return None

def _parse_points(obj: Dict[str, Any], scoring: str) -> Optional[float]:
    if not isinstance(obj, dict):
        return None

    # Check for fantasyPoints field
    if "fantasyPoints" in obj:
        v = _to_float(obj.get("fantasyPoints"))
        if v is not None:
            return v

    # Check for fantasyPointsDefault field
    # This field can be a dict with multiple scoring formats
    fpd = obj.get("fantasyPointsDefault")
    if isinstance(fpd, dict):
        for key in [scoring, "PPR", "standard", "halfPPR", "HalfPPR", "Default"]:
            if key in fpd:
                v = _to_float(fpd.get(key))
                if v is not None:
                    return v
    else:
        v = _to_float(fpd)
        if v is not None:
            return v

    # Check for fantasyPointsPPR, fantasyPointsHalfPPR, fantasyPointsStandard
    for k in ["fantasyPointsPPR", "fantasyPointsHalfPPR", "fantasyPointsStandard"]:
        v = _to_float(obj.get(k))
        if v is not None:
            return v
    return None

# Generate slug candidates for a player's name
# This function creates a list of potential slugs for a player's name by removing special characters,
# converting to lowercase, and removing common suffixes like "Jr", "Sr", etc
# Utilized ChatGPT to understand how to generate slugs effectively.
_SUFFIXES = {"jr","sr","ii","iii","iv","v","vi"}

def _slug_candidates(name: str) -> List[str]:
    base = re.sub(r"[^\w\s-]", "", (name or "")).strip().lower()
    toks = [t for t in base.split() if t]
    slugs = []
    if toks:
        slugs.append("-".join(toks))
    toks2 = [t for t in toks if t not in _SUFFIXES]
    if toks2 and toks2 != toks:
        slugs.append("-".join(toks2))
    # dedupe
    out, seen = [], set()
    for s in slugs:
        if s not in seen:
            seen.add(s); out.append(s)
    return out

# Considering long loading times, we utilized ChatGPT to understand how to implement this feature to improve user experience.
@lru_cache(maxsize=2048)
def fetch_profile(player_name: str) -> Dict[str, Any]:
    """Best-effort player profile lookup using multiple slugs."""
    for slug in _slug_candidates(player_name):
        try:
            raw = api_get("getNFLPlayerInfo", {"playerName": slug, "getStats": "false"})
            body = raw.get("body", [])
            if isinstance(body, list) and body:
                return body[0]
        except Exception:
            continue
    return {}

# Extracts injury information from a player's profile
def injury_from_profile(bio: Dict[str, Any]) -> str:
    inj = {}
    if isinstance(bio, dict):
        inj = bio.get("injury") or {}
        if not isinstance(inj, dict):
            inj = {}
    return (inj.get("description") or inj.get("designation") or inj.get("status") or "").strip()

def weekly_injury_text(_: Dict[str, Any]) -> str:
    return "(Weekly Information Not Available)"

# Fetches weekly opponent and location information for a given season and week
def get_week_opp_and_loc(season: str, week: int, known_abvs: set) -> Tuple[Dict[str,str], Dict[str,str]]:
    attempts = [
        ("getNFLWeeklySchedule", {"season": season, "week": week}),
        ("getNFLGamesForWeek", {"season": season, "week": week}),
        ("getNFLScoreboard", {"season": season, "week": week}),
    ]
    opp_map, loc_map = {}, {}

    for ep, params in attempts:
        try:
            data = api_get(ep, params)
        except Exception:
            continue

        body = data.get("body", {})
        games = None
        if isinstance(body, dict):
            if isinstance(body.get("games"), list):
                games = body["games"]
            elif isinstance(body.get("weeklySchedule"), list):
                games = body["weeklySchedule"]
        elif isinstance(body, list):
            games = body

        if not games:
            continue

        for g in games:
            ha = g.get("home") or g.get("homeTeam") or g.get("homeTeamAbv") or g.get("homeTeamAbbr")
            aa = g.get("away") or g.get("awayTeam") or g.get("awayTeamAbv") or g.get("awayTeamAbbr")
            if not ha or not aa:
                continue
            home = canon_abv(str(ha), known_abvs)
            away = canon_abv(str(aa), known_abvs)
            for h_al in expand_aliases(home):
                for a_al in expand_aliases(away):
                    opp_map[h_al] = a_al; loc_map[h_al] = "H"
                    opp_map[a_al] = h_al; loc_map[a_al] = "A"
        if opp_map:
            break

    return opp_map, loc_map
