"""Who is acting on a request, and how that was established.

Every request gets its identity from an :class:`IdentityVerifier`, chosen by
``AUTH_MODE``. The choice fails closed: an unset, unknown, or incomplete configuration
yields a verifier that rejects everything, never a default identity. Headers that merely
claim an identity are never trusted. See docs/adr/0004.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Mapping, Optional

from .config import Settings
from .workspace import MIN_SECRET_LENGTH, workspace_from_headers


class Unauthenticated(Exception):
    pass


@dataclass(frozen=True)
class Identity:
    """Who acted. ``verified`` is False when nothing checked the claim, as in local mode.

    ``workspace`` is set only for a demo visitor, and picks their sandbox (docs/adr/0010).
    """

    email: str
    method: str
    verified: bool
    workspace: Optional[str] = None


class IdentityVerifier(ABC):
    @abstractmethod
    def verify(self, headers: Mapping[str, str]) -> "Identity":
        """Return who is acting, or raise :class:`Unauthenticated`."""
        ...


class RejectAll(IdentityVerifier):
    def __init__(self, reason: str) -> None:
        self.reason = reason

    def verify(self, headers: Mapping[str, str]) -> "Identity":
        raise Unauthenticated(self.reason)


class LocalDevVerifier(IdentityVerifier):
    """Acts as one configured person for every request. Checks nothing, and says so."""

    def __init__(self, email: str) -> None:
        self.identity = Identity(email=email, method="local", verified=False)

    def verify(self, headers: Mapping[str, str]) -> Identity:
        return self.identity


class DemoVisitorVerifier(IdentityVerifier):
    """An anonymous visitor to the public demo, known only by a signed workspace cookie.
    Nothing establishes who they are, and every entry says so."""

    def __init__(self, secret: str) -> None:
        self.secret = secret

    def verify(self, headers: Mapping[str, str]) -> Identity:
        workspace = workspace_from_headers(headers, self.secret)
        if workspace is None:
            raise Unauthenticated("no demo session; start one with POST /session")
        return Identity(
            email="anonymous visitor", method="demo", verified=False, workspace=workspace
        )


def get_verifier(settings: Settings) -> IdentityVerifier:
    if settings.auth_mode == "demo":
        if len(settings.demo_cookie_secret) < MIN_SECRET_LENGTH:
            return RejectAll(
                f"AUTH_MODE=demo needs a DEMO_COOKIE_SECRET of at least {MIN_SECRET_LENGTH} characters"
            )
        return DemoVisitorVerifier(settings.demo_cookie_secret)
    if settings.auth_mode == "local":
        email = settings.local_identity_email.strip()
        if not email:
            return RejectAll("AUTH_MODE=local needs LOCAL_IDENTITY_EMAIL")
        return LocalDevVerifier(email)
    return RejectAll("authentication is not configured")
