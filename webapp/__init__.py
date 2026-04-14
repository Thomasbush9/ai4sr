from datetime import timedelta
from flask import Flask, render_template, request, abort
from .routes import api_bp
from .auth import auth_bp
import config
from utils.logger import get_logger

logger = get_logger("webapp")

def create_app():
    app = Flask(__name__, static_folder="../static", template_folder="../templates")

    # Configure Flask secret key for sessions
    app.config['SECRET_KEY'] = config.FLASK_SECRET_KEY

    # Secure session cookies
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=8)
    if config.IS_PRODUCTION:
        app.config['SESSION_COOKIE_SECURE'] = True   # HTTPS only in prod

    # Register blueprints
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(auth_bp, url_prefix="/auth")

    # CSRF-like origin check for state-changing requests
    @app.before_request
    def _check_origin():
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return
        origin = request.headers.get("Origin") or request.headers.get("Referer") or ""
        # Allow same-origin requests and requests with no Origin (e.g. curl, Postman)
        if origin:
            from urllib.parse import urlparse
            allowed_host = request.host.split(":")[0]
            req_host = urlparse(origin).hostname
            if req_host and req_host != allowed_host and req_host != "localhost":
                logger.warning("Blocked cross-origin POST from %s", origin)
                abort(403)

    @app.route("/")
    def index():
        return render_template("index.html")

    # Register error handlers
    @app.errorhandler(404)
    def not_found(error):
        return {"error": "Resource not found"}, 404

    @app.errorhandler(500)
    def internal_error(error):
        logger.error("Internal server error", exc_info=True)
        return {"error": "Internal server error"}, 500

    logger.info("Flask app created and configured")
    return app
