import argparse
import logging
import os
import re
import time
from typing import List
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

DEFAULT_ARCHIVE = "https://www.paulgraham.com/articles.html?utm_source=chatgpt.com"
USER_AGENT = "paul-graham-scraper/1.0 (+https://github.com/)"


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s: %(message)s",
    )


def sanitize_filename(s: str) -> str:
    s = s.strip()
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"[^A-Za-z0-9_.-]", "", s)
    return s[:200]


def get_archive_links(session: requests.Session, archive_url: str) -> List[str]:
    logging.info("Fetching archive page: %s", archive_url)
    try:
        resp = session.get(archive_url, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        logging.error("Failed fetching archive: %s", e)
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    links = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        # look for .html links (Paul Graham essays are .html)
        if ".html" in href:
            full = urljoin(archive_url, href)
            parsed = urlparse(full)
            if parsed.scheme in ("http", "https"):
                links.add(full)

    logging.info("Found %d candidate links", len(links))
    return sorted(links)


def extract_text_from_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    # Prefer article/body content; fallback to full text
    parts = []
    # Try common containers
    for selector in ["article", "div#content", "div.content", "body"]:
        node = soup.select_one(selector)
        if node:
            parts = list(node.stripped_strings)
            break

    if not parts:
        parts = list(soup.stripped_strings)

    return "\n\n".join(parts)


def fetch_and_save(session: requests.Session, url: str, out_dir: str) -> bool:
    logging.info("Downloading: %s", url)
    try:
        resp = session.get(url, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as e:
        logging.error("Request failed for %s: %s", url, e)
        return False

    text = extract_text_from_html(resp.text)
    # Determine filename from <title> if possible
    title = None
    try:
        soup = BeautifulSoup(resp.text, "html.parser")
        if soup.title and soup.title.string:
            title = soup.title.string
    except Exception:
        title = None

    if title:
        name = sanitize_filename(title)
    else:
        # fallback to path slug
        parsed = urlparse(url)
        name = os.path.basename(parsed.path) or parsed.netloc
        name = sanitize_filename(name)

    if not name:
        name = sanitize_filename(str(int(time.time())))

    filename = os.path.join(out_dir, f"{name}.txt")
    try:
        with open(filename, "w", encoding="utf-8") as f:
            f.write(url + "\n\n")
            f.write(text)
        logging.info("Saved: %s", filename)
        return True
    except OSError as e:
        logging.error("Failed saving %s: %s", filename, e)
        return False


def scrape(archive_url: str, out_dir: str, delay: float = 1.0, limit: int = 0):
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    os.makedirs(out_dir, exist_ok=True)

    links = get_archive_links(session, archive_url)
    if not links:
        logging.error("No links to process. Exiting.")
        return

    if limit > 0:
        links = links[:limit]

    for i, link in enumerate(links, start=1):
        logging.info("(%d/%d) Processing", i, len(links))
        try:
            success = fetch_and_save(session, link, out_dir)
            if not success:
                logging.warning("Skipping after failed fetch: %s", link)
        except Exception as e:
            logging.exception("Unexpected error processing %s: %s", link, e)

        time.sleep(delay)


def parse_args():
    p = argparse.ArgumentParser(description="Scrape Paul Graham essays into text files.")
    p.add_argument("--archive", default=DEFAULT_ARCHIVE, help="Archive page URL")
    p.add_argument("--out", default="essays", help="Output directory for essays")
    p.add_argument("--delay", type=float, default=1.0, help="Seconds to wait between requests")
    p.add_argument("--limit", type=int, default=0, help="Maximum number of essays to download (0 = all)")
    return p.parse_args()


if __name__ == "__main__":
    setup_logging()
    args = parse_args()
    logging.info("Starting scraper")
    scrape(args.archive, args.out, delay=args.delay, limit=args.limit)
