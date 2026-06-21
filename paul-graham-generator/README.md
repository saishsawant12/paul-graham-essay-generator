# Paul Graham Essay Scraper

This script downloads essays from Paul Graham's archive and saves each essay as a text file in an `essays` folder.

Usage:

```bash
python paul-graham-generator/scraper.py --out essays
```

Options:

Install dependencies:

```bash
pip install -r paul-graham-generator/requirements.txt
```

Notes:
Quick start: run the generator (Flask API or Streamlit UI)

1) Create a virtual environment and install dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2) Create a `.env` from `.env.example` and add your OpenAI key (or set `OPENAI_API_KEY` in your environment).

```powershell
copy .env.example .env
# edit .env and replace the placeholder key
```

3) Run the Flask API server:

```powershell
#$env:OPENAI_API_KEY = "your_key_here"   # optional override
python app.py
```

4) Or run the Streamlit UI:

```powershell

streamlit run streamlit_app.py
```

Security note: If you exposed an API key publicly, revoke it from your OpenAI dashboard immediately and create a new one. The repository's `.gitignore` prevents `.env` from being committed.
