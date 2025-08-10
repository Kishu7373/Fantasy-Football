# services/news_service.py
from urllib.parse import urlparse
from utils.api import api_get, normalize_list

# This function extracts the source of a URL.
# It parses the URL and returns the network location, replacing "www." with an empty string
def _source_of(url: str) -> str:
    try:
        return urlparse(url).netloc.replace("www.", "")
    except Exception:
        return ""

# This function fetches league news from the API.
# It allows for a maximum number of items to be returned and can filter for fantasy-related news
# It returns a list of dictionaries containing the title, source, and link for each news item.
def fetch_league_news(max_items: int = 40, fantasy_only: bool = True):
    params = {"maxItems": str(max_items)}
    if fantasy_only:
        params["fantasyNews"] = "true"

    resp = api_get("getNFLNews", params)
    items = resp.get("body", []) if isinstance(resp, dict) else []
    rows = []
    for it in items:
        title = (it.get("title") or "").strip()
        link  = (it.get("link")  or "").strip()
        if title and link:
            rows.append({"title": title, "source": _source_of(link), "link": link})
    return rows

# This function filters news items based on a query string.
# It checks if the query is present in the title of each news item, ignoring case.
def filter_news(items, query: str):
    q = (query or "").strip().lower()
    if not q:
        return items
    return [r for r in items if q in r["title"].lower()]
