import json
import re
from pathlib import Path

from pypdf import PdfReader


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PDF_CANDIDATES = [
    PROJECT_ROOT / "data/raw/community_reports/Community_Insights_Report_2024.pdf",
    PROJECT_ROOT / "data/raw/community_reports/Community_Insights_Report_2024.pdf.pdf",
]
PDF_PATH = next((path for path in PDF_CANDIDATES if path.exists()), PDF_CANDIDATES[0])
OUTPUT_PATH = PROJECT_ROOT / "data/processed/community_report.json"
SOURCE_NAME = "Community Insights Report 2024"
MVP_SUBURBS = ["Newtown", "Glebe", "Redfern", "Surry Hills", "Haymarket"]
QUOTE_PATTERN = re.compile(r'[“"]([^”"]{30,500})[”"]')


SECTION_THEME_MAP = {
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
}

THEME_KEYWORDS = {
    "Transport": [
        "transport",
        "walking",
        "cycling",
        "bike",
        "footpath",
        "pedestrian",
        "metro",
        "light rail",
        "bus",
        "station",
    ],
    "Safety": [
        "safe",
        "safety",
        "violence",
        "abuse",
        "neglect",
        "exploitation",
        "crime",
    ],
    "Housing": [
        "housing",
        "affordable housing",
        "rent",
        "cost of living",
        "displacement",
        "homes",
        "density",
    ],
    "Environment": [
        "climate",
        "green",
        "tree",
        "trees",
        "waste",
        "pollution",
        "waterways",
        "renewable",
        "recycling",
        "emissions",
        "heatwaves",
        "flooding",
    ],
    "Culture": [
        "culture",
        "creative",
        "arts",
        "artists",
        "nightlife",
        "performance",
        "public art",
        "cultural",
        "chinatown",
    ],
    "Economy": [
        "economy",
        "business",
        "businesses",
        "innovation",
        "entrepreneurship",
        "tech central",
        "investment",
        "jobs",
    ],
    "Public Spaces": [
        "public space",
        "parks",
        "gardens",
        "shade",
        "seating",
        "library",
        "community centre",
        "plaza",
        "greening",
    ],
    "Inclusion": [
        "inclusive",
        "inclusion",
        "equity",
        "equitable",
        "diverse",
        "disability",
        "multicultural",
        "racism",
        "first nations",
    ],
    "Communities": [
        "community",
        "communities",
        "resilience",
        "resilient",
        "social connection",
        "food security",
        "emergency",
        "belonging",
    ],
    "Governance": [
        "governance",
        "decision-making",
        "council",
        "transparency",
        "engagement",
        "feedback",
        "trust",
    ],
    "Design": [
        "urban design",
        "design",
        "development",
        "building",
        "infrastructure",
        "ventilation",
        "drainage",
        "sustainable development",
    ],
}

FINDINGS_PAGE_RANGE = range(5, 24)


SKIP_BLOCKS = {
    "Overview",
    "Why we’re doing this",
    "How we engaged the community",
    "Our reporting approach",
    "Community insights",
    "Emerging trends",
    "Strategic directions",
    "Advisory panels",
}


def clean_page_text(text: str) -> str:
    text = text.replace("\u00ad", "")
    text = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", text)
    text = re.sub(r"Community insights report 2024\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^Report\s*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"^December 2024\s*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\d+\s*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"(?<!\n)\n(?!\n)", " ", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def find_suburb(text: str) -> str | None:
    lower_text = text.lower()
    for suburb in MVP_SUBURBS:
        if suburb.lower() in lower_text:
            return suburb
    return None


def score_theme(text: str) -> str | None:
    lower_text = text.lower()
    best_theme = None
    best_score = 0
    for theme, keywords in THEME_KEYWORDS.items():
        score = sum(1 for keyword in keywords if keyword in lower_text)
        if score > best_score:
            best_score = score
            best_theme = theme
    return best_theme if best_score else None


def detect_theme(text: str, current_theme: str | None) -> str:
    return score_theme(text) or current_theme or "Community Themes"


def word_count(text: str) -> int:
    return len(text.split())


def should_keep_block(text: str, page_number: int, theme: str, suburb: str | None) -> bool:
    words = word_count(text)
    if words < 35:
        return False
    if page_number not in FINDINGS_PAGE_RANGE:
        return False
    if "Contents" in text:
        return False
    if text in SKIP_BLOCKS:
        return False
    if text.startswith("Strategic direction What the community told us"):
        return False
    if suburb:
        return True
    return theme in {
        "Community Themes",
        "Transport",
        "Safety",
        "Housing",
        "Environment",
        "Culture",
        "Economy",
        "Public Spaces",
        "Inclusion",
        "Communities",
        "Governance",
        "Design",
    }


def extract_blocks(cleaned_text: str) -> list[str]:
    return [block.strip() for block in cleaned_text.split("\n\n") if block.strip()]


def extract_quotes(cleaned_text: str) -> list[str]:
    quotes = []
    for match in QUOTE_PATTERN.finditer(cleaned_text):
        quote = re.sub(r"\s+", " ", match.group(1)).strip()
        if word_count(quote) >= 8:
            quotes.append(quote)
    return quotes


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
        combined_words = word_count(buffer["text"]) + word_count(record["text"])

        if same_group and combined_words <= 380:
            buffer["text"] = f'{buffer["text"]} {record["text"]}'
            continue

        chunked.append(buffer)
        buffer = record.copy()

    if buffer is not None:
        chunked.append(buffer)

    return chunked


def parse_report() -> list[dict]:
    reader = PdfReader(str(PDF_PATH))
    findings: list[dict] = []
    quotes: list[dict] = []

    for page_number, page in enumerate(reader.pages, start=1):
        raw_text = page.extract_text() or ""
        cleaned_text = clean_page_text(raw_text)
        blocks = extract_blocks(cleaned_text)
        current_theme: str | None = None

        for block in blocks:
            block_text = block
            for heading, theme in SECTION_THEME_MAP.items():
                compact_heading = heading.lower()
                compact_block = block_text.lower()
                heading_index = compact_block.find(compact_heading)

                if block_text == heading:
                    current_theme = theme
                    block_text = ""
                    break
                if block_text.startswith(f"{heading} "):
                    current_theme = theme
                    block_text = block_text[len(heading) :].strip()
                    break
                if 0 <= heading_index <= 40:
                    current_theme = theme
                    block_text = block_text[heading_index + len(heading) :].strip(" :-")
                    break

            if not block_text:
                continue

            theme = current_theme or detect_theme(block_text, current_theme)
            suburb = find_suburb(block_text)

            if should_keep_block(block_text, page_number, theme, suburb):
                findings.append(
                    {
                        "text": block_text,
                        "theme": theme,
                        "suburb": suburb,
                        "source": SOURCE_NAME,
                        "page_number": page_number,
                    }
                )

        if page_number not in FINDINGS_PAGE_RANGE:
            continue

        page_suburb = find_suburb(cleaned_text)
        for quote in extract_quotes(cleaned_text):
            quote_theme = score_theme(quote) or current_theme or "Community Themes"
            quotes.append(
                {
                    "text": quote,
                    "theme": quote_theme,
                    "suburb": page_suburb,
                    "source": SOURCE_NAME,
                    "page_number": page_number,
                }
            )

    chunked_findings = chunk_blocks(findings)
    combined = chunked_findings + quotes
    combined.sort(key=lambda item: (item["page_number"], item["theme"], item["text"]))
    return combined


def main() -> None:
    records = parse_report()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(records, indent=2, ensure_ascii=False))
    print(f"Saved {len(records)} records to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
