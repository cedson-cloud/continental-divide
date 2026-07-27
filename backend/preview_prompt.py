"""Render the drafting prompts to disk for review. Makes no API call.

Writes one system prompt per governance template and three user-message variants
into backend/data/prompt_preview/ (gitignored). Run from the repo root:

    backend/.venv/bin/python backend/preview_prompt.py
"""

from pathlib import Path

from app.governance import load_profile
from app.interpreter import build_system_prompt, build_user_message

BACKEND_DIR = Path(__file__).resolve().parent
TEMPLATES = BACKEND_DIR.parent / "governance" / "templates"
PREVIEW_DIR = BACKEND_DIR / "data" / "prompt_preview"

INTAKE_TEXT = (
    "track when a shopper applies a discount code at checkout, and capture the code "
    "and the order total"
)
BUSINESS_VALUE = (
    "Merchandising wants to know which discount codes actually drive completed "
    "orders before renewing the spring campaign."
)


def main() -> None:
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)

    outputs = {}
    for template in sorted(TEMPLATES.glob("*.yaml")):
        profile = load_profile(template)
        outputs[f"system__{template.stem}.txt"] = build_system_prompt(profile)

    outputs["user__with_why.txt"] = build_user_message(
        INTAKE_TEXT, business_value=BUSINESS_VALUE
    )
    outputs["user__without_why.txt"] = build_user_message(INTAKE_TEXT)
    outputs["user__property_on_existing.txt"] = build_user_message(
        INTAKE_TEXT,
        business_value=BUSINESS_VALUE,
        request_kind="new_property_on_existing",
        existing_event="Coupon Applied",
    )

    for filename, text in outputs.items():
        path = PREVIEW_DIR / filename
        path.write_text(text + "\n")
        print(path)


if __name__ == "__main__":
    main()
