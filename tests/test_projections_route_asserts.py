# tests/test_projections_route_asserts.py

# Fetch and test the projections route, ensuring it works with
# various query parameters and that the page renders correctly.
def _simple_fetch():
    FAKE = {
        "getNFLADP": {"body": {"adpList": []}},
        "getNFLTeams": {"body": {"teams": []}},
        "getNFLGamesForWeek": {"body": {"games": []}},
        "getNFLProjections": {"body": {"playerProjections": {}}},

       # Other endpoints that might be used in the app
        "getNFLNews": {"body": []},
        "getNFLPlayerInfo": {"body": []},
        "getNFLBettingOdds": {"body": []},
    }
    def fetch(endpoint, params=None):
        return FAKE.get(endpoint, {})
    return fetch

# Tests for the projections route and other routes in the app
# Ensure that the status codes are correct and that the HTML content
# contains expected text based on the route.
def test_home_ok(app, client):
    r = client.get("/")
    assert r.status_code == 200
    html = r.data.decode()
    assert "Home" in html or "Projections" in html  # header links

# Test the projections route with no query parameters
# Utilized ChatGPT to understand how to utilize the fetch function
# Fetch is mocked to return a simple structure
def test_projections_updates_from_query(app, client):
    app.config["FETCH"] = _simple_fetch()

    # Pick some inputs and ensure the page reflects them
    r = client.get("/projections/?teams=8&slot=2&week=4&scoring=PPR")
    assert r.status_code == 200
    html = r.data.decode()

    # Check that the page renders correctly
    assert "Projections" in html
    # Check that the query parameters are reflected in the page
    assert "Week 4 — Projections" in html
    # Check that the team and slot are reflected in the page
    assert "Team 2 Roster Total" in html

# Test the projections route with another set of query parameters
def test_projections_another_combo(app, client):
    app.config["FETCH"] = _simple_fetch()

    r = client.get("/projections/?teams=10&slot=3&week=1&scoring=standard")
    assert r.status_code == 200
    html = r.data.decode()
    assert "Week 1 — Projections" in html
    assert "Team 3 Roster Total" in html

# Similar to the projections tests, but for the injuries route
def test_injuries_ok(app, client):
    app.config["FETCH"] = _simple_fetch()

    r = client.get("/injuries")
    assert r.status_code == 200
    html = r.data.decode()
    # Just make sure the page renders its title area
    assert "Injury" in html or "Injuries" in html

# Similar to the projections tests, but for the schedule route
def test_schedule_ok(app, client):
    app.config["FETCH"] = _simple_fetch()

    r = client.get("/schedule")
    assert r.status_code == 200
    html = r.data.decode()
    assert "Schedule" in html or "Odds" in html

# Similar to the projections tests, but for the news route
def test_news_ok(app, client):
    app.config["FETCH"] = _simple_fetch()

    r = client.get("/news")
    assert r.status_code == 200
    html = r.data.decode()
    assert "News" in html
