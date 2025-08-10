from flask import Blueprint, request, render_template
from services.projections_service import build_projections
from utils.api import current_season

projections_bp = Blueprint("projections", __name__, url_prefix="/projections")

@projections_bp.route("/", methods=["GET"])
def projections():
    # The projections page allows users to view player projections
    # Users are able to add customize the number of teams, slot, week, and scoring type
    # Default values for the controls are set to 10 teams, slot 1, week 1, and standard scoring
    # Utilized ChatGPT to generate the understand how to implement this feature
    n_teams = int(request.args.get("teams", 10))
    slot    = int(request.args.get("slot", 1))
    week    = int(request.args.get("week", 1))
    scoring = request.args.get("scoring", "standard")

    # Ensure the number of teams is within a reasonable range
    if slot < 1: slot = 1
    if slot > n_teams: slot = n_teams

    data = build_projections(
        n_teams=n_teams,
        slot=slot,
        wk=week,
        scoring=scoring,
        season=current_season()
    )

    return render_template(
        "projections.html",
        controls={"teams": n_teams, "slot": slot, "week": week, "scoring": scoring},
        draft_log_html=data["draft_log_html"],
        roster_html=data["roster_html"],
        projections_html=data["projections_html"],
        starters_html=data["starters_html"],
        totals_html=data["totals_html"],
    )
