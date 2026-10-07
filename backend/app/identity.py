"""Who is acting on a request, and how that was established.

Every request gets its identity from an :class:`IdentityVerifier`, chosen by
``AUTH_MODE``. The choice fails closed: an unset, unknown, or incomplete configuration
yields a verifier that rejects everything, never a default identity. Headers that merely
claim an identity are never trusted. See docs/adr/0004.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Mapping

from .config import Settings


class Unauthenticated(Exception):
    pass


@dataclass(frozen=True)
class Identity:
    """Who acted. ``verified`` is False when nothing checked the claim, as in local mode."""

    email: str
    method: str
    verified: bool


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


def get_verifier(settings: Settings) -> IdentityVerifier:
    if settings.auth_mode == "local":
        email = settings.local_identity_email.strip()
        if not email:
            return RejectAll("AUTH_MODE=local needs LOCAL_IDENTITY_EMAIL")
        return LocalDevVerifier(email)
    return RejectAll("authentication is not configured")
