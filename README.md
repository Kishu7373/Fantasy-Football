# Fantasy-Football

A simple app that surfaces fantasy-friendly NFL data from the Tank01 RapidAPI endpoints:

- Projections (Main page) – mock draft, full rosters (with team + headshot), weekly projections, proposed starters, and totals  
- Injuries – quick league snapshot of injury blurbs (top ADP) + optional player card  
- Schedule + Odds – weekly schedule joined with available betting odds (with a friendly note when odds aren’t posted yet)  
- News – league-wide headlines first, with a “search by player” box

---

## Prerequisites

- Python
- Conda
- A free RapidAPI account + key for **Tank01 NFL**  

---

## Environment Variables

The app expects a single environment variable:

- `X_RAPIDAPI_KEY` – your RapidAPI key

---

## Rate Limits & Notes

- RapidAPI plans have per-minute/hour quotas. If you see 429 errors, slow requests or reduce list sizes (e.g., scan top-25 ADP instead of top-100).

- Odds may not be posted yet for future dates; the Schedule page adds a friendly note for those days.

- Team abbreviations differ across feeds; the app normalizes common ones.

## How to Active Locally

- conda create -n Fantasy-Football python=3.10
- conda activate Fantasy-Football
- python -m pip install -r requirements.txt
- flask run

