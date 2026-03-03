from flask import Flask

def create_app():
    app = Flask(__name__)

    # SECRET_KEY is required by Flask's session/flash mechanism.
    # For production, load this from an environment variable or config file.
    app.config["SECRET_KEY"] = "dev-secret-key-change-in-prod"

    from .routes import main
    app.register_blueprint(main)

    return app
