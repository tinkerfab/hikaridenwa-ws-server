"""Raw SIP INVITE fixtures used by the header-extraction and caller-ID tests.

These are hand-authored examples following RFC 3261/3325 conventions, not
captures from a real HGW. Milestone 0 (see the implementation plan) replaces
the anonymous-call assumptions here with real captured headers once available.
"""

INVITE_DISCLOSED_CALLER = (
    "INVITE sip:2@192.168.1.1 SIP/2.0\r\n"
    "Via: SIP/2.0/UDP 203.0.113.5:5060;branch=z9hG4bK-1\r\n"
    "Max-Forwards: 70\r\n"
    'From: "0312345678" <sip:0312345678@203.0.113.5;user=phone>;tag=9hx8ytr7\r\n'
    "To: <sip:2@192.168.1.1>\r\n"
    "Call-ID: abc123@203.0.113.5\r\n"
    "CSeq: 1 INVITE\r\n"
    "P-Asserted-Identity: <sip:0312345678@203.0.113.5>\r\n"
    "Contact: <sip:203.0.113.5:5060>\r\n"
    "Content-Length: 0\r\n"
    "\r\n"
)

INVITE_TEL_URI_CALLER = (
    "INVITE sip:2@192.168.1.1 SIP/2.0\r\n"
    "Via: SIP/2.0/UDP 203.0.113.5:5060;branch=z9hG4bK-2\r\n"
    "Max-Forwards: 70\r\n"
    "From: <tel:+81312345678>;tag=aabbcc\r\n"
    "To: <sip:2@192.168.1.1>\r\n"
    "Call-ID: def456@203.0.113.5\r\n"
    "CSeq: 1 INVITE\r\n"
    "P-Asserted-Identity: <tel:+81312345678>\r\n"
    "Content-Length: 0\r\n"
    "\r\n"
)

INVITE_ANONYMOUS_CALLER = (
    "INVITE sip:2@192.168.1.1 SIP/2.0\r\n"
    "Via: SIP/2.0/UDP 203.0.113.5:5060;branch=z9hG4bK-3\r\n"
    "Max-Forwards: 70\r\n"
    'From: "Anonymous" <sip:anonymous@anonymous.invalid>;tag=zz11yy\r\n'
    "To: <sip:2@192.168.1.1>\r\n"
    "Call-ID: ghi789@203.0.113.5\r\n"
    "CSeq: 1 INVITE\r\n"
    "Privacy: id\r\n"
    "Content-Length: 0\r\n"
    "\r\n"
)

INVITE_RPID_ONLY = (
    "INVITE sip:2@192.168.1.1 SIP/2.0\r\n"
    "Via: SIP/2.0/UDP 203.0.113.5:5060;branch=z9hG4bK-4\r\n"
    "Max-Forwards: 70\r\n"
    'From: "Restricted" <sip:anonymous@anonymous.invalid>;tag=rr22\r\n'
    "To: <sip:2@192.168.1.1>\r\n"
    "Call-ID: jkl012@203.0.113.5\r\n"
    "CSeq: 1 INVITE\r\n"
    'Remote-Party-ID: "0312345678" <sip:0312345678@203.0.113.5>;party=calling;screen=yes;privacy=off\r\n'
    "Content-Length: 0\r\n"
    "\r\n"
)

INVITE_FOLDED_HEADER = (
    "INVITE sip:2@192.168.1.1 SIP/2.0\r\n"
    "Via: SIP/2.0/UDP 203.0.113.5:5060\r\n"
    " ;branch=z9hG4bK-5\r\n"
    "Max-Forwards: 70\r\n"
    'From: "0312345678"\r\n'
    " <sip:0312345678@203.0.113.5>;tag=folded1\r\n"
    "To: <sip:2@192.168.1.1>\r\n"
    "Call-ID: mno345@203.0.113.5\r\n"
    "CSeq: 1 INVITE\r\n"
    "Content-Length: 0\r\n"
    "\r\n"
)

INVITE_NO_IDENTITY_HEADERS = (
    "INVITE sip:2@192.168.1.1 SIP/2.0\r\n"
    "Via: SIP/2.0/UDP 203.0.113.5:5060;branch=z9hG4bK-6\r\n"
    "Max-Forwards: 70\r\n"
    "To: <sip:2@192.168.1.1>\r\n"
    "Call-ID: pqr678@203.0.113.5\r\n"
    "CSeq: 1 INVITE\r\n"
    "Content-Length: 0\r\n"
    "\r\n"
)
