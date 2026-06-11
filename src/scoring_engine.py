import json
import re
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse

from db import get_connection


SCORING_VERSION = "rules_v0.7"


ELIGIBILITY_FAIL_PHRASES = [
    "60% ami",
    "80% ami",
    "ami",
    "mfte",
    "income restricted",
    "income-restricted",
    "affordable housing",
    "household income limit",
    "income limit",
    "must qualify",
    "lottery",
    "senior housing",
    "senior-only",
    "student housing",
    "student-only",
    "co-living",
    "coliving",
    "shared room",
    "roommate",
    "roommates",
]

SCAM_HIGH_RISK_PHRASES = [
    "western union",
    "moneygram",
    "wire transfer",
    "send deposit before viewing",
    "deposit before viewing",
    "landlord out of the country",
    "out of the country",
    "kindly reply",
]

KNOWN_CORPORATE_DOMAINS = [
    "greystar.leasehomenow.com",
    "blantonturner.touraptnow.com",
    "livecushwake.com",
    "leaseaptsnow.com",
    "liveindigorealestate.com",
    "hiveapartments.com",
    "cornellandassociates.com",
    "apartments.bellwetherhousing.org",
    "petscreening.com",
    "rentseattle.com",
    "showmojo.com",
    "tenantturner.com",
    "rentcafe.com",
    "yardi.com",
    "entrata.com",
]

URL_PATTERN = re.compile(
    r"(https?://[^\s]+|www\.[^\s]+|[a-zA-Z0-9.-]+\.(com|net|org|co)[^\s]*)",
    re.IGNORECASE,
)

OWNER_EXPLICIT_POSITIVE_PHRASES = [
    "owner",
    "owner managed",
    "owner-managed",
    "private landlord",
    "family owned",
    "family-owned",
    "by owner",
    "my house",
    "my home",
    "our house",
    "our home",
    "we lived here",
    "i lived here",
    "i am renting",
    "we are renting",
    "long-term tenant",
    "long term tenant",
    "current tenant",
    "previous tenant",
    "tell us about yourself",
    "tell me about yourself",
    "looking for someone",
    "looking for a tenant",
    "good tenant",
]

OWNER_STRONG_POSITIVE_PHRASES = [
    "family home",
    "owners live",
    "owner lives",
    "owners who live",
    "owner lives onsite",
    "owners live onsite",
    "live in the upper two floors",
    "upper two floors",
    "shared laundry with owners",
    "all utilities included",
    "utilities included",
    "deposit can be paid",
    "flexible move in date",
    "flexible move-in date",
    "mother-in-law",
    "mother in law",
    "in-law",
    "mil apt",
    "garden entrance",
    "garden level",
    "daylight basement",
    "basement apartment",
    "carriage house",
    "pride of ownership",
    "separate back house",
    "back house",
    "adu",
]

OWNER_STYLE_POSITIVE_PHRASES = [
    "private",
    "quiet",
    "no smokers",
    "no smoking",
    "no pets",
    "wsg provided",
    "wsg included",
    "water sewer garbage",
    "shared laundry",
    "shared laundry space",
    "use text",
    "text to make appt",
    "text to make appointment",
    "text if you want photos",
    "text for photos",
    "please text",
    "please call",
    "call/text",
    "text/call",
    "available now",
    "available after",
    "make appt",
    "make appointment",
    "small building",
    "5 unit building",
    "fourplex",
    "triplex",
]

STUDENT_LEASING_NEGATIVE_PHRASES = [
    "leasing for fall",
    "preleasing for fall",
    "pre-leasing for fall",
    "pre leasing for fall",
    "for fall",
    "fall 2026",
    "available fall",
    "student apt",
    "student apartment",
    "student living",
    "student life",
    "student experience",
    "student housing",
    "live study play",
    "high-quality residents",
    "high quality residents",
    "university teachers",
    "college students",
    "large commercial district",
    "commercial district",
    "technicians working",
    "u district community",
    "5-min walk to uw campus",
    "5 mins walk to uw campus",
    "5 mins walk to uw",
    "5 min walk to uw",
    "discount low rent",
    "the last 2 br unit",
    "the last 3 br unit",
    "last 2 br unit",
    "last 3 br unit",
]

