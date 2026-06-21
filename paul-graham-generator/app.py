import os
import logging
from typing import List

from flask import Flask, request, jsonify
from flask import render_template

try:
    from openai import OpenAI
except Exception:
    OpenAI = None
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from embeddings import retrieve_context


def setup_logging():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")


app = Flask(__name__)
setup_logging()


def build_prompt(topic: str, contexts: List[dict]) -> str:
    rules = (
        "Rules:\n"
        "1) Start with a surprising question.\n"
        "2) Use personal reasoning.\n"
        "3) Include examples.\n"
        "4) Build ideas progressively.\n"
        "5) End with an unexpected insight.\n"
        "6) Do not copy any essay text; be original.\n\n"
    )

    insp = "\n\n".join([f"- ({i+1}) {c.get('paragraph','')[:800]}" for i, c in enumerate(contexts)]) if contexts else ""

    prompt = (
        f"You are an essay writer inspired by Paul Graham's style. Write an original essay on the topic: '{topic}'.\n\n"
        f"{rules}"
        "Use the following retrieved Paul Graham paragraphs as inspiration (do not copy):\n"
        f"{insp}\n\n"
        "Produce a single essay that follows the rules above. Keep it ~600-1200 words.\n"
    )

    return prompt


@app.route("/generate", methods=["POST"])
def generate():
    data = request.get_json() or {}
    topic = data.get("topic")
    if not topic:
        return jsonify({"error": "Missing 'topic' in JSON body"}), 400

    # retrieve contexts (will return [] if index/meta missing)
    try:
        contexts = retrieve_context(topic)
    except Exception as e:
        logging.exception("Error retrieving context: %s", e)
        contexts = []

    prompt = build_prompt(topic, contexts)

    if OpenAI is None:
        return jsonify({"error": "OpenAI SDK not installed", "prompt": prompt}), 503

    provided_key = os.getenv("OPENAI_API_KEY")
    if not provided_key:
        return jsonify({"error": "OPENAI_API_KEY not set", "prompt": prompt}), 503

    model = os.getenv("MODEL", "gpt-4o-mini")
    try:
        client = OpenAI(api_key=provided_key)
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1200,
            temperature=0.8,
        )
        # robust extraction
        essay = None
        try:
            essay = getattr(resp.choices[0].message, "content", None)
        except Exception:
            pass
        if not essay:
            try:
                essay = resp["choices"][0]["message"]["content"]
            except Exception:
                essay = str(resp)
        if isinstance(essay, list):
            # join list parts
            essay = "\n".join([p.get("text") if isinstance(p, dict) else str(p) for p in essay])
        essay = (essay or "").strip()
    except Exception as e:
        logging.exception("OpenAI request failed: %s", e)
        return jsonify({"error": str(e)}), 500

    return jsonify({"topic": topic, "essay": essay, "contexts": contexts})


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)


@app.route("/", methods=["GET"])
def index():
    return render_template('index.html')
