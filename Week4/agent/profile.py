import json
import re

from .config import generate_text


PROFILE_FIELDS = {
    "name",
    "email",
    "budget_pkr",
    "currency",
    "country",
    "timezone",
    "purpose",
    "preferred_city",
    "bedrooms",
    "property_of_interest",
    "start_iso",
    "end_iso",
    "notes",
}


def _local_profile_fallback(user_msg: str, profile: dict) -> dict:
    """
    Lightweight local fallback used only when Gemini profile extraction fails.
    Extracts common real-estate preferences without making guesses.
    """
    text = user_msg.strip()
    lower = text.lower()

    # Bedrooms
    bedroom_patterns = [
        r"(\d+)\s*(?:bedroom|bedrooms|bed|bhk)",
        r"(\d+)\s*(?:بیڈ روم|بیڈروم|bedroom)",
    ]

    for pattern in bedroom_patterns:
        match = re.search(pattern, lower, re.IGNORECASE)
        if match:
            profile["bedrooms"] = int(match.group(1))
            break

    # Common cities
    cities = {
        "lahore": "Lahore",
        "لاہور": "Lahore",
        "islamabad": "Islamabad",
        "اسلام آباد": "Islamabad",
        "islamabad": "Islamabad",
        "karachi": "Karachi",
        "کراچی": "Karachi",
        "rawalpindi": "Rawalpindi",
        "راولپنڈی": "Rawalpindi",
        "faisalabad": "Faisalabad",
        "فیصل آباد": "Faisalabad",
        "multan": "Multan",
        "ملتان": "Multan",
    }

    for key, city in cities.items():
        if key in lower:
            profile["preferred_city"] = city
            break

    # Property type / purpose hints
    if any(x in lower for x in [
        "apartment", "flat", "اپارٹمنٹ", "فلیٹ"
    ]):
        profile.setdefault("notes", "")
        profile["notes"] = (
            profile["notes"] + " Apartment/flat requested."
        ).strip()

    if any(x in lower for x in [
        "house", "home", "گھر", "ہاؤس"
    ]):
        profile.setdefault("notes", "")
        profile["notes"] = (
            profile["notes"] + " House requested."
        ).strip()

    # Purpose
    if any(x in lower for x in [
        "investment", "invest", "سرمایہ کاری"
    ]):
        profile["purpose"] = "investment"

    elif any(x in lower for x in [
        "live", "living", "own use", "اپنے رہنے", "رہنے کے لیے"
    ]):
        profile["purpose"] = "own_use"

    # Email
    email_match = re.search(
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
        text
    )
    if email_match:
        profile["email"] = email_match.group(0)

    return profile


def extract_profile_update(user_msg: str, profile: dict) -> dict:
    """
    Extract only information explicitly stated by the caller.

    Gemini is used normally. If Gemini is temporarily unavailable,
    fall back to lightweight local extraction.
    """
    if not user_msg or not user_msg.strip():
        return profile

    prompt = f"""
Extract ONLY information explicitly stated in this caller message.

Allowed fields:

- name
- email
- budget_pkr
- currency
- country
- timezone
- purpose: investment or own_use
- preferred_city
- bedrooms
- property_of_interest
- start_iso
- end_iso
- notes

Rules:
1. Return ONLY valid JSON.
2. Omit fields that are not explicitly stated.
3. NEVER guess missing information.
4. NEVER invent a timezone.
5. NEVER invent a date or time.
6. budget_pkr must be a number if explicitly stated.
7. bedrooms must be an integer if explicitly stated.
8. property_of_interest should be a property ID such as P001 if explicitly stated.
9. Keep previously known profile information unchanged.

Existing profile:

{json.dumps(profile, default=str)}

Caller message:

{user_msg}
"""

    try:
        raw = generate_text(prompt).strip()

        if raw.startswith("```"):
            raw = raw.replace("```json", "", 1)
            raw = raw.replace("```", "", 1).strip()

        update = json.loads(raw)

        if not isinstance(update, dict):
            return profile

        for key, value in update.items():
            if key not in PROFILE_FIELDS:
                continue

            if value is None:
                continue

            if isinstance(value, str) and not value.strip():
                continue

            profile[key] = value

        return profile

    except Exception as exc:
        print("PROFILE EXTRACTION ERROR - USING LOCAL FALLBACK:", exc)
        return _local_profile_fallback(user_msg, profile)