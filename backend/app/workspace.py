"""Anonymous demo visitors and their sandboxes. See docs/adr/0010.

A visitor is a random workspace id carried in a cookie signed with the instance's key, and
nothing else. The id names the visitor's own SQLite file, so it is checked to be exactly 32
lowercase hex characters before it is ever used in a path.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from http.cookies import CookieError, SimpleCookie
from typing import Mapping, Optional

COOKIE_NAME = "cd_workspace"
MIN_SECRET_LENGTH = 32

_WORKSPACE_ID = re.compile(r"[0-9a-f]{32}")


def is_workspace_id(value: str) -> bool:
    return _WORKSPACE_ID.fullmatch(value) is not None


def new_workspace_id() -> str:
    return secrets.token_hex(16)


def _signature(workspace_id: str, secret: str) -> str:
    return hmac.new(secret.encode(), workspace_id.encode(), hashlib.sha256).hexdigest()


def sign_workspace(workspace_id: str, secret: str) -> str:
    return f"{workspace_id}.{_signature(workspace_id, secret)}"


def verified_workspace(token: str, secret: str) -> Optional[str]:
    """The workspace id in ``token``, or None unless it was signed with ``secret``."""
    workspace_id, _, signature = token.partition(".")
    if not is_workspace_id(workspace_id):
        return None
    if not hmac.compare_digest(signature, _signature(workspace_id, secret)):
        return None
    return workspace_id


def workspace_from_headers(headers: Mapping[str, str], secret: str) -> Optional[str]:
    raw = headers.get("cookie")
    if not raw:
        return None
    cookie: SimpleCookie = SimpleCookie()
    try:
        cookie.load(raw)
    except CookieError:
        return None
    morsel = cookie.get(COOKIE_NAME)
    return verified_workspace(morsel.value, secret) if morsel else None
