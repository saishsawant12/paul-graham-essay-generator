import os
import sys
import hashlib
import json
from datetime import datetime

# Ensure project package dir is on sys.path so imports succeed when running tests
HERE = os.path.dirname(__file__)
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, ROOT)

from embeddings import search_with_index
import streamlit_app as app

OUT_PATH = "test_results.txt"
TOPICS = [
    "Why AI Will Change Education",
    "Why Startups Fail",
    "Future of Programming",
]

REPORT = []
results = {}

os.makedirs(os.path.dirname(OUT_PATH) or ".", exist_ok=True)

for topic in TOPICS:
    entry = {"topic": topic}

    # Retrieve contexts (use absolute paths so test is independent of working dir)
    index_path = os.path.join(ROOT, "pg_index.faiss")
    meta_path = os.path.join(ROOT, "embeddings_meta.json")
    contexts = search_with_index(topic, index_path=index_path, meta_path=meta_path, top_k=5)
    entry["retrieved"] = contexts

    # Build prompt
    prompt = app.build_prompt(topic, contexts)
    entry["prompt"] = prompt

    # Generate essay using local generator to avoid API dependencies
    essay = app.local_generate_essay(topic, contexts)
    entry["essay"] = essay

    # Compact representations for comparisons
    ctx_text = "\n".join([c.get("paragraph","") for c in contexts])
    entry["ctx_hash"] = hashlib.sha1(ctx_text.encode("utf-8")).hexdigest()
    entry["prompt_hash"] = hashlib.sha1(prompt.encode("utf-8")).hexdigest()
    entry["essay_hash"] = hashlib.sha1(essay.encode("utf-8")).hexdigest()

    results[topic] = entry

# Tests
pass_report = True
fail_reasons = []

# 8. Verify: Retrieved contexts are not identical.
ctx_hashes = [results[t]["ctx_hash"] for t in TOPICS]
if len(set(ctx_hashes)) != len(ctx_hashes):
    pass_report = False
    fail_reasons.append("Retrieved contexts contain identical hashes for different topics.")

# 9. Prompts are not identical.
prompt_hashes = [results[t]["prompt_hash"] for t in TOPICS]
if len(set(prompt_hashes)) != len(prompt_hashes):
    pass_report = False
    fail_reasons.append("Generated prompts are identical for multiple topics.")

# 10. Essays are not identical.
essay_hashes = [results[t]["essay_hash"] for t in TOPICS]
if len(set(essay_hashes)) != len(essay_hashes):
    pass_report = False
    fail_reasons.append("Generated essays are identical for multiple topics.")

# Build human-readable report
report_lines = []
report_lines.append(f"Integration test run: {datetime.utcnow().isoformat()}Z")
report_lines.append("")
for t in TOPICS:
    e = results[t]
    report_lines.append("---")
    report_lines.append(f"Topic: {t}")
    report_lines.append("")
    report_lines.append("Retrieved Contexts (top 5):")
    if not e["retrieved"]:
        report_lines.append("  [NO CONTEXTS RETURNED]")
    for i, c in enumerate(e["retrieved"], start=1):
        para = c.get("paragraph","").replace("\n"," ")
        report_lines.append(f"  {i}. score={c.get('score',0):.4f} title={c.get('title')!r}")
        report_lines.append(f"     {para[:300]}")
    report_lines.append("")
    report_lines.append("Generated Prompt:")
    report_lines.append(e["prompt"][:1000])
    report_lines.append("")
    report_lines.append("Generated Essay (first 1000 chars):")
    report_lines.append(e["essay"][:1000])
    report_lines.append("")
    report_lines.append(f"ctx_hash: {e['ctx_hash']}")
    report_lines.append(f"prompt_hash: {e['prompt_hash']}")
    report_lines.append(f"essay_hash: {e['essay_hash']}")
    report_lines.append("")

report_lines.append("=== Summary ===")
report_lines.append(f"Retrieved contexts distinct: {len(set(ctx_hashes)) == len(ctx_hashes)}")
report_lines.append(f"Prompts distinct: {len(set(prompt_hashes)) == len(prompt_hashes)}")
report_lines.append(f"Essays distinct: {len(set(essay_hashes)) == len(essay_hashes)}")
report_lines.append("")
if pass_report:
    report_lines.append("RESULT: PASS — topics produced different retrievals, prompts, and essays.")
else:
    report_lines.append("RESULT: FAIL — see reasons and suggestions below.")
    report_lines.append("")
    report_lines.append("Failure reasons:")
    for r in fail_reasons:
        report_lines.append(f"- {r}")
    report_lines.append("")
    # Suggestions
    if any("Retrieved contexts" in r for r in fail_reasons):
        report_lines.append("Suggested fixes for identical retrievals:")
        report_lines.append("- Rebuild the FAISS index from more essays (increase corpus or include paragraph context).")
        report_lines.append("- Increase `top_k` or use a different embedding model for better semantic separation.")
    if any("prompts are identical" in r.lower() or "Generated prompts" in r for r in fail_reasons):
        report_lines.append("Suggested fixes for identical prompts:")
        report_lines.append("- Ensure `build_prompt` includes the topic string and retrieved context excerpts (it does), but consider adding topic-specific instructions or random seed-based variations.")
    if any("essays are identical" in r.lower() for r in fail_reasons):
        report_lines.append("Suggested fixes for identical essays:")
        report_lines.append("- Expand local generator templates and add controlled randomness seeded by topic.")
        report_lines.append("- If using API generation, ensure prompts include retrieved contexts and topic-specific anchors.")

# Save to OUT_PATH
with open(OUT_PATH, "w", encoding="utf-8") as f:
    f.write("\n".join(report_lines))

# Print summary
print("\n".join(report_lines))
print(f"\nDetailed test report saved to {OUT_PATH}")

# Exit non-zero on failure so CI fails the job when topics are not distinct
if not pass_report:
    print("\nOne or more checks failed. See test_results.txt for details.")
    import sys
    sys.exit(1)

print("\nAll checks passed.")
