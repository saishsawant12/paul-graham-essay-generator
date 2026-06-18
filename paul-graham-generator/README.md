# Paul Graham Essay Scraper

This script downloads essays from Paul Graham's archive and saves each essay as a text file in an `essays` folder.

Usage:

```bash
python paul-graham-generator/scraper.py --out essays
```

Options:
- `--archive`: Archive URL (default: https://www.paulgraham.com/articles.html?utm_source=chatgpt.com)
- `--out`: Output directory (default: essays)
- `--delay`: Seconds between requests (default: 1.0)
- `--limit`: Max essays to download (0 = all)

Install dependencies:

```bash
pip install -r paul-graham-generator/requirements.txt
```

Notes:
- The scraper uses `requests` and `BeautifulSoup` and handles HTTP errors gracefully.
- If a page cannot be downloaded or saved it will be skipped and logged.