OWNER_NEGATIVE_PHRASES = [
    "professionally managed",
    "property management",
    "managed by",
    "leasing office",
    "leasing team",
    "leasing agent",
    "resident portal",
    "schedule your tour",
    "schedule a tour",
    "tour today",
    "book a tour",
    "now leasing",
    "preleasing",
    "pre-leasing",
    "pre leasing",
    "limited time special",
    "special offer",
    "specials available",
    "concession",
    "community amenities",
    "luxury living",
    "apartment community",
    "professionally leased",
    "income requirement",
    "application fee",
    "applications are open",
    "admin fee",
    "pet rent",
    "resident benefits package",
    "equal housing opportunity",
    "call for details",
    "apply now",
    "apply online",
    "online application",
    "floor plans",
    "availability subject to change",
    "pricing subject to change",
    "controlled access community",
    "controlled access building",
    "fitness center",
    "clubhouse",
    "package lockers",
    "roof deck",
    "rooftop deck",
    "legal disclosure",
    "legal-disclosure",
    "unit highlights",
    "community highlights",
    "office hours",
    "private showing",
    "open-concept home",
    "designed for comfort and convenience",
    "before these homes are gone",
    "bright interiors",
    "ultimate access",
    "look and lease",
    "one month free",
    "weeks free",
    "4-wks free",
    "8-weeks free",
    "come tour today",
    "call today",
    "call now",
    "shared amenities",
    "on-site management",
    "onsite management",
    "professional on-site management",
    "professional onsite management",
    "professional on-site maintenance",
    "professional onsite maintenance",
]

HUMAN_POSITIVE_PHRASES = [
    "quiet street",
    "morning light",
    "afternoon light",
    "great neighbors",
    "tell us about yourself",
    "tell me about yourself",
    "looking for someone",
    "looking for a tenant",
    "well cared for",
    "lived here",
    "we loved",
    "i loved",
    "recently replaced",
    "walk to",
    "close to",
    "text if you want photos",
    "text for photos",
    "happy to show",
    "available after",
    "available now",
    "please text",
    "please call",
    "use text",
    "private",
    "quiet",
    "shared laundry",
    "no smokers",
    "no pets",
    "separate back house",
    "back house",
    "small building",
    "family home",
    "owners live",
    "owner lives",
    "carriage house",
    "pride of ownership",
    "garden entrance",
    "daylight basement",
]

HUMAN_NEGATIVE_PHRASES = [
    "elevated living",
    "curated",
    "premier destination",
    "urban oasis",
    "unparalleled",
    "resort-style",
    "resort style",
    "modern lifestyle",
    "vibrant community",
    "luxury awaits",
    "discover your new home",
    "perfect blend of",
    "nestled in the heart",
    "sophisticated",
    "breathtaking",
    "pristine",
    "bright interiors",
    "ultimate access",
    "designed for comfort and convenience",
    "before these homes are gone",
    "leasing for fall",
    "preleasing",
    "pre-leasing",
    "student living",
    "student life",
    "student experience",
    "student housing",
    "high-quality residents",
    "large commercial district",
    "look and lease",
    "one month free",
    "weeks free",
    "specials available",
    "come tour today",
    "call today",
    "call now",
]

TITLE_PROPERTY_TYPE_KEYWORDS = {
    "room": [
        "room for rent",
        "shared room",
        "private room",
        "roommate",
    ],
    "adu": [
        "adu",
        "mother-in-law",
        "mother in law",
        "mil apt",
        "in-law",
        "backyard cottage",
        "detached cottage",
        "garden apt",
        "garden apartment",
    ],
    "duplex": [
        "duplex",
        "triplex",
        "fourplex",
    ],
    "townhouse": [
        "townhouse",
        "townhome",
        "town house",
    ],
    "condo": [
        "condo",
        "condominium",
    ],
    "houseboat": [
        "houseboat",
    ],
    "house": [
        "house",
        "carriage house",
        "single family",
        "single-family",
        "back house",
    ],
    "apartment": [
        "apartment",
        "apt",
        "studio",
        "1 bedroom",
        "1br",
        "2 bedroom",
        "2br",
        "3 bedroom",
        "3br",
    ],
}

