from __future__ import annotations

import os
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

from ..config import settings


def _get_serializer() -> URLSafeTimedSerializer:
    secret = settings.CSRF_SECRET
    # Use a stable salt to bind purpose; change to rotate
    return URLSafeTimedSerializer(secret_key=secret, salt="pm.csrf.v1")


def generate_csrf_token() -> str:
    """Create a signed CSRF token string."""
    s = _get_serializer()
    # Payload can be random; signature protects integrity.
    payload = os.urandom(16).hex()
    return s.dumps(payload)


def validate_csrf_token(token: str, max_age: Optional[int] = None) -> bool:
    """Validate CSRF token signature and optional TTL."""
    if not token:
        return False
    s = _get_serializer()
    try:
        s.loads(token, max_age=max_age or settings.CSRF_TOKEN_TTL_SECONDS)
        return True
    except (BadSignature, SignatureExpired):
        return False


def extract_csrf_from_request(request: Request) -> Optional[str]:
    """Get CSRF token from header or form body, depending on request type."""
    # Prefer header for AJAX (htmx can send a header), fallback to form field
    header = request.headers.get(settings.CSRF_HEADER_NAME)
    if header:
        return header
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        # FastAPI parses form in endpoint; here we read raw for safety
        # Caller can also pass token via request.state.csrf_token if pre-parsed
        form_field = settings.CSRF_FORM_FIELD
        # Avoid consuming body: expect handlers to provide token explicitly
        return request.query_params.get(form_field)
    return None


def set_csrf_cookie(response, token: Optional[str] = None) -> str:
    """Ensure CSRF cookie is set; returns the token used."""
    t = token or generate_csrf_token()
    response.set_cookie(
        key=settings.CSRF_COOKIE_NAME,
        value=t,
        httponly=False,  # allow JS to read if needed for SPA; for HTMX forms, hidden input is enough
        secure=settings.CSRF_COOKIE_SECURE,
        samesite=settings.CSRF_COOKIE_SAMESITE,
        max_age=settings.CSRF_TOKEN_TTL_SECONDS,
    )
    return t


def ensure_csrf(request: Request) -> None:
    """FastAPI dependency to enforce CSRF on state-mutating web requests.

    Strategy: compare a signed token provided by client (header or form) with
    a valid signed token stored in cookie. Both must be valid tokens.
    """
    if not settings.CSRF_ENFORCE:
        return None

    cookie_token = request.cookies.get(settings.CSRF_COOKIE_NAME, "")
    provided = extract_csrf_from_request(request) or ""

    if not (cookie_token and provided):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF token missing")

    if not (validate_csrf_token(cookie_token) and validate_csrf_token(provided)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF token invalid")

    # Optionally, enforce equality to bind double-submit cookie pattern
    if cookie_token != provided:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF token mismatch")

    return None

