"""Unit tests for the Notion approval-board mapping. The client is mocked, so the suite
never touches the network. Run from backend/: pytest
"""

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.notion_publisher import (
    ApprovalRow,
    build_properties,
    push_request,
    row_from_request,
)

FULL_ROW = ApprovalRow(
    name="Cart Cleared",
    submitter_name="Calvin",
    call_type="track",
    side="Client",
    pii_flagged=True,
    pii_details="email -> email",
    properties_summary="cart_id (string)",
    description="Fired when a cart is emptied.",
    category="Core Ordering",
    submitter_team="Data",
)


class BuildPropertiesTest(unittest.TestCase):
    def test_field_to_property_mapping(self):
        props = build_properties(FULL_ROW, "2026-01-01T00:00:00+00:00")
        self.assertEqual(props["Event Name"]["title"][0]["text"]["content"], "Cart Cleared")
        self.assertEqual(props["Status"]["select"]["name"], "Pending")
        self.assertEqual(props["Submitter"]["rich_text"][0]["text"]["content"], "Calvin")
        self.assertEqual(props["Team"]["select"]["name"], "Data")
        self.assertIs(props["PII Flagged"]["checkbox"], True)
        self.assertEqual(props["PII Details"]["rich_text"][0]["text"]["content"], "email -> email")
        self.assertIs(props["PII Acknowledged"]["checkbox"], False)
        self.assertEqual(props["Call Type"]["select"]["name"], "track")
        self.assertEqual(props["Side"]["select"]["name"], "Client")
        self.assertEqual(props["Properties"]["rich_text"][0]["text"]["content"], "cart_id (string)")
        self.assertEqual(props["Category"]["select"]["name"], "Core Ordering")
        self.assertEqual(props["Submitted At"]["date"]["start"], "2026-01-01T00:00:00+00:00")

    def test_optional_selects_are_guarded(self):
        row = ApprovalRow(
            name="X", submitter_name="", call_type="track", side="Client",
            pii_flagged=False, pii_details="", properties_summary="",
            submitter_team=None, category=None, destinations=[],
        )
        props = build_properties(row, "t")
        self.assertNotIn("Team", props)
        self.assertNotIn("Category", props)
        self.assertNotIn("Destinations", props)


class RowFromRequestTest(unittest.TestCase):
    def test_derives_summary_and_defaults_call_type_and_side(self):
        request = {
            "parsed_definition": {
                "name": "Cart Cleared",
                "category": "Core Ordering",
                "description": "d",
                "properties": [
                    {"name": "cart_id", "type": "string"},
                    {"name": "total", "type": "number"},
                ],
            },
            "submitter_name": "Calvin",
            "submitter_team": "Data",
            "call_type": None,
            "side": None,
            "pii_flagged": False,
            "pii_details": None,
        }
        row = row_from_request(request)
        self.assertEqual(row.properties_summary, "cart_id (string), total (number)")
        self.assertEqual(row.call_type, "track")
        self.assertEqual(row.side, "Client")


class PushRequestTest(unittest.TestCase):
    def test_skips_silently_without_token(self):
        with patch(
            "app.notion_publisher.get_settings",
            return_value=SimpleNamespace(notion_token="", notion_approval_db_id=""),
        ):
            self.assertIsNone(push_request({"parsed_definition": {}}))

    def test_pushes_with_mocked_client(self):
        client = MagicMock()
        client.pages.create.return_value = {"url": "https://notion.so/page-123"}
        request = {
            "parsed_definition": {
                "name": "Cart Cleared",
                "category": "Core Ordering",
                "properties": [{"name": "cart_id", "type": "string"}],
            },
            "submitter_name": "Calvin",
            "submitter_team": "Data",
            "call_type": "track",
            "side": "Client",
            "pii_flagged": False,
            "pii_details": "",
        }
        with patch("app.notion_publisher._client", return_value=client), patch(
            "app.notion_publisher.get_settings",
            return_value=SimpleNamespace(notion_token="x", notion_approval_db_id="db-123"),
        ):
            url = push_request(request)

        self.assertEqual(url, "https://notion.so/page-123")
        client.pages.create.assert_called_once()
        kwargs = client.pages.create.call_args.kwargs
        self.assertEqual(kwargs["parent"], {"database_id": "db-123"})
        self.assertEqual(
            kwargs["properties"]["Event Name"]["title"][0]["text"]["content"], "Cart Cleared"
        )
        self.assertEqual(kwargs["properties"]["Team"]["select"]["name"], "Data")


if __name__ == "__main__":
    unittest.main()
