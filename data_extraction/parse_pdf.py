"""Extract thematic findings and resident quotes from community PDF reports.

For each configured PDF, produces:
  data/processed/community_reports/<slugified_name>.json  — per-report records
  data/processed/community_reports/community_report.json  — combined from all reports
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from pypdf import PdfReader


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = PROJECT_ROOT / "data/raw/community_reports"
OUTPUT_DIR = PROJECT_ROOT / "data/processed/community_reports"
COMBINED_OUTPUT_PATH = OUTPUT_DIR / "community_report.json"

QUOTE_PATTERN = re.compile(r'["“]([^"”]{30,500})["”]')
DETECTION_SUBURBS = ["Newtown", "Glebe", "Redfern", "Surry Hills", "Haymarket"]


# ---------------------------------------------------------------------------
# Per-PDF configuration
# ---------------------------------------------------------------------------

@dataclass
class PDFConfig:
    source: str
    default_suburb: str | None
    findings_pages: set[int]
    section_theme_map: dict[str, str]
    skip_blocks: set[str]
    header_patterns: list[str]
    theme_keywords: dict[str, list[str]]
    min_words: int = 35


COMMUNITY_INSIGHTS_CONFIG = PDFConfig(
    source="Community Insights Report 2024",
    default_suburb=None,
    findings_pages=set(range(5, 24)),
    section_theme_map={
        "Key themes": "Community Themes",
        "Aboriginal and Torres Strait Islander Advisory Panel": "Inclusion",
        "Multicultural Advisory Panel": "Inclusion",
        "Disability (Inclusion) Advisory Panel": "Inclusion",
        "Young people": "Inclusion",
        "A city for people": "Public Spaces",
        "A city that moves": "Transport",
        "An environmentally responsive city": "Environment",
        "A lively, cultural and creative city": "Culture",
        "A city with a future focused economy": "Economy",
        "1. Responsible governance and stewardship": "Governance",
        "2. A leading environmental performer": "Environment",
        "3. Public places for all": "Public Spaces",
        "4. Design excellence and sustainable development": "Design",
        "5. A city for walking, cycling and public transport": "Transport",
        "6. An equitable and inclusive city": "Inclusion",
        "7. Resilient and diverse communities": "Communities",
        "8. A thriving cultural life": "Culture",
        "9. A transformed and innovative economy": "Economy",
        "10. Housing for all": "Housing",
    },
    skip_blocks={
        "Overview",
        "Why we're doing this",
        "How we engaged the community",
        "Our reporting approach",
        "Community insights",
        "Emerging trends",
        "Strategic directions",
        "Advisory panels",
    },
    header_patterns=[
        r"Community insights report 2024\s*",
        r"^Report\s*$",
        r"^December 2024\s*$",
    ],
    theme_keywords={
        "Transport": ["transport", "walking", "cycling", "bike", "footpath", "pedestrian", "metro", "light rail", "bus", "station"],
        "Safety": ["safe", "safety", "violence", "abuse", "neglect", "exploitation", "crime"],
        "Housing": ["housing", "affordable housing", "rent", "cost of living", "displacement", "homes", "density"],
        "Environment": ["climate", "green", "tree", "trees", "waste", "pollution", "waterways", "renewable", "recycling", "emissions", "heatwaves", "flooding"],
        "Culture": ["culture", "creative", "arts", "artists", "nightlife", "performance", "public art", "cultural", "chinatown"],
        "Economy": ["economy", "business", "businesses", "innovation", "entrepreneurship", "tech central", "investment", "jobs"],
        "Public Spaces": ["public space", "parks", "gardens", "shade", "seating", "library", "community centre", "plaza", "greening"],
        "Inclusion": ["inclusive", "inclusion", "equity", "equitable", "diverse", "disability", "multicultural", "racism", "first nations"],
        "Communities": ["community", "communities", "resilience", "resilient", "social connection", "food security", "emergency", "belonging"],
        "Governance": ["governance", "decision-making", "council", "transparency", "engagement", "feedback", "trust"],
        "Design": ["urban design", "design", "development", "building", "infrastructure", "ventilation", "drainage", "sustainable development"],
    },
    min_words=35,
)

HAYMARKET_VISION_CONFIG = PDFConfig(
    source="Haymarket Vision engagement report",
    default_suburb="Haymarket",
    # Main findings: pages 4–62. Verbatim appendices: pages 71–89.
    findings_pages=set(range(4, 63)) | set(range(71, 90)),
    section_theme_map={
        "Summary of key themes": "Community Themes",
        "What makes Haymarket special": "Culture",
        "Why do people go to Haymarket": "Lifestyle",
        "What are the places that people love in Haymarket": "Public Spaces",
        "What can be improved": "Community Themes",
        "Preservation of local character and cultural heritage": "Culture",
        "More lighting to create a safe and colourful atmosphere": "Safety",
        "Greater range of quality, authentic and affordable food and retail options": "Lifestyle",
        "2.2 Summary of forum": "Community Themes",
        "3.5 Describing Haymarket": "Community Themes",
        "3.6 Features in Haymarket": "Community Themes",
        "3.7 Social and cultural significance of Haymarket": "Culture",
        "3.8 Places that are special in Haymarket": "Public Spaces",
        "3.8.1 Dixon Street": "Public Spaces",
        "3.8.2 Paddy's Markets": "Lifestyle",
        "3.8.3 Darling Quarter": "Public Spaces",
        "3.8.4 Chinatown": "Culture",
        "3.8.5 Market City": "Lifestyle",
        "3.8.6 Emperor's Garden Cakes and Bakery (Dixon Street)": "Lifestyle",
        "3.9 Places that could be improved in Haymarket": "Community Themes",
        "3.9.1 Chinatown (overall)": "Culture",
        "3.9.2 Paddy's Market": "Lifestyle",
        "3.9.3 George Street": "Public Spaces",
        "3.9.4 Belmore Park": "Public Spaces",
        "3.9.5 Haymarket (general)": "Community Themes",
        "3.10 Upgrades in Dixon Street and Chinatown": "Public Spaces",
        "3.11 Future look and feel of Haymarket": "Community Themes",
        "3.12 More, the same, or less in the future in Haymarket": "Community Themes",
        "3.13 Additional comments about the future of Haymarket": "Community Themes",
        "4.4 Snapshot of key findings": "Community Themes",
        "4.5.1 Haymarket consultation boards": "Community Themes",
        "4.5.2 Dixon Street consultation boards": "Public Spaces",
        "5.2 Snapshot of face-to-face meetings": "Community Themes",
        "5.3 Summary of written submissions": "Culture",
    },
    skip_blocks={
        "Table of Contents",
        "1. Introduction",
        "1.1 Background",
        "1.2 Engagement purpose and methodology",
        "2. Lord Mayor's Forum",
        "2.1 About the Lord Mayor's Forum",
        "3. Community survey",
        "3.1 About the community survey",
        "3.2 Snapshot of survey findings",
        "3.3 Respondent profile",
        "3.4 Visitation and relationship to Haymarket",
        "4. Consultation board findings",
        "4.1 About the consultation boards",
        "4.2 Dixon Street consultation boards",
        "4.3 Haymarket consultation boards",
        "5. Stakeholder meetings and submissions",
        "5.1 About the stakeholder meetings and submissions",
        "6. Appendices",
    },
    header_patterns=[
        r"^\s*\d*\s*City of Sydney\s*[–\-]\s*Haymarket Vision Engagement Report[^\n]*",
        r"^\s*\d*\s*Cred Consulting\s*$",
    ],
    theme_keywords={
        "Transport": ["transport", "pedestrian", "walking", "cycling", "bike", "footpath", "tram", "bus", "connectivity", "connections", "parking"],
        "Safety": ["safe", "safety", "lighting", "light", "crime", "secure", "unsafe"],
        "Culture": ["culture", "cultural", "heritage", "chinatown", "asian", "history", "chinese", "thai", "korean", "japanese", "lunar new year", "diverse", "multicultural"],
        "Lifestyle": ["restaurant", "cafe", "food", "dining", "nightlife", "retail", "shop", "market", "bar", "entertainment", "events", "festival"],
        "Public Spaces": ["public space", "street", "streetscape", "seating", "park", "laneway", "outdoor", "pedestrian", "plaza", "cleanliness", "maintenance"],
        "Environment": ["green", "tree", "trees", "greenery", "plants", "drainage", "stormwater"],
        "Economy": ["business", "businesses", "trading", "retail", "investment", "development", "commercial"],
        "Community Themes": ["community", "respondents", "future", "improve", "special", "vision", "residents"],
    },
    min_words=20,
)

PDF_CONFIGS: dict[str, PDFConfig] = {
    "Community_Insights_Report_2024.pdf": COMMUNITY_INSIGHTS_CONFIG,
    "Haymarket Vision engagement report.pdf": HAYMARKET_VISION_CONFIG,
}


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def clean_page_text(text: str, header_patterns: list[str]) -> str:
    text = text.replace("­", "")
    text = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", text)
    for pattern in header_patterns:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE | re.MULTILINE)
    text = re.sub(r"^\s*\d+\s*$", "", text, flags=re.MULTILINE)
    # Strip PDF font artifacts: some decorated bullets extract as '?'
    text = re.sub(r"^[?•]\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"(?<!\n)\n(?!\n)", " ", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def find_suburb(text: str) -> str | None:
    lower = text.lower()
    for suburb in DETECTION_SUBURBS:
        if suburb.lower() in lower:
            return suburb
    return None


def score_theme(text: str, theme_keywords: dict[str, list[str]]) -> str | None:
    lower = text.lower()
    best_theme, best_score = None, 0
    for theme, keywords in theme_keywords.items():
        score = sum(1 for kw in keywords if kw in lower)
        if score > best_score:
            best_score, best_theme = score, theme
    return best_theme if best_score else None


def word_count(text: str) -> int:
    return len(text.split())


def extract_blocks(cleaned_text: str) -> list[str]:
    return [b.strip() for b in cleaned_text.split("\n\n") if b.strip()]


def extract_quotes(cleaned_text: str) -> list[str]:
    quotes = []
    for match in QUOTE_PATTERN.finditer(cleaned_text):
        quote = re.sub(r"\s+", " ", match.group(1)).strip()
        if word_count(quote) >= 8:
            quotes.append(quote)
    return quotes


def should_keep_block(text: str, page_number: int, config: PDFConfig) -> bool:
    if word_count(text) < config.min_words:
        return False
    if page_number not in config.findings_pages:
        return False
    if "Contents" in text:
        return False
    if text in config.skip_blocks:
        return False
    if text.startswith("Strategic direction What the community told us"):
        return False
    # Filter appendix table header blocks (e.g. "71 6.4 Appendix D Question 6...")
    if "Select verbatim" in text:
        return False
    if re.match(r"^\d+\s+\d+\.\d+\s+Appendix", text):
        return False
    return True


def chunk_blocks(records: list[dict]) -> list[dict]:
    chunked: list[dict] = []
    buffer: dict | None = None
    for record in records:
        if buffer is None:
            buffer = record.copy()
            continue
        same_group = (
            buffer["page_number"] == record["page_number"]
            and buffer["theme"] == record["theme"]
            and buffer["suburb"] == record["suburb"]
        )
        if same_group and word_count(buffer["text"]) + word_count(record["text"]) <= 380:
            buffer["text"] = f'{buffer["text"]} {record["text"]}'
            continue
        chunked.append(buffer)
        buffer = record.copy()
    if buffer is not None:
        chunked.append(buffer)
    return chunked


# ---------------------------------------------------------------------------
# Core parser
# ---------------------------------------------------------------------------

def parse_pdf_file(pdf_path: Path, config: PDFConfig) -> list[dict]:
    reader = PdfReader(str(pdf_path))
    findings: list[dict] = []
    quotes: list[dict] = []

    for page_number, page in enumerate(reader.pages, start=1):
        if page_number not in config.findings_pages:
            continue

        cleaned_text = clean_page_text(page.extract_text() or "", config.header_patterns)
        if not cleaned_text:
            continue

        blocks = extract_blocks(cleaned_text)
        current_theme: str | None = None

        for block in blocks:
            block_text = block

            for heading, theme in config.section_theme_map.items():
                compact_heading = heading.lower()
                compact_block = block_text.lower()
                heading_index = compact_block.find(compact_heading)

                if block_text == heading:
                    current_theme = theme
                    block_text = ""
                    break
                if block_text.startswith(f"{heading} "):
                    current_theme = theme
                    block_text = block_text[len(heading):].strip()
                    break
                if 0 <= heading_index <= 40:
                    current_theme = theme
                    block_text = block_text[heading_index + len(heading):].strip(" :-?!")
                    break

            if not block_text:
                continue

            theme = (
                current_theme
                or score_theme(block_text, config.theme_keywords)
                or "Community Themes"
            )
            suburb = find_suburb(block_text) or config.default_suburb

            if should_keep_block(block_text, page_number, config):
                findings.append({
                    "text": block_text,
                    "theme": theme,
                    "suburb": suburb,
                    "source": config.source,
                    "page_number": page_number,
                })

        page_suburb = find_suburb(cleaned_text) or config.default_suburb
        for quote in extract_quotes(cleaned_text):
            quote_theme = (
                score_theme(quote, config.theme_keywords)
                or current_theme
                or "Community Themes"
            )
            quotes.append({
                "text": quote,
                "theme": quote_theme,
                "suburb": page_suburb,
                "source": config.source,
                "page_number": page_number,
            })

    chunked = chunk_blocks(findings)
    combined = chunked + quotes
    combined.sort(key=lambda r: (r["page_number"], r["theme"], r["text"]))
    return combined


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def write_outputs(records_by_file: dict[str, list[dict]]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    combined: list[dict] = []

    for pdf_name, records in records_by_file.items():
        per_file = OUTPUT_DIR / f"{slugify(Path(pdf_name).stem)}.json"
        per_file.write_text(json.dumps(records, indent=2, ensure_ascii=False))
        combined.extend(records)

    combined.sort(key=lambda r: (r["source"], r["page_number"], r["theme"], r["text"]))
    COMBINED_OUTPUT_PATH.write_text(json.dumps(combined, indent=2, ensure_ascii=False))


def main() -> None:
    records_by_file: dict[str, list[dict]] = {}

    for pdf_name, config in PDF_CONFIGS.items():
        pdf_path = REPORTS_DIR / pdf_name
        if not pdf_path.exists():
            print(f"WARNING: {pdf_name} not found, skipping.")
            continue
        records = parse_pdf_file(pdf_path, config)
        records_by_file[pdf_name] = records
        print(f"{pdf_name}: {len(records)} records")

    write_outputs(records_by_file)
    total = sum(len(r) for r in records_by_file.values())
    print(f"Combined: {total} records → {COMBINED_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
