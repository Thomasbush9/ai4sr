from flask import Flask, render_template
from .routes import api_bp

def create_app():
    app = Flask(__name__, static_folder="../static", template_folder="../templates")
    app.register_blueprint(api_bp, url_prefix="/api")

    @app.route("/")
    def index():
        return render_template("index.html")

    return app
