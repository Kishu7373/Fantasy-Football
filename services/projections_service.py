import math
import re
from functools import lru_cache
import pandas as pd
from utils.api import api_get, normalize_list, current_season, canon_abv, _parse_points

# Due to various team abbreviations, we use a canonical mapping
# This helps to standardize team abbreviations across different data sources.
# For example, "JAC" is often used for Jacksonville Jaguars, but we prefer "JAX".
CANON = {"JAC":"JAX","WAS":"WSH","SFO":"SF","TAM":"TB","NOR":"NO","LA":"LAR","OAK":"LV","STL":"LAR","SD":"LAC"}
def _norm(abv: str) -> str:
    a = (abv or "").upper()
    return CANON.get(a, a)

# This function parses the scoring settings and returns a dictionary of scoring knobs.
# It handles different scoring types like PPR, Half-PPR, and Standard.
# The returned dictionary contains scoring values for various actions like passing yards, rushing yards, etc.
def _scoring_knobs(scoring: str) -> dict:
    s = (scoring or "").lower()
    if s == "ppr":
        ppr = 1.0
    elif s in ("halfppr", "half_ppr", "half-ppr"):
        ppr = 0.5
    else:
        ppr = 0.0
    return {
        "pointsPerReception": ppr,
        "twoPointConversions": 2, "passYards": 0.04, "passTD": 4,
        "passCompletions": 1,  "passInterceptions": -2,
        "rushYards": 0.1,  "rushTD": 6,
        "receivingYards": 0.1,  "receivingTD": 6, "fumbles": -2,
        "fgMade": 3, "fgMissed": -1, "xpMade": 1, "xpMissed": -1
    }

# This function generates a slug for a player's name.
# It removes special characters, converts to lowercase, and handles common suffixes like "Jr", "Sr", etc.
# The function returns a list of candidate slugs that can be used for API queries.
SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v", "vi"}

def _slug_candidates(name: str) -> list[str]:
    base = re.sub(r"[^\w\s-]", "", (name or "")).strip().lower()
    toks = [t for t in base.split() if t]
    out = []
    if toks: out.append("-".join(toks))
    no_suf = [t for t in toks if t not in SUFFIXES]
    if no_suf and no_suf != toks:
        out.append("-".join(no_suf))
    seen, dedup = set(), []
    for s in out:
        if s not in seen:
            seen.add(s); dedup.append(s)
    return dedup

# This function fetches a player's profile using their name.
# It tries multiple slug candidates to find the best match.
# The function caches results to improve performance for frequently queried players.
# Considering long loading times, we utilized ChatGPT to understand how to implement this feature to improve user experience.
@lru_cache(maxsize=2048)
def _fetch_profile(player_name: str) -> dict:
    for slug in _slug_candidates(player_name):
        try:
            raw = api_get("getNFLPlayerInfo", {"playerName": slug, "getStats": "false"})
            body = raw.get("body", [])
            if isinstance(body, list) and body:
                return body[0]
        except Exception:
            continue
    return {}

