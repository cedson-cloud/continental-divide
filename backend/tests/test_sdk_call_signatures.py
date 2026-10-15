"""Every model call passes only arguments the installed Anthropic SDK accepts.

The rest of the suite fakes the model client, so an SDK release that drops an argument
a call passes would otherwise surface only in production, as it did with ``temperature``
in 1.x. Here the fake binds each call's arguments to the installed ``Messages.create``
signature, which raises the same TypeError the real client would. Nothing calls a model.
"""

import inspect

import pytest
from anthropic.resources.messages import Messages

from app.catalog import review_against_catalog
from app.config import get_settings
from app.interpreter import interpret
from app.models import EventDefinition

_SIGNATURE = inspect.signature(Messages.create)


class _Bound(Exception):
    """The arguments bound; stops the caller before it reads a response."""


class _BindingClient:
    def __init__(self, api_key=None):
        self.messages = self

    def create(self, **kwargs):
        _SIGNATURE.bind(None, **kwargs)
        raise _Bound


@pytest.fixture
def sdk_signature_checked(storage, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
    get_settings.cache_clear()
    monkeypatch.setattr("app.interpreter.anthropic.Anthropic", _BindingClient)
    monkeypatch.setattr("app.catalog.anthropic.Anthropic", _BindingClient)


def test_the_drafting_call_matches_the_installed_sdk(sdk_signature_checked):
    with pytest.raises(_Bound):
        interpret("track when someone bookmarks a product", business_value="measures intent")


def test_the_review_call_matches_the_installed_sdk(sdk_signature_checked):
    definition = EventDefinition.model_validate(
        {
            "name": "Product Bookmarked",
            "category": "Wishlisting",
            "description": "User bookmarked a product to revisit later.",
            "properties": [{"name": "product_id", "type": "string", "required": True}],
        }
    )
    with pytest.raises(_Bound):
        review_against_catalog(definition, raw_intake_text="track product bookmarks")