DESCRIPTION_PROPERTY_TYPE_KEYWORDS = {
    "room": [
        "room for rent",
        "shared room",
        "private room",
        "roommate",
        "roommates",
    ],
    "adu": [
        "adu",
        "accessory dwelling",
        "mother-in-law",
        "mother in law",
        "mil apt",
        "in-law",
        "backyard cottage",
        "detached cottage",
        "garden apt",
        "garden apartment",
        "daylight basement",
        "basement apartment",
    ],
    "duplex": [
        "duplex",
        "triplex",
        "fourplex",
    ],
    "townhouse": [
        "townhouse",
        "townhome",
        "town house",
    ],
    "condo": [
        "condo",
        "condominium",
    ],
    "houseboat": [
        "houseboat",
    ],
    "house": [
        "carriage house",
        "single family house",
        "single-family house",
        "single family home",
        "single-family home",
        "entire house",
        "whole house",
        "standalone house",
        "detached house",
        "separate back house",
        "back house",
    ],
    "apartment": [
        "apartment",
        "apt",
        "studio",
        "1 bedroom",
        "1br",
        "2 bedroom",
        "2br",
        "3 bedroom",
        "3br",
    ],
}

PROPERTY_TYPE_PREFERENCE = {
    "house": 100,
    "condo": 95,
    "townhouse": 90,
    "houseboat": 85,
    "adu": 80,
    "duplex": 75,
    "apartment": 70,
    "unclear": 50,
    "room": 0,
}


def get_utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_text(*parts: Optional[str]) -> str:
    combined = " ".join(part or "" for part in parts)
    combined = combined.lower()
    combined = re.sub(r"\s+", " ", combined)
    return combined.strip()


def phrase_to_regex(phrase: str) -> re.Pattern:
    escaped = re.escape(phrase.lower())
    escaped = escaped.replace(r"\ ", r"\s+")

    starts_word = phrase[0].isalnum()
    ends_word = phrase[-1].isalnum()

    pattern = escaped

    if starts_word:
        pattern = r"\b" + pattern

    if ends_word:
        pattern = pattern + r"\b"

    return re.compile(pattern, re.IGNORECASE)


def find_phrase_hits(text: str, phrases: list[str]) -> list[str]:
    hits = []

    for phrase in phrases:
        pattern = phrase_to_regex(phrase)
        if pattern.search(text):
            hits.append(phrase)

    return hits


def clamp_score(score: int) -> int:
    return max(0, min(100, score))


def extract_urls(text: str) -> list[str]:
    return [match.group(0).rstrip(".,)") for match in URL_PATTERN.finditer(text)]


def normalize_domain(url: str) -> str:
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url

    parsed = urlparse(url)
    domain = parsed.netloc.lower()

    if domain.startswith("www."):
        domain = domain[4:]

    return domain


def detect_url_and_domain_signals(text: str) -> tuple[list[str], list[str], list[str]]:
    urls = extract_urls(text)
    domains = []

    for url in urls:
        try:
            domain = normalize_domain(url)
            if domain:
                domains.append(domain)
        except Exception:
            continue

    known_corporate_hits = []

    for domain in domains:
        for known_domain in KNOWN_CORPORATE_DOMAINS:
            if known_domain in domain or domain in known_domain:
                known_corporate_hits.append(domain)

    return urls, sorted(set(domains)), sorted(set(known_corporate_hits))


def detect_named_apartment_building(title: Optional[str], text: str) -> tuple[bool, list[str]]:
    reasons = []
    title_text = normalize_text(title)

    if "apartments" in title_text or "apts" in title_text:
        reasons.append("Title appears to name an apartment building")

    if " apartments is " in f" {text} ":
        reasons.append("Description uses named-apartment-building pattern: 'Apartments is'")

    if " apartments are " in f" {text} ":
        reasons.append("Description uses named-apartment-building pattern: 'Apartments are'")

    return bool(reasons), reasons


