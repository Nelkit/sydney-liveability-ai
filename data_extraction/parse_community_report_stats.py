import json
import re
from pathlib import Path

from pypdf import PdfReader


REPORTS_DIR = Path("data/raw/community_reports")
OUTPUT_DIR = Path("data/processed/community_reports/stats")
COMBINED_OUTPUT_PATH = Path("data/processed/community_reports_stats_all.json")
PERCENT_PATTERN = re.compile(r"(\d{1,3})%")

THEME_KEYWORDS = {
    "Transport": ["transport", "pedestrian", "walking", "access", "connections"],
    "Safety": ["safe", "safety", "lighting", "welcoming"],
    "Housing": ["housing", "buildings", "affordable"],
    "Culture": ["culture", "cultural", "heritage", "art", "celebrations", "lighting"],
    "Lifestyle": ["restaurants", "cafes", "nightlife", "food", "events", "dining"],
    "Public Spaces": ["public", "street", "seating", "toilets", "streetscape"],
    "Community Themes": ["respondents", "important", "would like", "future"],
}

REPORT_CONFIG = {
    "Community_Insights_Report_2024.pdf": {
        "source": "Community Insights Report 2024",
        "default_suburb": None,
    },
    "Haymarket Summary Final English.pdf": {
        "source": "A community vision for Haymarket",
        "default_suburb": "Haymarket",
    },
    "Haymarket Vision engagement report.pdf": {
        "source": "Haymarket Vision engagement report",
        "default_suburb": "Haymarket",
    },
}


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def clean_line(text: str) -> str:
    text = text.replace("\u00ad", "")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


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


def extract_lines(page_text: str) -> list[str]:
    lines: list[str] = []
    for raw_line in page_text.splitlines():
        normalized = raw_line.replace("\u00ad", "")
        normalized = re.sub(r"(?<=[A-Za-z])(?=\d{1,3}%)", "\n", normalized)
        for part in normalized.splitlines():
            cleaned = clean_line(part)
            if cleaned:
                lines.append(cleaned)
    return lines


def build_stat_record(
    percentage: int,
    statistic_text: str,
    page_number: int,
    source: str,
    source_file: str,
    suburb: str | None,
) -> dict:
    return {
        "percentage": percentage,
        "statistic_text": statistic_text,
        "theme": score_theme(statistic_text),
        "suburb": suburb,
        "source": source,
        "source_file": source_file,
        "page_number": page_number,
        "record_type": "statistic",
    }


def parse_pdf_stats(pdf_path: Path) -> list[dict]:
    config = REPORT_CONFIG.get(
        pdf_path.name,
        {"source": pdf_path.stem, "default_suburb": None},
    )

    reader = PdfReader(str(pdf_path))
    records: list[dict] = []

    for page_number, page in enumerate(reader.pages, start=1):
        lines = extract_lines(page.extract_text() or "")

        for index, line in enumerate(lines):
            match = PERCENT_PATTERN.search(line)
            if not match:
                continue

            percentage = int(match.group(1))
            line_without_percentage = clean_line(PERCENT_PATTERN.sub("", line))
            context_lines = []

            if line_without_percentage:
                context_lines.append(line_without_percentage)

            next_index = index + 1
            while next_index < len(lines) and len(context_lines) < 4:
                next_line = lines[next_index]
                if PERCENT_PATTERN.search(next_line):
                    break
                if next_line.startswith(("“", '"')):
                    break
                if re.fullmatch(r"\d+", next_line):
                    next_index += 1
                    continue
                context_lines.append(next_line)
                next_index += 1

            statistic_text = clean_line(" ".join(context_lines))
            if not statistic_text:
                continue

            records.append(
                build_stat_record(
                    percentage=percentage,
                    statistic_text=statistic_text,
                    page_number=page_number,
                    source=config["source"],
                    source_file=pdf_path.name,
                    suburb=config["default_suburb"],
                )
            )

    return records


def write_outputs(records_by_file: dict[str, list[dict]]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    combined_records: list[dict] = []

    for source_file, records in records_by_file.items():
        output_name = f"{slugify(Path(source_file).stem)}_stats.json"
        output_path = OUTPUT_DIR / output_name
        output_path.write_text(json.dumps(records, indent=2, ensure_ascii=False) + "\n")
        combined_records.extend(records)

    combined_records.sort(key=lambda item: (item["source_file"], item["page_number"], -item["percentage"]))
    COMBINED_OUTPUT_PATH.write_text(json.dumps(combined_records, indent=2, ensure_ascii=False) + "\n")


def main() -> None:
    pdf_files = sorted(REPORTS_DIR.glob("*.pdf"))
    records_by_file = {pdf_path.name: parse_pdf_stats(pdf_path) for pdf_path in pdf_files}
    write_outputs(records_by_file)

    for pdf_name, records in records_by_file.items():
        print(f"{pdf_name}: saved {len(records)} statistics")
    print(f"Combined output saved to {COMBINED_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
