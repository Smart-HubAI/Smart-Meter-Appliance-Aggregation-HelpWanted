"""
Authentication, RBAC decorators, user seeding, and audit logging.
"""

from datetime import datetime
from functools import wraps
import logging

import bcrypt
from flask import jsonify
from flask_jwt_extended import get_jwt, get_jwt_identity, verify_jwt_in_request

from database.dal import (
    get_user_by_username,
    insert_audit_log,
    insert_user,
    update_last_login,
    user_count,
)


# ---------------------------------------------------------------------------
# Password helpers
# ---------------------------------------------------------------------------

def hash_password(plain: str) -> str:
    """Return bcrypt hash of a plaintext password."""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def check_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


# ---------------------------------------------------------------------------
# RBAC decorators
# ---------------------------------------------------------------------------

def role_required(*allowed_roles):
    """
    Decorator that enforces role-based access on Flask routes.
    Must be used *after* @jwt_required().
    Reads the 'role' claim from the JWT and returns 403 if not in allowed_roles.
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            claims = get_jwt()
            role = claims.get("role", "")
            if role not in allowed_roles:
                insert_audit_log(
                    username=get_jwt_identity(),
                    role=role,
                    action="access_denied",
                    page_accessed=fn.__name__,
                )
                return jsonify({
                    "error": "Access denied",
                    "message": f"Role '{role}' is not authorized for this resource.",
                }), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def consumer_scope_required():
    """
    Decorator that ensures a consumer-role user can only access their own data.
    Must be used *after* @jwt_required() and on routes that accept <consumer_id>.
    Admin and developer roles bypass this check.
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            claims = get_jwt()
            role = claims.get("role", "")
            consumer_id = kwargs.get("consumer_id")
            if role == "consumer":
                user_consumer_id = claims.get("consumer_id", "")
                if consumer_id and consumer_id != user_consumer_id:
                    insert_audit_log(
                        username=get_jwt_identity(),
                        role=role,
                        action="unauthorized_consumer_access",
                        page_accessed=f"{fn.__name__} consumer_id={consumer_id}",
                    )
                    return jsonify({
                        "error": "Access denied",
                        "message": "You can only access your own data.",
                    }), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator


# ---------------------------------------------------------------------------
# User seeding
# ---------------------------------------------------------------------------

def seed_users() -> str:
    """
    Create default users if the users table is empty.
    100 consumers (con001–con100), one admin, one developer.
    """
    logging.info("[Smart Meter Platform] Authentication initialized.")
    if user_count() > 0:
        logging.info("[Smart Meter Platform] Default user accounts verified.")
        return "verified"

    # Consumer users con001 – con100
    consumer_hash = hash_password("consumer123")
    for i in range(1, 101):
        username = f"con{i:03d}"
        consumer_id = f"CON{i:03d}"
        insert_user(username, consumer_hash, "consumer", consumer_id)

    # Admin user
    insert_user("admin", hash_password("admin123"), "admin", None)  # type: ignore

    # Developer user
    insert_user("developer", hash_password("developer123"), "developer", None)  # type: ignore

    logging.info("[Smart Meter Platform] Default administrator and consumer accounts created.")
    return "created"


# ---------------------------------------------------------------------------
# Login helper
# ---------------------------------------------------------------------------

def authenticate_user(username: str, password: str):
    """
    Validate credentials and return a user dict (without hash) or None.
    Updates last_login on success and logs the attempt.
    """
    user = get_user_by_username(username)
    if not user:
        insert_audit_log(username, "", "failed_login", "")
        return None

    if not user["is_active"]:
        insert_audit_log(username, user["role"], "failed_login_inactive", "")
        return None

    if not check_password(password, user["password_hash"]):
        insert_audit_log(username, user["role"], "failed_login", "")
        return None

    # Success
    update_last_login(username)
    insert_audit_log(username, user["role"], "login", "")
    return {
        "username": user["username"],
        "role": user["role"],
        "consumer_id": user["consumer_id"],
        "is_active": user["is_active"],
    }


def get_role_redirect(role: str) -> str:
    """Return the default landing route for a given role."""
    return {
        "consumer": "/home",
        "admin": "/admin",
        "developer": "/admin",
    }.get(role, "/")


def get_role_display_name(role: str) -> str:
    """Human-friendly role label for the UI."""
    return {
        "consumer": "Consumer",
        "admin": "Administrator",
        "developer": "AI Developer",
    }.get(role, role)