# This function fetches the weekly opponent and location for a given season and week.
# It tries multiple API endpoints to find the schedule data.
def _week_opp_and_loc(season: str, week: int):
    attempts = [
        ("getNFLWeeklySchedule", {"season": season, "week": week}),
        ("getNFLGamesForWeek",   {"season": season, "week": week}),
        ("getNFLScoreboard",     {"season": season, "week": week}),
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
            ha = _norm(g.get("home") or g.get("homeTeam") or g.get("homeTeamAbv") or g.get("homeTeamAbbr"))
            aa = _norm(g.get("away") or g.get("awayTeam") or g.get("awayTeamAbv") or g.get("awayTeamAbbr"))
            if not ha or not aa:
                continue
            opp_map[ha] = aa;  loc_map[ha] = "H"
            opp_map[aa] = ha;  loc_map[aa] = "A"
        if opp_map:
            break
    return opp_map, loc_map

# This function normalizes a team abbreviation to its canonical form.
# It uses the CANON mapping to ensure consistent team abbreviations.
def _team_maps():
    teams_raw = api_get("getNFLTeams", {"teamStats":"false"})
    all_teams = normalize_list(teams_raw, key="teams")
    team_map  = { (t.get("teamAbv") or "").upper(): t.get("teamName", t.get("teamAbv",""))
                  for t in all_teams if isinstance(t, dict) }
    known_abv = set(team_map.keys())
    name_to_abv = { v: k for k, v in team_map.items() }
    nickname_to_abv = {}
    for abv, full in team_map.items():
        nick = full.split()[-1].lower()
        nickname_to_abv[nick] = abv
    return team_map, known_abv, name_to_abv, nickname_to_abv

# This function infers the team abbreviation from a player's name, specifically for DST players (i.e., Defense/Special Teams).
# It checks if the name contains "DST" and tries to find a matching team abbreviation.
# If the name does not contain "DST", it returns None.
def _infer_abv_from_dst(name: str, name_to_abv: dict, nickname_to_abv: dict):
    if not name or "dst" not in name.lower(): 
        return None
    base = name.replace(" DST","").strip()
    if base in name_to_abv:
        return name_to_abv[base]
    nick = base.split()[-1].lower()
    return nickname_to_abv.get(nick)

# This function calculates the projected points for a player based on their profile and the scoring settings.
# It fetches the player's profile, checks if they are a DST player, and retrieves their projected points.
# If the player is a DST, it looks for the team abbreviation and fetches the projected points for that team.
# If the player is not found or has no projections, it returns 0.0.
def _proj_points_for(pl, week, season, scoring, team_abv, known_abvs):
    pts = 0.0
    try:
        knobs = _scoring_knobs(scoring)
        pay = {"week": week, "archiveSeason": season, **knobs}
        resp = api_get("getNFLProjections", pay).get("body", {}) or {}

        if pl["pos"] == "DST" and team_abv:
            tdp = resp.get("teamDefenseProjections")
            candidates = []
            if isinstance(tdp, dict):
                candidates = [v for v in tdp.values() if isinstance(v, dict)]
            elif isinstance(tdp, list):
                candidates = tdp

            target = None
            for it in candidates:
                abv_item = canon_abv(_norm(str(it.get("teamAbv","")).upper()), known_abvs)
                if abv_item == team_abv:
                    target = it; break
            if target:
                val = _parse_points(target, scoring)
                if val is not None:
                    pts = float(val)
        else:
            if pl["playerID"]:
                pj = (resp.get("playerProjections", {}) or {}).get(pl["playerID"], {})
                val = _parse_points(pj, scoring)
                if val is not None:
                    pts = float(val)
    except Exception:
        pts = 0.0
    return round(pts, 2)

# This function builds player projections for a fantasy football team.
# It generates a draft log, roster, projections, starters, and totals for the specified team.
# It uses various helper functions to fetch player profiles, team maps, and weekly opponents.
def build_projections(n_teams: int, slot: int, wk: int, scoring: str, season: str | None = None):
    season = season or current_season()

    # 1) ADP (Average Draft Position)
    adp_raw  = api_get("getNFLADP", {"season": season, "adpType": scoring})
    adp_list = normalize_list(adp_raw, key="adpList")

    positions = ["QB","RB","WR","TE","K","DST"]
    buckets   = {p:[] for p in positions}
    for p in adp_list:
        rp = (p.get("posADP") or "").upper()
        pos = "DST" if rp.startswith("DST") or rp == "DEF" else ("K" if rp.startswith("PK") or rp.startswith("K") else rp[:2])
        if pos in buckets:
            buckets[pos].append({
                "name":     p.get("longName","<none>"),
                "adp":      float(p.get("overallADP") or 0),
                "playerID": p.get("playerID"),
                "pos":      pos
            })

    # Ensure all positions have at least one player
    # If a position is missing, we add a default player with a placeholder ADP.
    def fallback(pos, adp_default):
        teams = normalize_list(api_get("getNFLTeams", {"teamStats":"false"}), key="teams")[:n_teams]
        for t in teams:
            abv = (t.get("teamAbv") or "UNK").upper()
            label = f"{t.get('teamName', abv)} {'DST' if pos=='DST' else 'K'}"
            buckets[pos].append({"name": label, "adp": adp_default, "playerID": None, "pos": pos})
    if not buckets["DST"]: fallback("DST", 200.0)
    if not buckets["K"]:   fallback("K",   180.0)

    # 2) Draft log (simulated draft)
    # This section simulates a draft log for the specified number of teams and rounds.
    total_picks = n_teams * 15
    limits      = {"QB":1,"RB":2,"WR":3,"TE":1,"K":1,"DST":1}
    rosters     = {i:[] for i in range(1, n_teams+1)}
    draft_log   = []

    for pick in range(total_picks):
        rnd  = pick // n_teams + 1
        idx  = pick % n_teams + 1
        team = idx if rnd % 2 else (n_teams + 1 - idx)

        # Select a player for the current pick
        choices=[]
        for pos,cap in limits.items():
            have=sum(1 for pl in rosters[team] if pl["pos"]==pos)
            if have<cap and buckets[pos]:
                choices.append(buckets[pos][0])
        if choices:
            sel = min(choices, key=lambda x:x["adp"])
        else:
            all_rem = [pl for p in positions for pl in buckets[p]]
            sel = min(all_rem, key=lambda x:x["adp"])

        buckets[sel["pos"]].remove(sel)
        rosters[team].append(sel)
        draft_log.append([rnd, pick+1, team, sel["pos"], sel["name"]])

    df_log = pd.DataFrame(draft_log, columns=["Round","Pick#","Team","Pos","Player"])
    draft_log_html = df_log.to_html(index=False)

    # 3) Team maps and weekly opponent/location
    # This section fetches team maps and weekly opponent/location data.
    team_map, known_abvs, name_to_abv, nickname_to_abv = _team_maps()
    opp_map, loc_map = _week_opp_and_loc(season, wk)

    # 4) Roster for the specified slot and provides player details and images.
    # This section builds the roster for the specified team slot and includes player details such as position, name, NFL team, photo, and ADP.
    def _nfl_team_for(pl, prof):
        if pl["pos"] == "DST":
            abv = _infer_abv_from_dst(pl["name"], name_to_abv, nickname_to_abv)
            return team_map.get(abv, abv or "")
        abv = (prof.get("team") or "").upper() if isinstance(prof, dict) else ""
        return team_map.get(abv, abv)

    # Utilizes the enumerate function to create a roster HTML table.
    # Referenced ChatGPT for understanding how to use enumerate effectively in this context.
    rows = []
    for i, pl in enumerate(rosters[slot], 1):
        prof = _fetch_profile(pl["name"]) if pl["playerID"] else {}
        img  = prof.get("espnHeadshot", "")
        img_tag = f'<img src="{img}" width="48">' if img else ""
        rows.append({
            "#": i, "Pos": pl["pos"], "Name": pl["name"],
            "NFL Team": _nfl_team_for(pl, prof),
            "Photo": img_tag,
            "ADP (Average Draft Pick)": f"{pl['adp']:.1f}",
        })
    roster_html = pd.DataFrame(rows).to_html(escape=False, index=False)

    # 5) Player projections for the specified week and season.
    # This section calculates the projected points for each player in the roster.
    proj_rows = []
    for pl in rosters[slot]:
        prof = _fetch_profile(pl["name"]) if pl["playerID"] else {}
        # team abv for DSTs / players
        if pl["pos"] == "DST":
            team_abv = _infer_abv_from_dst(pl["name"], name_to_abv, nickname_to_abv)
        else:
            team_abv = (prof.get("team") or "").upper()

        team_abv = canon_abv(_norm(team_abv), known_abvs) if team_abv else ""
        team_name = team_map.get(team_abv, team_abv) if team_abv else ""

        # Determine opponent string
        if team_abv and team_abv in opp_map:
            opp_abv = opp_map[team_abv]
            ha      = loc_map.get(team_abv, "H")
            opp_str = f"@ {team_map.get(opp_abv, opp_abv)}" if ha == "A" else f"vs {team_map.get(opp_abv, opp_abv)}"
        elif team_abv:
            opp_str = "Bye Week"
        else:
            opp_str = "Bye Week"

        # Determine projected points for the player including DST handling and Bye Week
        if opp_str == "Bye Week":
            pts = 0.0
        else:
            pts = _proj_points_for(pl, wk, season, scoring, team_abv, known_abvs)

        proj_rows.append({
            "Player": pl["name"], "Pos": pl["pos"], "NFL Team": team_name,
            "Opp": opp_str, "ProjPts": pts
        })

    df_proj = pd.DataFrame(proj_rows)
    projections_html = df_proj.to_html(index=False)

    # 6) Starters for the team based on projections.
    # This section selects the top players for each position based on their projected points.
    # It ensures that the number of players selected for each position matches the league's roster requirements
    def pick_top(df, pos, n):
        d = df[df["Pos"]==pos].copy()
        return d.sort_values("ProjPts", ascending=False).head(n)

    starters = []
    for pos, cnt in [("QB",1),("RB",2),("WR",3),("TE",1),("K",1),("DST",1)]:
        for _, r in pick_top(df_proj, pos, cnt).iterrows():
            starters.append({"Pos": r["Pos"], "Player": r["Player"], "NFL Team": r["NFL Team"],
                             "Opp": r["Opp"], "ProjPts": float(r["ProjPts"])})
    df_start = pd.DataFrame(starters)
    starters_html = df_start.to_html(index=False)

    # 7) Totals for the team roster and starters.
    roster_total = float(pd.to_numeric(df_proj["ProjPts"], errors="coerce").fillna(0).sum())
    starter_total = float(pd.to_numeric(df_start["ProjPts"], errors="coerce").fillna(0).sum())
    df_totals = pd.DataFrame([
        {"Group": f"Team {slot} Roster Total",   "ProjPts": round(roster_total, 2)},
        {"Group": f"Team {slot} Starters Total", "ProjPts": round(starter_total, 2)},
    ])
    totals_html = df_totals.to_html(index=False)

    return {
        "draft_log_html": draft_log_html,
        "roster_html": roster_html,
        "projections_html": projections_html,
        "starters_html": starters_html,
        "totals_html": totals_html,
    }
