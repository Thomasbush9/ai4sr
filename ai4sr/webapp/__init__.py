from flask import Flask, render_template
from .routes import api_bp
from .auth import auth_bp
import config
from utils.logger import get_logger

logger = get_logger("webapp")

def create_app():
    app = Flask(__name__, static_folder="../static", template_folder="../templates")

    # Configure Flask secret key for sessions
    app.config['SECRET_KEY'] = config.FLASK_SECRET_KEY

    # Register blueprints
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(auth_bp, url_prefix="/auth")

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
