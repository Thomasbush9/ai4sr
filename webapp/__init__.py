from flask import Flask, render_template
from .routes import api_bp
from .auth import auth_bp
import config

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

    return app