def determine_eligibility(text: str) -> tuple[str, list[str]]:
    hits = find_phrase_hits(text, ELIGIBILITY_FAIL_PHRASES)

    if hits:
        return "fail", [f"Eligibility phrase detected: {hit}" for hit in hits[:5]]

    return "pass", []


def determine_scam_risk(text: str) -> tuple[str, list[str]]:
    hits = find_phrase_hits(text, SCAM_HIGH_RISK_PHRASES)

    if hits:
        return "high", [f"Scam-risk phrase detected: {hit}" for hit in hits[:5]]

    return "low", []


def looks_like_simple_private_post(
    text: str,
    description: Optional[str],
    corporate_hits: list[str],
    student_leasing_hits: list[str],
    urls: list[str],
    known_corporate_domains: list[str],
) -> tuple[bool, list[str]]:
    reasons = []
    description_length = len(description or "")

    direct_contact_hits = find_phrase_hits(
        text,
        [
            "use text",
            "text to make appt",
            "text to make appointment",
            "text if you want photos",
            "text for photos",
            "please text",
            "please call",
            "call/text",
            "text/call",
        ],
    )

    practical_detail_hits = find_phrase_hits(
        text,
        [
            "wsg provided",
            "wsg included",
            "water sewer garbage",
            "no smokers",
            "no smoking",
            "no pets",
            "shared laundry",
            "shared laundry space",
            "1st floor",
            "first floor",
            "private",
            "quiet",
            "available now",
            "make appt",
            "make appointment",
        ],
    )

    location_detail_hits = find_phrase_hits(
        text,
        [
            "close to uw",
            "uw",
            "burke",
            "bg trail",
            "lake union",
            "lk union",
            "gasworks",
            "gas works",
            "bus line",
            "downtown seattle",
            "restaurants",
            "pubs",
        ],
    )

    if direct_contact_hits:
        reasons.append(f"Direct personal-contact language: {direct_contact_hits[:3]}")

    if practical_detail_hits:
        reasons.append(f"Practical unit-specific details: {practical_detail_hits[:4]}")

    if location_detail_hits:
        reasons.append(f"Specific local-location clues: {location_detail_hits[:4]}")

    if 80 <= description_length <= 900:
        reasons.append("Short/medium description, less like a large corporate template")

    is_simple_private_post = (
        len(corporate_hits) == 0
        and len(student_leasing_hits) == 0
        and len(urls) == 0
        and len(known_corporate_domains) == 0
        and len(direct_contact_hits) >= 1
        and len(practical_detail_hits) >= 2
    )

    return is_simple_private_post, reasons


