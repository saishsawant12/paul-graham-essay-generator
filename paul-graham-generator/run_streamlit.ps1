# run_streamlit.ps1
# Helper script: installs requirements and launches the Streamlit app.
# Usage: Open PowerShell, cd to this folder, then:
#   ./run_streamlit.ps1

# (Optional) To set your API key for this session, uncomment and set below:
# $env:OPENAI_API_KEY = "sk-your-new-key"

# Ensure pip uses the same python: use `python` if available in PATH.
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# Launch Streamlit (will block). Use Ctrl+C to stop.
python -m streamlit run streamlit_app.py
