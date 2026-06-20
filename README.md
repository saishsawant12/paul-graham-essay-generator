[![Integration Tests](https://github.com/OWNER/REPO/actions/workflows/integration-tests.yml/badge.svg)](https://github.com/OWNER/REPO/actions/workflows/integration-tests.yml)


# Paul Graham Essay Generator — RAG Demo

Project Overview
----------------
This repository implements a small production-ready Retrieval-Augmented Generation (RAG) demo inspired by Paul Graham's essays. It scrapes essays, cleans and splits them into paragraphs, builds sentence-transformer embeddings and a FAISS index, and provides a Streamlit UI and programmatic test harness to generate original, Paul Graham–inspired essays grounded in retrieved source paragraphs.

**Quick highlights:** semantic search with `faiss`, embeddings from `sentence-transformers`, Streamlit UI with dark theme, PDF export, integrated CI tests.

Architecture Diagram
--------------------
```mermaid
flowchart TD
	A[Scraper] --> B[essays/ (raw .txt)]
	B --> C[Cleaner]
	C --> D[cleaned_essays.csv]
	D --> E[Embeddings (SentenceTransformer)]
	E --> F[FAISS index + metadata]
	G[Streamlit UI] --> H[retrieve_context(query) via FAISS]
	H --> I[Generator (OpenAI or local fallback)]
	I --> J[PDF Export / Download]
```

Features
--------
- Semantic retrieval from Paul Graham essays using FAISS
- Deterministic, topic-seeded local essay generator (fallback)
- OpenAI integration (optional) with graceful fallback
- Streamlit UI: dark theme, loading spinners, source display, PDF export
- Integration tests that verify retrieval and generation distinctness
- GitHub Actions CI that runs the integration tests on push/PR

Installation
------------
Prerequisites: Python 3.10+ and pip. Clone the repo and install dependencies:

```bash
git clone https://github.com/OWNER/REPO.git
cd paul-graham-essay-generator/paul-graham-generator
python -m venv .venv
source .venv/bin/activate  # or ".venv\Scripts\Activate" on Windows
python -m pip install -r requirements.txt
```

Usage
-----
- Scrape essays (skip if you already have `essays/`):

```bash
python scraper.py --out essays --limit 100
```

- Clean scraped files into CSV:

```bash
python clean_essays.py --in essays --out cleaned_essays.csv
```

- Build embeddings and FAISS index:

```bash
python embeddings.py --csv cleaned_essays.csv --index pg_index.faiss --meta embeddings_meta.json --model all-MiniLM-L6-v2
```

- Run Streamlit UI:

```bash
python -m streamlit run streamlit_app.py
```

Running tests
-------------
The repository includes an integration test that verifies retrieval, prompts and essays differ across topics and writes a report to `test_results.txt`.

Run locally:
```bash
cd paul-graham-generator
python -m runpy run_path tests/integration_test.py
```

Screenshots
-----------
_(Placeholders — run Streamlit locally to capture screenshots.)_

Team Members
------------
- Primary author: Your Name
- Contributors: Your Team

Notes
-----
- Replace `OWNER/REPO` in the badge and clone URL with your GitHub organization and repository name so the Actions badge renders.
- The CI builds the FAISS index if it is missing; consider caching or uploading the prebuilt index to speed CI.

License & Credits
-----------------
This project is for demonstration and research; respect Paul Graham's copyright when reusing essay text. Code licensed as MIT (adjust as needed).