def score_owner_signal(
    title: Optional[str],
    text: str,
    description: Optional[str],
) -> tuple[int, list[str]]:
    explicit_positive_hits = find_phrase_hits(text, OWNER_EXPLICIT_POSITIVE_PHRASES)
    strong_positive_hits = find_phrase_hits(text, OWNER_STRONG_POSITIVE_PHRASES)
    style_positive_hits = find_phrase_hits(text, OWNER_STYLE_POSITIVE_PHRASES)
    corporate_hits = find_phrase_hits(text, OWNER_NEGATIVE_PHRASES)
    student_leasing_hits = find_phrase_hits(text, STUDENT_LEASING_NEGATIVE_PHRASES)
    urls, domains, known_corporate_domains = detect_url_and_domain_signals(text)
    named_apartment_building, named_apartment_reasons = detect_named_apartment_building(title, text)

    score = 45
    score += len(explicit_positive_hits) * 16
    score += len(strong_positive_hits) * 12
    score += len(style_positive_hits) * 5
    score -= len(corporate_hits) * 20
    score -= len(student_leasing_hits) * 24

    reasons = []
    reasons.extend([f"Explicit owner/private-landlord phrase: {hit}" for hit in explicit_positive_hits[:8]])
    reasons.extend([f"Strong owner/private-landlord pattern: {hit}" for hit in strong_positive_hits[:8]])
    reasons.extend([f"Private/small-landlord style phrase: {hit}" for hit in style_positive_hits[:8]])
    reasons.extend([f"Corporate/property-management phrase: {hit}" for hit in corporate_hits[:8]])
    reasons.extend([f"Student/fall-leasing phrase: {hit}" for hit in student_leasing_hits[:8]])

    if urls:
        reasons.append(f"URL(s) detected in description: {urls[:5]}")

    if domains:
        reasons.append(f"Domain(s) detected: {domains[:5]}")

    if known_corporate_domains:
        reasons.append(f"Known corporate/property-management domain(s): {known_corporate_domains[:5]}")

    if named_apartment_building:
        reasons.extend(named_apartment_reasons)

    simple_private_post, simple_private_reasons = looks_like_simple_private_post(
        text=text,
        description=description,
        corporate_hits=corporate_hits,
        student_leasing_hits=student_leasing_hits,
        urls=urls,
        known_corporate_domains=known_corporate_domains,
    )

    if simple_private_post:
        score += 30
        reasons.append("Looks like a terse private Craigslist post rather than corporate leasing copy")
        reasons.extend(simple_private_reasons)

    if strong_positive_hits:
        score += 18
        reasons.append("Owner-onsite/family-home/MIL/carriage-house pattern gets extra boost")

    if re.search(r"\bplease\s+(call|text)\s+[a-z]+", text):
        score += 8
        reasons.append("Direct contact with a named person")

    if re.search(r"\b\d+\s*unit building\b", text):
        score += 10
        reasons.append("Small-building phrase detected")

    if "separate back house" in text or "back house" in text:
        score += 12
        reasons.append("Separate/back-house pattern detected")

    if "adu" in text:
        score += 8
        reasons.append("ADU pattern detected")

    if "carriage house" in text:
        score += 12
        reasons.append("Carriage-house pattern detected")

    if named_apartment_building:
        score -= 18
        reasons.append("Named apartment building reduces owner/private-landlord confidence")

    if urls:
        score -= 20
        reasons.append("URL presence is a corporate/leasing-funnel red flag")

    if known_corporate_domains:
        score = min(score, 10)
        reasons.append("Known corporate/property-management domain caps Owner Signal at 10")

    elif urls:
        score = min(score, 35)
        reasons.append("Generic URL presence caps Owner Signal at 35")

    if len(student_leasing_hits) >= 1:
        score = min(score, 25)
        reasons.append("Student/fall-leasing pattern caps Owner Signal at 25")

    if len(corporate_hits) >= 2:
        score -= 25
        reasons.append("Multiple corporate/property-management markers detected")

    if len(corporate_hits) >= 4:
        score = min(score, 15)
        reasons.append("Strong corporate pattern; Owner Signal capped at 15")

    return clamp_score(score), reasons


def score_human_signal(text: str, description: Optional[str]) -> tuple[int, list[str]]:
    positive_hits = find_phrase_hits(text, HUMAN_POSITIVE_PHRASES)
    negative_hits = find_phrase_hits(text, HUMAN_NEGATIVE_PHRASES)
    student_leasing_hits = find_phrase_hits(text, STUDENT_LEASING_NEGATIVE_PHRASES)
    urls, domains, known_corporate_domains = detect_url_and_domain_signals(text)

    description_length = len(description or "")

    score = 50
    score += len(positive_hits) * 8
    score -= len(negative_hits) * 12
    score -= len(student_leasing_hits) * 10

    reasons = []
    reasons.extend([f"Human-written phrase: {hit}" for hit in positive_hits[:8]])
    reasons.extend([f"Marketing-copy phrase: {hit}" for hit in negative_hits[:8]])
    reasons.extend([f"Student/fall-leasing phrase: {hit}" for hit in student_leasing_hits[:8]])

    if 80 <= description_length <= 900:
        score += 12
        reasons.append("Concise description with practical details")

    if 250 <= description_length <= 1200:
        score += 5
        reasons.append("Description has enough detail without looking like a huge template")

    if description_length >= 1800:
        score -= 15
        reasons.append("Very long description may be templated marketing copy")

    if description_length < 60:
        score -= 12
        reasons.append("Very short description")

    if urls:
        score -= 12
        reasons.append("URL presence makes the post feel less like direct human/private writing")

    if known_corporate_domains:
        score = min(score, 45)
        reasons.append("Known corporate/property-management domain caps Human Signal at 45")

    if student_leasing_hits:
        score = min(score, 55)
        reasons.append("Student/fall-leasing pattern caps Human Signal at 55")

    return clamp_score(score), reasons


