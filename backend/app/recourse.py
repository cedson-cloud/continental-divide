"""What a requester can do about a rejection.

A rejected request used to end at ``rules_evaluated -> routed``. There was no way to
accept the engine's own answer and move on, and no way to say the rule looked wrong.
Two paths close that, and they are deliberately different in kind:

* :func:`rename_and_resubmit` — the requester takes a name the engine itself vouches
  for. It supersedes rather than mutates, exactly as ``/convert`` does, and it costs
  exactly one model call: the catalog review. Interpretation is *not* re-run — the
  original's parsed definition is reused with only the name replaced, because
  re-drafting a definition nobody disputed would be four calls for a rename.

* :func:`record_rule_dispute` — the requester says the rule is wrong for their team.
  It amends nothing: no profile change, no file write, no status change, no model
  call. Authoring conventions happens in the governance wizard and nowhere else, so
  enforcement and authoring never share a screen or a moment. What this records is a
  disagreement, addressed to the data team, stamped with which version of the rules
  was in force when it was raised.
"""

from __future__ import annotations

import hashlib
import json
from typing import Callable, Optional

from .catalog import DuplicateReview, review_against_catalog
from .governance import GovernanceProfile, load_active_profile
from .models import EventDefinition
from .naming_repair import suggest_compliant_names

# _route is the shared schema -> rules -> review -> routed tail. A renamed request
# must travel it byte-for-byte the way intake does, so it is reused rather than
# reimplemented here; pipeline.py is not modified.
from .pipeline import InvalidTransition, RequestNotFound, _route
from .storage import Storage

# Only a rejected request has anything to recover from.
RENAMEABLE_STATUSES = {"rejected"}


class NameNotOffered(Exception):
    """The caller supplied a name that is not in the set the server derives for this
    request. The candidate set is the authority, not the client."""


class RuleNotFailing(Exception):
    """The caller disputed a rule that did not fail on this request."""


def profile_digest(profile: GovernanceProfile) -> str:
    """A short, stable fingerprint of a profile's contents.

    Recorded alongside a dispute so a later reader knows which version of the rules
    was being argued with — a profile's name outlives its contents, and the whole
    point of governance-as-configuration is that the contents change."""
    payload = json.dumps(
        profile.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]


def _rule_checks(storage: Storage, request_id: int) -> list[dict]:
    """The per-rule report from the request's own rules pass, or an empty list."""
    entry = next(
        (
            e
            for e in reversed(storage.get_audit_log(request_id))
            if e["step"] == "rules_evaluated"
        ),
        None,
    )
    return list((entry or {}).get("detail", {}).get("checks") or [])


def failed_rules(storage: Storage, request_id: int) -> list[str]:
    return [c["rule"] for c in _rule_checks(storage, request_id) if not c.get("passed")]


def failed_naming_rule(storage: Storage, request_id: int) -> Optional[str]:
    """The name of the naming rule this request failed, if it failed one."""
    for check in _rule_checks(storage, request_id):
        if check["rule"] == "event_naming" and not check.get("passed"):
            return check["rule"]
    return None


def name_suggestions(
    request: dict,
    storage: Storage,
    profile: Optional[GovernanceProfile] = None,
) -> list[str]:
    """Compliant alternatives to a request's drafted name, or an empty list.

    Derived server-side from the stored definition and the active profile — the same
    call :func:`rename_and_resubmit` makes to validate a submitted name, so the set
    the UI offers and the set the endpoint accepts cannot drift apart. Only a request
    that a naming rule rejected has suggestions; everything else gets an empty list.
    """
    definition = request.get("parsed_definition")
    if request.get("status") not in RENAMEABLE_STATUSES or not definition:
        return []
    if failed_naming_rule(storage, request["id"]) is None:
        return []
    if profile is None:
        profile = load_active_profile()
    return suggest_compliant_names(definition["name"], profile=profile)


