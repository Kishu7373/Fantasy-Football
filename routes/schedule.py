# routes/schedule.py
from flask import Blueprint, render_template, request
from services.schedule_service import build_week_schedule_with_odds

schedule_bp = Blueprint("schedule", __name__)

@schedule_bp.get("/schedule", endpoint="schedule")
def schedule ():
    # The schedule page allows users to view the schedule for a specific week
    # Users can select the week they want to view
    # Default value for the week is set to 1
    try:
        week = int(request.args.get("week", 1))
    except ValueError:
        week = 1
    data = build_week_schedule_with_odds(week=week)
    return render_template(
        "schedule.html",
        week=data["week"],
        season=data["season"],
        table_html=data["table_html"],
        missing_note=data["missing_note"],
    )
