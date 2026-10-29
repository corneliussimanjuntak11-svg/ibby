import re
from datetime import date, datetime

_ORDINAL_RE = re.compile(r"(\d{1,2})(st|nd|rd|th)\b", re.IGNORECASE)
_ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_AMBIGUOUS_NUMERIC_RE = re.compile(r"^\d{1,4}[/.\-]\d{1,4}([/.\-]\d{1,4})?$")

_MONTH_DAY_YEAR_FORMATS = ["%B %d %Y", "%b %d %Y"]
_DAY_MONTH_YEAR_FORMATS = ["%d %B %Y", "%d %b %Y"]
_MONTH_DAY_FORMATS = ["%B %d", "%b %d"]
_DAY_MONTH_FORMATS = ["%d %B", "%d %b"]


def parse_natural_date(text):
    """
    Parses a date written the way people naturally type it: 'May 5th 2026',
    'May 5, 2026', '5 May 2026', '5th of May 2026', 'may 5 2026', with full or
    abbreviated month names, any capitalization, and optional ordinal suffixes.
    Also accepts the unambiguous YYYY-MM-DD fallback. Purely numeric formats like
    5/5/2026 are rejected since they're ambiguous. If the year is left out, the
    next upcoming occurrence of that date is assumed.

    Returns a datetime.date, or None if the text can't be understood.
    """
    if not text:
        return None

    cleaned = text.strip()

    # Unambiguous ISO fallback.
    if _ISO_RE.match(cleaned):
        try:
            return datetime.strptime(cleaned, "%Y-%m-%d").date()
        except ValueError:
            return None

    # Reject ambiguous purely-numeric dates like 5/5/2026 or 05-05-26.
    if _AMBIGUOUS_NUMERIC_RE.match(cleaned):
        return None

    # Normalize: drop ordinal suffixes, the word "of", commas, and extra whitespace.
    normalized = _ORDINAL_RE.sub(r"\1", cleaned)
    normalized = re.sub(r"\bof\b", " ", normalized, flags=re.IGNORECASE)
    normalized = normalized.replace(",", " ")
    normalized = re.sub(r"\s+", " ", normalized).strip()

    has_year = bool(re.search(r"\b\d{4}\b", normalized))
    formats = (
        _MONTH_DAY_YEAR_FORMATS + _DAY_MONTH_YEAR_FORMATS
        if has_year
        else _MONTH_DAY_FORMATS + _DAY_MONTH_FORMATS
    )

    for fmt in formats:
        try:
            parsed = datetime.strptime(normalized, fmt)
        except ValueError:
            continue

        if has_year:
            return parsed.date()

        # No year given: assume the next upcoming occurrence of that date.
        today = date.today()
        candidate = parsed.date().replace(year=today.year)
        if candidate < today:
            candidate = candidate.replace(year=today.year + 1)
        return candidate

    return None


def format_natural_date(d):
    """Formats a date like 'May 5th, 2026', with the correct ordinal suffix for the day."""
    day = d.day
    if 11 <= day % 100 <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
    return f"{d.strftime('%B')} {day}{suffix}, {d.year}"
