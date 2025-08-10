from flask import Flask
from routes.home import home_bp
from routes.projections import projections_bp
from routes.schedule import schedule_bp
from routes.news import news_bp
from routes.injuries import injuries_bp

# Create the Flask application instance
# This function initializes the Flask app and registers the blueprints for different routes.
# Each blueprint corresponds to a specific section of the application, such as home, projections, schedule, news, and injuries.
def create_app():
    app = Flask(__name__)

    # register pages
    app.register_blueprint(home_bp)         # "/"
    app.register_blueprint(projections_bp)  # "/projections"
    app.register_blueprint(schedule_bp)     # "/schedule"
    app.register_blueprint(news_bp)         # "/news"
    app.register_blueprint(injuries_bp)     # "/injuries"

    @app.after_request
    def add_no_cache_headers(resp):
        resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        resp.headers["Pragma"] = "no-cache"
        resp.headers["Expires"] = "0"
        return resp

    return app
