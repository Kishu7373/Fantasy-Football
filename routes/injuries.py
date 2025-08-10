from flask import Blueprint, render_template, request
from services.injuries_service import build_injury_table, build_player_card
from utils.api import current_season

injuries_bp = Blueprint("injuries", __name__)

@injuries_bp.get("/injuries", endpoint="injuries")
def injuries ():
    # Utilized ChatGPT to understand how to build a table within the link. It suggested a path utilizing Bleuprint and Flask's render_template.
    # This function builds the injury table and player card based on the request parameters.
    # We then applied the Blueprint template to all other routes for standardization.
    data = build_injury_table()

    if isinstance(data, dict):
        ctx = data
    else:
        # tuple order from the service:
        table_html, season, top_scan, max_results, found, elapsed = data
        ctx = {
            "table_html": table_html,
            "season": season or current_season(),
            "top_scan": top_scan,
            "max_results": max_results,
            "found": found,
            "elapsed": elapsed,
        }

    # Player card logic if a query is provided
    # Utilized the integrated Copilot in Visual Studio Code to understand how to build a player card based on the query.
    query = request.args.get("player", "").strip()
    card_html = ""
    if query:
        card_html = build_player_card(query)

    return render_template(
        "injuries.html",
        **ctx,
        query=query,
        card_html=card_html
    )