def classify_property_type(title: Optional[str], text: str) -> tuple[str, int, list[str]]:
    title_text = normalize_text(title)

    priority = [
        "room",
        "adu",
        "duplex",
        "townhouse",
        "condo",
        "houseboat",
        "house",
        "apartment",
    ]

    for property_type in priority:
        hits = find_phrase_hits(title_text, TITLE_PROPERTY_TYPE_KEYWORDS[property_type])
        if hits:
            return (
                property_type,
                PROPERTY_TYPE_PREFERENCE[property_type],
                [f"Title property type keyword: {hit}" for hit in hits[:3]],
            )

    detected = []

    for property_type, keywords in DESCRIPTION_PROPERTY_TYPE_KEYWORDS.items():
        hits = find_phrase_hits(text, keywords)
        if hits:
            detected.append((property_type, hits))

    if not detected:
        return "unclear", PROPERTY_TYPE_PREFERENCE["unclear"], ["No clear property type detected"]

    for property_type in priority:
        for detected_type, hits in detected:
            if detected_type == property_type:
                return (
                    property_type,
                    PROPERTY_TYPE_PREFERENCE[property_type],
                    [f"Description property type keyword: {hit}" for hit in hits[:3]],
                )

    return "unclear", PROPERTY_TYPE_PREFERENCE["unclear"], ["No clear property type detected"]


def score_fit(
    text: str,
    bedrooms: Optional[float],
    property_type: str,
) -> tuple[int, list[str]]:
    score = 50
    reasons = []

    inferred_bedrooms = bedrooms

    if inferred_bedrooms is None:
        bedroom_match = re.search(r"(\d+)\s*(br|bed|bedroom)", text)
        if bedroom_match:
            inferred_bedrooms = float(bedroom_match.group(1))

    if inferred_bedrooms is None:
        score -= 5
        reasons.append("Bedroom count unclear")
    elif 2 <= inferred_bedrooms <= 3:
        score += 35
        reasons.append("Preferred 2-3 bedroom range")
    elif inferred_bedrooms == 1:
        score += 15
        reasons.append("Acceptable 1 bedroom")
    elif inferred_bedrooms > 3:
        score -= 10
        reasons.append("More than 3 bedrooms")
    else:
        score -= 20
        reasons.append("Bedroom count outside preference")

    if re.search(r"\b(den|office|study|sunroom)\b", text):
        score += 10
        reasons.append("Mentions den/office/study/sunroom")

    if property_type == "room":
        score = 0
        reasons.append("Room/shared setup is not a fit")

    if property_type == "houseboat":
        score += 5
        reasons.append("Houseboat is unusual but potentially worth reviewing")

    return clamp_score(score), reasons


def calculate_grey_cells_score(
    eligibility_status: str,
    scam_risk_status: str,
    owner_signal_score: int,
    human_signal_score: int,
    fit_score: int,
) -> Optional[int]:
    if eligibility_status == "fail":
        return None

    if scam_risk_status == "high":
        return None

    return round(
        owner_signal_score * 0.70
        + human_signal_score * 0.20
        + fit_score * 0.10
    )


