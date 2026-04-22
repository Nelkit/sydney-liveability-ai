import json
import re
from pathlib import Path

from pypdf import PdfReader


PDF_PATH = Path("data/raw/community_reports/Community_Insights_Report_2024.pdf")
SUBURBS_PATH = Path("data/raw/community_reports/suburbs.json")
OUTPUT_PATH = Path("data/processed/community_report_quick_findings.json")
SOURCE_NAME = "Community Insights Report 2024"


def load_target_suburbs() -> list[str]:
    data = json.loads(SUBURBS_PATH.read_text())
    return data["suburbs"]


def clean_text(text: str) -> str:
    text = text.replace("\u00ad", "")
    text = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def build_suburb_pattern(suburb: str) -> re.Pattern[str]:
    if " " in suburb:
        escaped = re.escape(suburb).replace(r"\ ", r"\s+")
        return re.compile(rf"\b{escaped}\b", flags=re.IGNORECASE)
    return re.compile(rf"\b{re.escape(suburb)}\b", flags=re.IGNORECASE)


def extract_page_texts() -> list[dict]:
    reader = PdfReader(str(PDF_PATH))
    pages = []
    for page_number, page in enumerate(reader.pages, start=1):
        text = clean_text(page.extract_text() or "")
        pages.append({"page_number": page_number, "text": text})
    return pages


def count_suburb_mentions(pages: list[dict]) -> list[dict]:
    target_suburbs = load_target_suburbs()
    counts = []
    for suburb in target_suburbs:
        pattern = build_suburb_pattern(suburb)
        total_mentions = 0
        pages_with_mentions = []

        for page in pages:
            matches = pattern.findall(page["text"])
            if not matches:
                continue
            total_mentions += len(matches)
            pages_with_mentions.append(
                {
                    "page_number": page["page_number"],
                    "mentions_on_page": len(matches),
                }
            )

        counts.append(
            {
                "suburb": suburb,
                "total_mentions": total_mentions,
                "pages_with_mentions": pages_with_mentions,
            }
        )
    counts.sort(key=lambda item: (-item["total_mentions"], item["suburb"]))
    return counts


def build_output() -> dict:
    pages = extract_page_texts()
    suburb_counts = count_suburb_mentions(pages)
    total_mentions = sum(item["total_mentions"] for item in suburb_counts)
    suburbs_mentioned = [item["suburb"] for item in suburb_counts if item["total_mentions"] > 0]
    target_suburbs = [item["suburb"] for item in suburb_counts]

    return {
        "source": SOURCE_NAME,
        "file": str(PDF_PATH),
        "suburbs_file": str(SUBURBS_PATH),
        "total_pages": len(pages),
        "target_suburbs_count": len(target_suburbs),
        "suburb_mentions": suburb_counts,
        "summary": {
            "total_target_suburb_mentions": total_mentions,
            "suburbs_mentioned_at_least_once": suburbs_mentioned,
            "suburbs_not_mentioned": [
                item["suburb"] for item in suburb_counts if item["total_mentions"] == 0
            ],
        },
    }


def main() -> None:
    output = build_output()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(output, indent=2, ensure_ascii=False))
    print(f"Saved quick findings to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
