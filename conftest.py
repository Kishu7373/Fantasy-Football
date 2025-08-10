# conftest.py
import os
import pytest
from datetime import datetime

# Ensure nothing in the app prompts for an API key during tests
os.environ.setdefault("X_RAPIDAPI_KEY", "test-key")

from app import create_app

# Data fakes for stubbing API calls
def _fake_teams():
    # Needed to include a few teams for projections page tests
    names = [
        ("KC", "Kansas City Chiefs"),
        ("BUF", "Buffalo Bills"),
        ("DAL", "Dallas Cowboys"),
        ("PHI", "Philadelphia Eagles"),
        ("SF", "San Francisco 49ers"),
        ("CIN", "Cincinnati Bengals"),
        ("JAX", "Jacksonville Jaguars"),
        ("NYJ", "New York Jets"),
        ("LAC", "Los Angeles Chargers"),
        ("LAR", "Los Angeles Rams"),
        ("MIA", "Miami Dolphins"),
        ("DET", "Detroit Lions"),
    ]
    return [{"teamAbv": abv, "teamName": nm} for abv, nm in names]

# Need a good number of players to cover multiple teams and positions
# Utilized ChatGPT to help understand this function as we were having issues with the test not passing nor generating enough players
def _fake_adp(n=120):
    rows = []
    # cycle through positions to get a mix
    pos_cycle = (["RB"]*4 + ["WR"]*4 + ["QB"]*1 + ["TE"]*1 + ["K"]*1 + ["DST"]*1)
    # ensure we have at least n entries
    pnum = 1
    # start ADP at 1.0 and increment for each player
    adp_val = 1.0
    for i in range(n):
        pos = pos_cycle[i % len(pos_cycle)]
        rows.append({
            "longName": f"Player {pnum} {pos}",
            "overallADP": adp_val,
            "playerID": f"{1000+pnum}",
            "posADP": pos,
        })
        pnum += 1
        adp_val += 1.0
    return rows

# Create fake projections loosely based on ADP
# Utilized ChatGPT to help understand how to create this function
def _fake_player_projections(adp_list):
    out = {}
    for row in adp_list:
        pid = str(row["playerID"])
        adp = float(row["overallADP"])
        # Simple formula to create some fantasy points based on ADP
        pts = max(0.0, (200.0 - adp) / 5.0)
        # Round to 2 decimal places for realism
        out[pid] = {
            "fantasyPointsDefault": {
                "standard": round(pts, 2),
                "PPR": round(pts * 1.05, 2),
                "halfPPR": round(pts * 1.025, 2),
            }
        }
    return out

# Simple schedule with a couple of games
def _fake_week_schedule():
    # Week 1 of 2025 season for testing
    return [
        {"homeTeamAbv": "KC",  "awayTeamAbv": "BUF", "gameDate": "20250907", "gameTime": "08:20 PM"},
        {"homeTeamAbv": "DAL", "awayTeamAbv": "PHI", "gameDate": "20250907", "gameTime": "04:25 PM"},
    ]

# A simple fetch function that returns a fixed structure
@pytest.fixture(scope="session")
def app():
    app = create_app()
    app.config.update(TESTING=True)

    # Ensure routes work with or without trailing slashs
    # Needed ChatGPT to help with this as we had failing tests due to 308 redirects
    app.url_map.strict_slashes = False
    # Initialize all rules to not require strict slashes
    for rule in list(app.url_map.iter_rules()):
        try:
            rule.strict_slashes = False
        except Exception:
            pass
    return app

@pytest.fixture()
def client(app):
    return app.test_client()

@pytest.fixture(autouse=True)
def stub_api_calls(app):
    # Create fakes for all API calls used in the app
    TEAMS = _fake_teams()
    ADP   = _fake_adp(300)
    PROJ  = _fake_player_projections(ADP)
    WK1   = _fake_week_schedule()

    # Using api_get to receive data from the fake API
    def fake_api_get(endpoint, params=None):
        ep = endpoint or ""
        if ep == "getNFLADP":
            return {"body": {"adpList": ADP}}
        if ep == "getNFLTeams":
            return {"body": {"teams": TEAMS}}
        if ep in ("getNFLGamesForWeek", "getNFLWeeklySchedule", "getNFLScoreboard"):
            return {"body": {"games": WK1}}
        if ep == "getNFLProjections":
            return {"body": {"playerProjections": PROJ}}
        if ep == "getNFLBettingOdds":
            return {"body": []}
        if ep == "getNFLNews":
            return {"body": [
                {"title": "Sample headline A", "link": "https://example.com/a"},
                {"title": "Sample headline B", "link": "https://example.com/b"},
            ]}
        if ep == "getNFLPlayerInfo":
            return {"body": []}
        return {"body": {}}

    # Use the fake_api_get in place of the real api_get during tests
    import utils.api as api_mod
    import services.projections_service as proj
    import services.injuries_service as inj
    import services.schedule_service as sched
    import services.news_service as news

    # Save originals to restore later
    originals = (api_mod.api_get, proj.api_get, inj.api_get, sched.api_get, news.api_get)
    api_mod.api_get = fake_api_get
    proj.api_get    = fake_api_get
    inj.api_get     = fake_api_get
    sched.api_get   = fake_api_get
    news.api_get    = fake_api_get

    # Yield to the test, then restore originals
    try:
        yield
    finally:
        (api_mod.api_get, proj.api_get, inj.api_get, sched.api_get, news.api_get) = originals
