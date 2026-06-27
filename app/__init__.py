import os

from flask import Flask


def _env_flag(name, default):
    value = os.environ.get(name)
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def create_app():
    app = Flask(__name__)

    # SECRET_KEY is required by Flask's session/flash mechanism.
    # For production, load this from an environment variable or config file.
    app.config["SECRET_KEY"] = "dev-secret-key-change-in-prod"

    # Feature flags for the template-guided local-LLM threat pipeline. Each is
    # overridable via the matching environment variable. The new pipeline is on by
    # default and always degrades to a valid deterministic risks.json if the local
    # LLM is unavailable; the legacy single-call risk review is off by default.
    app.config["LLM_THREAT_IDENTIFICATION_ENABLED"] = _env_flag("LLM_THREAT_IDENTIFICATION_ENABLED", True)
    app.config["LLM_MITIGATION_GENERATION_ENABLED"] = _env_flag("LLM_MITIGATION_GENERATION_ENABLED", True)
    app.config["LEGACY_LLM_RISK_REVIEW_ENABLED"] = _env_flag("LEGACY_LLM_RISK_REVIEW_ENABLED", False)

    from .routes import main
    app.register_blueprint(main)

    return app
