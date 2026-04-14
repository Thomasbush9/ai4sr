"""
Microsoft Entra ID (Azure AD) authentication for Flask app.
"""
import os
from flask import Blueprint, request, jsonify, session, redirect, url_for
from functools import wraps
import msal
import settings_store

auth_bp = Blueprint("auth", __name__)


def _setting(key: str, default=None):
    """Get a config value: runtime settings override environment variables."""
    val = settings_store.get(key)
    if val:
        return val
    return os.getenv(key, default)


def get_msal_app():
    """Create MSAL confidential client application."""
    client_id = _setting("MICROSOFT_CLIENT_ID")
    client_secret = _setting("MICROSOFT_CLIENT_SECRET")
    tenant_id = _setting("MICROSOFT_TENANT_ID")

    if not all([client_id, client_secret, tenant_id]):
        raise ValueError(
            "Microsoft authentication not configured. "
            "Please set MICROSOFT_CLIENT_ID, MICROSOFT_CLIENT_SECRET, and MICROSOFT_TENANT_ID "
            "in the Settings UI or .env file."
        )

    authority = f"https://login.microsoftonline.com/{tenant_id}"

    return msal.ConfidentialClientApplication(
        client_id,
        authority=authority,
        client_credential=client_secret
    )


def require_auth(f):
    """Decorator to require authentication for a route."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return jsonify({"error": "Authentication required"}), 401
        return f(*args, **kwargs)
    return decorated_function


def _get_redirect_uri() -> str:
    """Get OAuth redirect URI. Uses env/settings config, or auto-derives from request."""
    configured = _setting("MICROSOFT_REDIRECT_URI")
    if configured:
        return configured
    # Auto-derive from the current request so it works in Docker/prod without config
    return request.url_root.rstrip("/") + "/auth/callback"


@auth_bp.route("/login")
def login():
    """Initiate Microsoft login flow."""
    try:
        msal_app = get_msal_app()
        redirect_uri = _get_redirect_uri()

        auth_url = msal_app.get_authorization_request_url(
            scopes=["User.Read"],
            redirect_uri=redirect_uri
        )

        return jsonify({"auth_url": auth_url})

    except ValueError as e:
        # Config not set — expected, not a server error
        return jsonify({"error": str(e)}), 400
    except Exception:
        return jsonify({"error": "Failed to initiate login. Check server logs."}), 500


@auth_bp.route("/callback")
def callback():
    """Handle Microsoft login callback."""
    try:
        code = request.args.get('code')
        if not code:
            return jsonify({"error": "No authorization code received"}), 400

        msal_app = get_msal_app()
        redirect_uri = _get_redirect_uri()

        result = msal_app.acquire_token_by_authorization_code(
            code,
            scopes=["User.Read"],
            redirect_uri=redirect_uri
        )

        if "error" in result:
            return jsonify({"error": result.get("error_description", "Authentication failed")}), 400

        # Store user info in session (do NOT store the access token in the session)
        session['user'] = {
            'name': result.get('id_token_claims', {}).get('name', 'Unknown'),
            'email': result.get('id_token_claims', {}).get('preferred_username', 'Unknown'),
        }
        session.permanent = True

        # Redirect to main app
        return redirect('/')

    except Exception:
        return jsonify({"error": "Authentication callback failed. Check server logs."}), 500


@auth_bp.route("/logout")
def logout():
    """Logout user."""
    session.pop('user', None)
    return jsonify({"message": "Logged out successfully"})


@auth_bp.route("/user")
def get_user():
    """Get current user info."""
    if 'user' in session:
        return jsonify({
            "authenticated": True,
            "user": {
                "name": session['user']['name'],
                "email": session['user']['email']
            }
        })
    else:
        return jsonify({"authenticated": False})
