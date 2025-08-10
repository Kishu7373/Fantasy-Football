from typing import Any, Dict, List, Tuple, Optional
import pandas as pd
from utils.api import (
    api_get, normalize_list, fetch_profile, injury_from_profile, weekly_injury_text,
    get_week_opp_and_loc, canon_abv, current_season, datetime, os, re, requests,
)

# Helper function to extract a value from a dictionary using a list of keys.
def _pick(d: dict, keys: List[str]) -> str:
    for k in keys:
        v = d.get(k)
        if v not in (None, ""):
            return v
    return ""

# Helper function to format a date string from YYYYMMDD to a more readable format.
def _fmt_date(yyyymmdd: str) -> str:
    try:
        dt = datetime.strptime(yyyymmdd, "%Y%m%d")
        return dt.strftime("%Y-%m-%d (%a)")
    except Exception:
        return yyyymmdd

# Helper function to normalize team abbreviations.
# This is used to ensure consistent team names across different data sources.
_CANON = {"JAC": "JAX", "WAS": "WSH", "SFO": "SF", "TAM": "TB",
          "NOR": "NO",  "LA": "LAR", "OAK": "LV", "STL": "LAR", "SD": "LAC"}

def _norm(abv: str) -> str:
    a = (abv or "").upper()
    return _CANON.get(a, a)

# Function to build a weekly schedule with betting odds.
# It returns a dictionary containing the season, week, HTML table of the schedule, and a note about missing odds.
def build_week_schedule_with_odds(week: int, season: Optional[str] = None) -> Dict[str, str]:
    season = season or current_season()

    # 1) fetch the schedule for the given week
    sched = api_get("getNFLGamesForWeek", {"season": season, "week": week, "seasonType": "reg"})
    body  = sched.get("body", [])
    games = body if isinstance(body, list) else (body.get("games", []) if isinstance(body, dict) else [])

    schedule_rows: List[Dict[str, str]] = []
    dates_needed: set[str] = set()

    # Helper function to format the game data into a row.
    for g in games:
        home = _norm(_pick(g, ["home", "homeTeam", "homeTeamAbv", "teamHomeAbv"]))
        away = _norm(_pick(g, ["away", "awayTeam", "awayTeamAbv", "teamAwayAbv"]))
        date = _pick(g, ["gameDate", "date"]).strip()
        time = _pick(g, ["gameTime", "time"])
        if home and away and date:
            schedule_rows.append({
                "Date": _fmt_date(date),
                "RawDate": date,
                "Time": time,
                "Away": away,
                "Home": home
            })
            dates_needed.add(date)

    if not schedule_rows:
        return {
            "season": season,
            "week": week,
            "table_html": "<p>No games found for that week.</p>",
            "missing_note": ""
        }

    # 2) fetch betting odds for the dates needed
    # This will create a mapping of (date, away_team, home_team) to their betting odds.
    odds_index: Dict[Tuple[str, str, str], Dict[str, float]] = {}
    date_note: Dict[str, str] = {}  # RawDate -> note

    for d in sorted(dates_needed):
        resp = api_get("getNFLBettingOdds", {"gameDate": d, "itemFormat": "list", "impliedTotals": "true"})
        items = resp.get("body", [])
        if not isinstance(items, list) or len(items) == 0:
            date_note[d] = "Betting odds not yet released for this date."
            continue

        for o in items:
            h = _norm(_pick(o, ["home","homeTeam","homeTeamAbv","teamHomeAbv"]))
            a = _norm(_pick(o, ["away","awayTeam","awayTeamAbv","teamAwayAbv"]))
            def f(x):
                try:
                    return float(str(x).replace("+", "").strip())
                except Exception:
                    return None

            total    = f(_pick(o, ["overUnder","total","ou"]))
            h_spread = f(_pick(o, ["homeSpread","spreadHome","spread"]))
            ml_home  = f(_pick(o, ["homeMoneyline","mlHome","moneylineHome"]))
            ml_away  = f(_pick(o, ["awayMoneyline","mlAway","moneylineAway"]))
            it       = o.get("impliedTotals") or {}
            imp_home = f(_pick(it, ["home","homeImplied"]))
            imp_away = f(_pick(it, ["away","awayImplied"]))

            odds_index[(d, a, h)] = {
                "Spread (Home)": h_spread, "Total (O/U)": total,
                "ML Away": ml_away, "ML Home": ml_home,
                "Imp Away": imp_away, "Imp Home": imp_home
            }

    # 3) format the schedule rows with the betting odds
    # If no odds are available for a game, we provide a default note.
    # This is useful for users to understand that odds are not yet released.
    DEFAULT_NOTE = "Betting odds not yet released."
    out_rows: List[Dict[str, object]] = []

    for s in schedule_rows:
        key = (s["RawDate"], s["Away"], s["Home"])
        o = odds_index.get(key, {})
        date_default = date_note.get(s["RawDate"], "")

        rec = {
            "Date": s["Date"],
            "Time": s["Time"],
            "Away": s["Away"],
            "Home": s["Home"],
            "Spread (Home)": o.get("Spread (Home)"),
            "Total (O/U)":   o.get("Total (O/U)"),
            "ML Away":       o.get("ML Away"),
            "ML Home":       o.get("ML Home"),
            "Imp Away":      o.get("Imp Away"),
            "Imp Home":      o.get("Imp Home"),
            "Note":          date_default,
        }
        if all(rec[k] is None for k in ("Spread (Home)", "Total (O/U)", "ML Away", "ML Home")):
            rec["Note"] = rec["Note"] or DEFAULT_NOTE

        out_rows.append(rec)

    # 4) convert the rows to a DataFrame and then to HTML
    # Utilized ChatGPT to generate the understand how to implement this feature and utilized a similar approach throughout the code.
    df = pd.DataFrame(out_rows).sort_values(["Date", "Time"], na_position="last").reset_index(drop=True)
    table_html = df.to_html(index=False)

    # 5) check for any missing dates where betting odds are not posted yet
    missing_dates = sorted({s["RawDate"] for s in schedule_rows if date_note.get(s["RawDate"])})
    missing_note  = ""
    if missing_dates:
        pretty = ", ".join(_fmt_date(d) for d in missing_dates)
        missing_note = f"Note: Betting odds aren’t posted yet for: {pretty}. They often appear closer to game week."

    return {
        "season": season,
        "week": week,
        "table_html": table_html,
        "missing_note": missing_note
    }
