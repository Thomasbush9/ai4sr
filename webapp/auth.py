"""
Microsoft Entra ID (Azure AD) authentication for Flask app.
"""
import os
from flask import Blueprint, request, jsonify, session, redirect, url_for
from functools import wraps
import msal

auth_bp = Blueprint("auth", __name__)


def get_msal_app():
    """Create MSAL confidential client application."""
    client_id = os.getenv("MICROSOFT_CLIENT_ID")
    client_secret = os.getenv("MICROSOFT_CLIENT_SECRET")
    tenant_id = os.getenv("MICROSOFT_TENANT_ID")

    if not all([client_id, client_secret, tenant_id]):
        raise ValueError(
            "Microsoft authentication not configured. "
            "Please set MICROSOFT_CLIENT_ID, MICROSOFT_CLIENT_SECRET, and MICROSOFT_TENANT_ID."
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


@auth_bp.route("/login")
def login():
    """Initiate Microsoft login flow."""
    try:
        msal_app = get_msal_app()
        redirect_uri = os.getenv("MICROSOFT_REDIRECT_URI", "http://localhost:5000/auth/callback")

        auth_url = msal_app.get_authorization_request_url(
            scopes=["User.Read"],
            redirect_uri=redirect_uri
        )

        return jsonify({"auth_url": auth_url})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@auth_bp.route("/callback")
def callback():
    """Handle Microsoft login callback."""
    try:
        code = request.args.get('code')
        if not code:
            return jsonify({"error": "No authorization code received"}), 400

        msal_app = get_msal_app()
        redirect_uri = os.getenv("MICROSOFT_REDIRECT_URI", "http://localhost:5000/auth/callback")

        result = msal_app.acquire_token_by_authorization_code(
            code,
            scopes=["User.Read"],
            redirect_uri=redirect_uri
        )

        if "error" in result:
            return jsonify({"error": result.get("error_description", "Authentication failed")}), 400

        # Store user info in session
        session['user'] = {
            'name': result.get('id_token_claims', {}).get('name', 'Unknown'),
            'email': result.get('id_token_claims', {}).get('preferred_username', 'Unknown'),
            'token': result.get('access_token')
        }

        # Redirect to main app
        return redirect('/')

    except Exception as e:
        return jsonify({"error": str(e)}), 500


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