def rename_and_resubmit(
    request_id: int,
    new_name: str,
    storage: Storage,
    duplicate_fn: Callable[..., DuplicateReview] = review_against_catalog,
    profile: Optional[GovernanceProfile] = None,
) -> int:
    """Supersede a name-rejected request with one carrying a compliant name.

    ``new_name`` must be a member of the set :func:`name_suggestions` derives on the
    server for this request; a name from anywhere else is refused, so the client can
    never dictate a name past the rule. The original is never edited — it keeps its
    ``rejected`` status and its parsed definition, and gains only an append-only
    ``superseded_by`` entry. The new request carries the original's intake text and
    metadata and reuses its parsed definition with the name replaced, so no
    interpretation call is made; the rules re-run deterministically and, because they
    now pass, the catalog review runs. Exactly one model call per rename.

    Returns the new request id; raises :class:`RequestNotFound`,
    :class:`InvalidTransition`, or :class:`NameNotOffered` for the caller to map to
    HTTP.
    """
    request = storage.get_request(request_id)
    if request is None:
        raise RequestNotFound(f"request {request_id} not found")
    if request["status"] not in RENAMEABLE_STATUSES:
        raise InvalidTransition(
            f"request {request_id} is '{request['status']}' and cannot be renamed"
        )
    definition = request.get("parsed_definition")
    if not definition:
        raise InvalidTransition(
            f"request {request_id} has no parsed definition to rename"
        )
    rule = failed_naming_rule(storage, request_id)
    if rule is None:
        raise InvalidTransition(
            f"request {request_id} was not rejected by the event-naming rule"
        )

    if profile is None:
        profile = load_active_profile()
    offered = name_suggestions(request, storage, profile)
    if new_name not in offered:
        raise NameNotOffered(
            f"'{new_name}' is not one of the compliant names derived for request "
            f"{request_id} ({', '.join(offered) or 'none'}); a rename must take a "
            "name the engine itself accepts"
        )

    original_name = definition["name"]
    renamed = {**definition, "name": new_name}

    new_request_id = storage.create_request(
        raw_intake_text=request["raw_intake_text"],
        submitter_name=request.get("submitter_name"),
        submitter_team=request.get("submitter_team"),
        call_type=request.get("call_type"),
        side=request.get("side"),
        business_value=request.get("business_value"),
        urgent=bool(request.get("urgent")),
        urgency_reason=request.get("urgency_reason"),
        needed_by=request.get("needed_by"),
        request_kind=request.get("request_kind"),
        existing_event=request.get("existing_event"),
        destinations=request.get("destinations"),
    )
    storage.add_audit_entry(
        new_request_id,
        "intake_received",
        {
            "raw_intake_text": request["raw_intake_text"],
            "submitter_name": request.get("submitter_name"),
            "submitter_team": request.get("submitter_team"),
            "call_type": request.get("call_type"),
            "side": request.get("side"),
            "business_value": request.get("business_value"),
            "urgent": bool(request.get("urgent")),
            "urgency_reason": request.get("urgency_reason"),
            "needed_by": request.get("needed_by"),
            "request_kind": request.get("request_kind"),
            "existing_event": request.get("existing_event"),
            "destinations": request.get("destinations"),
        },
    )
    # The consent, recorded before the definition it explains: this name was dictated
    # by the requester off a server-derived list, not drafted by the model.
    storage.add_audit_entry(
        new_request_id,
        "renamed_and_resubmitted",
        {
            "original_request_id": request_id,
            "original_name": original_name,
            "new_name": new_name,
            "failed_rule": rule,
            "profile": profile.name,
        },
    )

    parsed = EventDefinition.model_validate(renamed)
    storage.set_parsed_definition(new_request_id, parsed.model_dump(), parsed.category)
    _route(
        new_request_id,
        parsed,
        None,
        storage,
        profile,
        duplicate_fn,
        requires_confirmation=True,
    )

    storage.add_audit_entry(
        request_id,
        "superseded_by",
        {"new_request_id": new_request_id, "new_name": new_name},
    )
    storage.add_audit_entry(
        new_request_id,
        "supersedes",
        {"original_request_id": request_id, "original_name": original_name},
    )
    return new_request_id


def record_rule_dispute(
    request_id: int,
    rule: str,
    note: str,
    storage: Storage,
    profile: Optional[GovernanceProfile] = None,
) -> dict:
    """Record that the requester thinks ``rule`` is wrong for their team.

    Writes one ``rule_disputed`` audit entry and nothing else. No profile is amended,
    no file is written, no status changes, and no model is called — the request stays
    exactly as the rules left it. ``rule`` must be a rule that actually failed on this
    request, so a dispute is always anchored to a real outcome.

    Returns the recorded detail; raises :class:`RequestNotFound` or
    :class:`RuleNotFailing` for the caller to map to HTTP.
    """
    request = storage.get_request(request_id)
    if request is None:
        raise RequestNotFound(f"request {request_id} not found")
    failed = failed_rules(storage, request_id)
    if rule not in failed:
        raise RuleNotFailing(
            f"rule '{rule}' did not fail on request {request_id} "
            f"({', '.join(failed) or 'no rule failed'}); a dispute must name a rule "
            "that decided this request"
        )

    if profile is None:
        profile = load_active_profile()
    detail = {
        "rule": rule,
        "note": note,
        "profile": profile.name,
        "profile_digest": profile_digest(profile),
    }
    storage.add_audit_entry(request_id, "rule_disputed", detail)
    return detail


def open_disputes(storage: Storage) -> list[dict]:
    """Every recorded dispute, newest first, for the data team's read-only panel.

    There is no resolution mechanism by design — amending a rule happens in the
    governance wizard, in a versioned file, by a human — so every recorded dispute is
    open. This is a list, not a workflow.
    """
    disputes = []
    for row in storage.list_requests():
        for entry in storage.get_audit_log(row["id"]):
            if entry["step"] != "rule_disputed":
                continue
            detail = entry.get("detail") or {}
            disputes.append(
                {
                    "request_id": row["id"],
                    "event_name": (row.get("parsed_definition") or {}).get("name"),
                    "request_status": row["status"],
                    "rule": detail.get("rule"),
                    "note": detail.get("note"),
                    "profile": detail.get("profile"),
                    "profile_digest": detail.get("profile_digest"),
                    "created_at": entry["created_at"],
                }
            )
    disputes.sort(key=lambda d: (d["created_at"], d["request_id"]), reverse=True)
    return disputes
