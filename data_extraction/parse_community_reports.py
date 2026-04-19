import json
import re
from pathlib import Path

from pypdf import PdfReader


REPORTS_DIR = Path("data/raw/community_reports")
OUTPUT_DIR = Path("data/processed/community_reports")
COMBINED_OUTPUT_PATH = Path("data/processed/community_reports_all.json")
QUOTE_PATTERN = re.compile(r'[“"]([^”"]{20,500})[”"]')

THEME_KEYWORDS = {
    "Transport": [
        "transport",
        "walking",
        "walk",
        "cycling",
        "bike",
        "pedestrian",
        "station",
        "access",
        "connections",
    ],
    "Safety": [
        "safe",
        "safety",
        "lighting",
        "crime",
        "security",
        "well lit",
    ],
    "Housing": [
        "housing",
        "rent",
        "affordable housing",
        "homes",
        "displacement",
        "cost of living",
    ],
    "Environment": [
        "green",
        "tree",
        "trees",
        "waste",
        "pollution",
        "climate",
        "cleaning",
        "maintenance",
    ],
    "Culture": [
        "culture",
        "cultural",
        "heritage",
        "art",
        "public art",
        "lighting",
        "chinatown",
        "thai town",
        "celebrations",
        "history",
    ],
    "Lifestyle": [
        "restaurants",
        "cafes",
        "food",
        "retail",
        "events",
        "activities",
        "nightlife",
        "bars",
        "dining",
        "vibrant",
    ],
    "Public Spaces": [
        "public spaces",
        "public space",
        "street",
        "streetscape",
        "seating",
        "public toilets",
        "park",
        "laneways",
        "outdoor dining",
    ],
    "Economy": [
        "business",
        "businesses",
        "trading",
        "retail",
        "market",
        "investment",
    ],
    "Community Themes": [
        "community",
        "respondents",
        "future",
        "improve",
        "special",
        "vision",
    ],
}

REPORT_CONFIG = {
    "Community_Insights_Report_2024.pdf": {
        "source": "Community Insights Report 2024",
        "default_suburb": None,
        "min_words": 35,
    },
    "Haymarket Summary Final English.pdf": {
        "source": "A community vision for Haymarket",
        "default_suburb": "Haymarket",
        "min_words": 12,
    },
}


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return slug or "report"


def clean_text(text: str) -> str:
    text = text.replace("\u00ad", "")
    text = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", text)
    text = re.sub(r"^\s*\d+\s*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"(?<!\n)\n(?!\n)", " ", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def word_count(text: str) -> int:
    return len(text.split())


def score_theme(text: str) -> str:
    lower_text = text.lower()
    best_theme = "Community Themes"
    best_score = 0

    for theme, keywords in THEME_KEYWORDS.items():
        score = sum(1 for keyword in keywords if keyword in lower_text)
        if score > best_score:
            best_score = score
            best_theme = theme

    return best_theme


def split_into_blocks(text: str) -> list[str]:
    blocks = [block.strip() for block in text.split("\n\n") if block.strip()]
    return [block for block in blocks if word_count(block) >= 8]


def extract_quotes(text: str) -> list[str]:
    quotes = []
    for match in QUOTE_PATTERN.finditer(text):
        quote = re.sub(r"\s+", " ", match.group(1)).strip()
        if word_count(quote) >= 5:
            quotes.append(quote)
    return quotes


def build_record(
    text: str,
    page_number: int,
    source: str,
    source_file: str,
    default_suburb: str | None,
    record_type: str,
) -> dict:
    return {
        "text": re.sub(r"\s+", " ", text).strip(),
        "theme": score_theme(text),
        "suburb": default_suburb,
        "source": source,
        "source_file": source_file,
        "page_number": page_number,
        "record_type": record_type,
    }


def parse_pdf(pdf_path: Path) -> list[dict]:
    config = REPORT_CONFIG.get(
        pdf_path.name,
        {
            "source": pdf_path.stem,
            "default_suburb": None,
            "min_words": 20,
        },
    )

    reader = PdfReader(str(pdf_path))
    records: list[dict] = []

    for page_number, page in enumerate(reader.pages, start=1):
        cleaned_text = clean_text(page.extract_text() or "")
        if not cleaned_text:
            continue

        for block in split_into_blocks(cleaned_text):
            if word_count(block) < config["min_words"]:
                continue
            records.append(
                build_record(
                    text=block,
                    page_number=page_number,
                    source=config["source"],
                    source_file=pdf_path.name,
                    default_suburb=config["default_suburb"],
                    record_type="finding",
                )
            )

        for quote in extract_quotes(cleaned_text):
            records.append(
                build_record(
                    text=quote,
                    page_number=page_number,
                    source=config["source"],
                    source_file=pdf_path.name,
                    default_suburb=config["default_suburb"],
                    record_type="quote",
                )
            )

    return records


def write_outputs(records_by_file: dict[str, list[dict]]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    combined_records: list[dict] = []
    for source_file, records in records_by_file.items():
        output_name = f"{slugify(Path(source_file).stem)}.json"
        output_path = OUTPUT_DIR / output_name
        output_path.write_text(json.dumps(records, indent=2, ensure_ascii=False) + "\n")
        combined_records.extend(records)

    combined_records.sort(key=lambda item: (item["source_file"], item["page_number"], item["record_type"], item["text"]))
    COMBINED_OUTPUT_PATH.write_text(json.dumps(combined_records, indent=2, ensure_ascii=False) + "\n")


def main() -> None:
    pdf_files = sorted(REPORTS_DIR.glob("*.pdf"))
    records_by_file = {pdf_path.name: parse_pdf(pdf_path) for pdf_path in pdf_files}
    write_outputs(records_by_file)

    for pdf_name, records in records_by_file.items():
        print(f"{pdf_name}: saved {len(records)} records")
    print(f"Combined output saved to {COMBINED_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
