# routes/news.py
from flask import Blueprint, render_template, request
from services.news_service import fetch_league_news, filter_news

news_bp = Blueprint("news", __name__, url_prefix="/news")

@news_bp.route("/", methods=["GET"])
def news():
    q = request.args.get("q", "").strip()
    items = fetch_league_news(max_items=40, fantasy_only=True)
    shown = filter_news(items, q) if q else items
    return render_template("news.html", items=shown, query=q)