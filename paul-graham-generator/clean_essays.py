import argparse
import csv
import logging
import os
import re
from typing import List

from bs4 import BeautifulSoup


def setup_logging():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")


def clean_html(raw_html: str) -> str:
    # Use BeautifulSoup to remove any HTML tags/entities
    try:
        soup = BeautifulSoup(raw_html, "html.parser")
        text = soup.get_text("\n")
    except Exception:
        text = raw_html
    return text


def normalize_whitespace(s: str) -> str:
    # collapse multiple spaces and trim
    s = re.sub(r"[ \t\u00A0]+", " ", s)
    s = re.sub(r"\r\n|\r", "\n", s)
    s = re.sub(r"\n\s+", "\n", s)
    s = s.strip()
    return s


NAV_KEYWORDS = re.compile(r"\b(home|next|previous|index|search|contact|rss|archives|sitemap|back to top|top|menu)\b", re.I)


def is_navigation_paragraph(p: str) -> bool:
    p_stripped = p.strip()
    if not p_stripped:
        return True
    # drop very short lines that look like navigation
    if len(p_stripped) < 40 and NAV_KEYWORDS.search(p_stripped):
        return True
    # drop lines that are just symbols or arrows
    if re.fullmatch(r"[«»<>↦→←-]{1,6}", p_stripped):
        return True
    return False


def split_into_paragraphs(text: str) -> List[str]:
    # split on blank lines
    parts = re.split(r"\n\s*\n+", text)
    cleaned = []
    for p in parts:
        p = p.replace("\n", " ")
        p = normalize_whitespace(p)
        if is_navigation_paragraph(p):
            continue
        if not p:
            continue
        cleaned.append(p)
    return cleaned


def process_file(path: str) -> List[dict]:
    logging.info("Processing file: %s", path)
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
    except OSError as e:
        logging.error("Failed to read %s: %s", path, e)
        return []

    # If first line is a URL, extract and remove it
    lines = content.splitlines()
    url = ""
    if lines and lines[0].startswith("http"):
        url = lines[0].strip()
        body = "\n".join(lines[2:]) if len(lines) > 2 else ""
    else:
        body = content

    # Remove any remaining HTML
    body = clean_html(body)

    paragraphs = split_into_paragraphs(body)

    rows = []
    base = os.path.basename(path)
    title = os.path.splitext(base)[0]
    for idx, p in enumerate(paragraphs, start=1):
        rows.append({"filename": base, "title": title, "url": url, "paragraph_index": idx, "paragraph": p})

    return rows


def find_text_files(input_dir: str) -> List[str]:
    files = []
    if not os.path.isdir(input_dir):
        logging.error("Input directory does not exist: %s", input_dir)
        return files
    for name in os.listdir(input_dir):
        if name.lower().endswith(".txt"):
            files.append(os.path.join(input_dir, name))
    return sorted(files)


def write_csv(rows: List[dict], out_csv: str):
    if not rows:
        logging.warning("No rows to write to CSV")
        return
    fieldnames = ["filename", "title", "url", "paragraph_index", "paragraph"]
    try:
        with open(out_csv, "w", encoding="utf-8-sig", newline="") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for r in rows:
                writer.writerow(r)
        logging.info("Wrote cleaned CSV: %s", out_csv)
    except OSError as e:
        logging.error("Failed to write CSV %s: %s", out_csv, e)


def main(input_dir: str, out_csv: str):
    setup_logging()
    files = find_text_files(input_dir)
    logging.info("Found %d text files", len(files))
    all_rows = []
    for path in files:
        try:
            rows = process_file(path)
            all_rows.extend(rows)
        except Exception as e:
            logging.exception("Unexpected error processing %s: %s", path, e)

    write_csv(all_rows, out_csv)


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="Clean essay text files and save to CSV")
    p.add_argument("--in", dest="input_dir", default="essays", help="Directory with essay .txt files")
    p.add_argument("--out", dest="out_csv", default="cleaned_essays.csv", help="Output CSV file path")
    args = p.parse_args()
    main(args.input_dir, args.out_csv)
