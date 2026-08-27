from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

ANONYMOUS_USERS = {"anonymous"}
ANONYMOUS_HOSTS = {"anonymous.invalid"}
PRIVACY_TOKENS_REQUESTING_ID = {"id", "header", "user", "session", "critical"}

Source = Literal["pai", "rpid", "from", "none"]


@dataclass(frozen=True)
class CallerId:
    number: str | None
    display_name: str | None
    anonymous: bool
    source: Source


def normalize_phone_number(user: str) -> str:
    """Normalize a SIP/tel URI user part into a plain domestic phone number.

    Strips a leading Japan country-code prefix ("+81" or "0081") in favor of
    the domestic "0"-prefixed form, and any trailing URI parameters.
    """
    value = user.split(";", 1)[0]
    if value.startswith("+81"):
        value = "0" + value[3:]
    elif value.startswith("0081"):
        value = "0" + value[4:]
    return value


def _parse_uri_field(value: str) -> tuple[str | None, str | None, bool]:
    """Parse a From/P-Asserted-Identity/Remote-Party-ID style header value.

    Returns (number, display_name, is_anonymous_marker).
    """
    value = value.strip()
    if not value:
        return None, None, False

    display: str | None = None
    remainder = value

    if remainder.startswith('"'):
        end_quote = remainder.find('"', 1)
        if end_quote != -1:
            display = remainder[1:end_quote]
            remainder = remainder[end_quote + 1 :].strip()

    if "<" in remainder:
        start = remainder.find("<")
        end = remainder.find(">", start)
        end = end if end != -1 else len(remainder)
        uri = remainder[start + 1 : end]
        if display is None:
            leading = remainder[:start].strip()
            display = leading or None
    else:
        uri = remainder.split(";", 1)[0].strip()

    scheme, _, rest = uri.partition(":")
    scheme = scheme.lower()
    if scheme not in ("sip", "sips", "tel"):
        return None, display, False

    userinfo, _, hostport = rest.partition("@")
    user = userinfo.split(";", 1)[0]
    host = hostport.split(";", 1)[0].split(":", 1)[0].lower()

    if user.lower() in ANONYMOUS_USERS or host in ANONYMOUS_HOSTS:
        return None, display, True

    if not user:
        return None, display, False

    return normalize_phone_number(user), display, False


def _requests_id_privacy(headers: dict[str, str]) -> bool:
    privacy = (headers.get("privacy") or "").lower()
    if not privacy:
        return False
    tokens = set(re.split(r"[;,\s]+", privacy))
    tokens.discard("")
    if "none" in tokens:
        return False
    return bool(tokens & PRIVACY_TOKENS_REQUESTING_ID)


def parse_caller_id(headers: dict[str, str]) -> CallerId:
    """Resolve the caller's phone number from a parsed SIP header dict.

    Precedence: P-Asserted-Identity > Remote-Party-ID > From, since PAI is the
    carrier-network-asserted identity and is the most trustworthy of the
    three within a trusted domain (RFC 3325).
    """
    candidates: list[tuple[Source, str | None]] = [
        ("pai", headers.get("p-asserted-identity")),
        ("rpid", headers.get("remote-party-id")),
        ("from", headers.get("from")),
    ]

    anonymous_source: Source | None = None
    anonymous_display: str | None = None

    for source, raw_value in candidates:
        if not raw_value:
            continue
        number, display, is_anonymous = _parse_uri_field(raw_value)
        if number:
            return CallerId(number=number, display_name=display, anonymous=False, source=source)
        if is_anonymous and anonymous_source is None:
            anonymous_source = source
            anonymous_display = display

    if anonymous_source is not None:
        return CallerId(number=None, display_name=anonymous_display, anonymous=True, source=anonymous_source)

    if _requests_id_privacy(headers):
        return CallerId(number=None, display_name=None, anonymous=True, source="none")

    return CallerId(number=None, display_name=None, anonymous=False, source="none")