def get_listings_to_score(conn) -> list:
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            l.listing_id,
            l.title,
            l.price,
            l.neighborhood,
            d.description,
            d.bedrooms,
            d.bathrooms,
            d.sqft
        FROM listing l
        JOIN listing_detail d
            ON l.listing_id = d.listing_id
        WHERE d.fetch_status = 'success'
        ORDER BY l.listing_id ASC;
        """
    )

    return cursor.fetchall()


def save_score(conn, score_record: dict) -> None:
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO listing_score (
            listing_id,
            scored_at,
            scoring_version,

            eligibility_status,
            eligibility_reasons,

            scam_risk_status,
            scam_risk_reasons,

            owner_signal_score,
            owner_signal_reasons,

            human_signal_score,
            human_signal_reasons,

            property_type,
            property_type_score,
            property_type_reasons,

            fit_score,
            fit_reasons,

            grey_cells_score
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """,
        (
            score_record["listing_id"],
            score_record["scored_at"],
            score_record["scoring_version"],
            score_record["eligibility_status"],
            json.dumps(score_record["eligibility_reasons"]),
            score_record["scam_risk_status"],
            json.dumps(score_record["scam_risk_reasons"]),
            score_record["owner_signal_score"],
            json.dumps(score_record["owner_signal_reasons"]),
            score_record["human_signal_score"],
            json.dumps(score_record["human_signal_reasons"]),
            score_record["property_type"],
            score_record["property_type_score"],
            json.dumps(score_record["property_type_reasons"]),
            score_record["fit_score"],
            json.dumps(score_record["fit_reasons"]),
            score_record["grey_cells_score"],
        ),
    )


def clear_scores_for_version(conn, scoring_version: str) -> None:
    cursor = conn.cursor()

    cursor.execute(
        """
        DELETE FROM listing_score
        WHERE scoring_version = ?;
        """,
        (scoring_version,),
    )


def score_listing(row: tuple) -> dict:
    (
        listing_id,
        title,
        price,
        neighborhood,
        description,
        bedrooms,
        bathrooms,
        sqft,
    ) = row

    text = normalize_text(title, neighborhood, description)

    eligibility_status, eligibility_reasons = determine_eligibility(text)
    scam_risk_status, scam_risk_reasons = determine_scam_risk(text)

    owner_signal_score, owner_signal_reasons = score_owner_signal(title, text, description)
    human_signal_score, human_signal_reasons = score_human_signal(text, description)

    property_type, property_type_score, property_type_reasons = classify_property_type(title, text)

    fit_score, fit_reasons = score_fit(
        text=text,
        bedrooms=bedrooms,
        property_type=property_type,
    )

    grey_cells_score = calculate_grey_cells_score(
        eligibility_status=eligibility_status,
        scam_risk_status=scam_risk_status,
        owner_signal_score=owner_signal_score,
        human_signal_score=human_signal_score,
        fit_score=fit_score,
    )

    return {
        "listing_id": listing_id,
        "scored_at": get_utc_now(),
        "scoring_version": SCORING_VERSION,
        "eligibility_status": eligibility_status,
        "eligibility_reasons": eligibility_reasons,
        "scam_risk_status": scam_risk_status,
        "scam_risk_reasons": scam_risk_reasons,
        "owner_signal_score": owner_signal_score,
        "owner_signal_reasons": owner_signal_reasons,
        "human_signal_score": human_signal_score,
        "human_signal_reasons": human_signal_reasons,
        "property_type": property_type,
        "property_type_score": property_type_score,
        "property_type_reasons": property_type_reasons,
        "fit_score": fit_score,
        "fit_reasons": fit_reasons,
        "grey_cells_score": grey_cells_score,
    }


def run_scoring_engine() -> None:
    conn = get_connection()

    listings = get_listings_to_score(conn)

    if not listings:
        print("No successfully fetched listing details to score.")
        conn.close()
        return

    print(f"ScoringEngine will score {len(listings)} listings.")

    clear_scores_for_version(conn, SCORING_VERSION)

    for row in listings:
        score_record = score_listing(row)
        save_score(conn, score_record)

    conn.commit()

    print("ScoringEngine complete.")

    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT
            l.listing_id,
            l.title,
            l.price,
            s.grey_cells_score,
            s.owner_signal_score,
            s.human_signal_score,
            s.fit_score,
            s.property_type
        FROM listing_score s
        JOIN listing l
            ON s.listing_id = l.listing_id
        WHERE s.scoring_version = ?
        ORDER BY s.grey_cells_score DESC
        LIMIT 10;
        """,
        (SCORING_VERSION,),
    )

    print("\nShortlist preview:")
    for row in cursor.fetchall():
        print(row)

    conn.close()


if __name__ == "__main__":
    run_scoring_engine()