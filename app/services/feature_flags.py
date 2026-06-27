"""Small helper for reading boolean feature flags.

Flags are resolved from the Flask app config first (so they can be set in
``create_app``/config), then from the process environment, then a default. This
keeps the new template-guided threat-identification pipeline behind toggles:

    LLM_THREAT_IDENTIFICATION_ENABLED   (default: True)
    LLM_MITIGATION_GENERATION_ENABLED   (default: True)
    LEGACY_LLM_RISK_REVIEW_ENABLED      (default: False)
"""

import os

_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}


def flag_enabled(app_config, name, default=False):
    """Return whether the named boolean flag is enabled.

    ``app_config`` may be a Flask config (dict-like), a plain dict, or None.
    Unset / unrecognized values fall back to ``default``.
    """
    value = _config_value(app_config, name)
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in _TRUE:
        return True
    if text in _FALSE:
        return False
    return default


def config_int(app_config, name, default):
    """Return an integer config value (app config first, then env, then default).

    Unset or non-integer values fall back to ``default``. Used for tunables like
    the local-LLM request timeout (``LLM_REQUEST_TIMEOUT``), so a slower or faster
    swapped-in model can be given more/less time without code changes.
    """
    value = _config_value(app_config, name)
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _config_value(app_config, name):
    """Read ``name`` from the Flask/dict config first, then the environment."""
    value = None
    if app_config is not None:
        try:
            value = app_config.get(name)
        except AttributeError:
            value = None
    if value is None:
        value = os.environ.get(name)
    return value
