import io
import os
import textwrap
import logging

import streamlit as st
try:
    from openai import OpenAI
except Exception:
    OpenAI = None
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

import embeddings
from embeddings import search_with_index
from typing import List
import hashlib
import random


def setup_logging():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
    return logging.getLogger("paulgraham.rag")


def build_prompt(topic: str, contexts):
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


def text_to_pdf_bytes(title: str, text: str) -> bytes:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    margin = 72
    y = height - margin

    # Title
    c.setFont("Helvetica-Bold", 16)
    wrapped_title = textwrap.wrap(title, width=80)
    for line in wrapped_title:
        c.drawString(margin, y, line)
        y -= 20

    y -= 10
    c.setFont("Helvetica", 11)
    lines = []
    for para in text.split("\n\n"):
        wrapped = textwrap.wrap(para, width=95)
        if not wrapped:
            lines.append("")
        else:
            lines.extend(wrapped)
        lines.append("")

    for line in lines:
        if y < margin:
            c.showPage()
            y = height - margin
            c.setFont("Helvetica", 11)
        c.drawString(margin, y, line)
        y -= 14

    c.save()
    buffer.seek(0)
    return buffer.read()


def sanitize_filename(s: str) -> str:
    keep = "abcdefghijklmnopqrstuvwxyz0123456789-_"
    s = s.lower().replace(" ", "-")
    return "".join([c for c in s if c in keep])[:120]


def generate_title(topic: str, essay: str) -> str:
    # Deterministic short title based on topic and essay content
    seed = int(hashlib.sha1(topic.encode("utf-8")).hexdigest(), 16) % 10000
    candidates = [
        f"On {topic}",
        f"Thinking About {topic}",
        f"Notes on {topic}",
        f"Rethinking {topic}",
        f"{topic}: An Essay"
    ]
    title = candidates[seed % len(candidates)]
    # add short hint from first sentence
    first_sent = essay.split(".\n\n")[0].split(".")[0][:60]
    if first_sent:
        title = f"{title} — {first_sent.strip()}"
    return title


def local_generate_essay(topic: str, contexts: list) -> str:
    # Build an original essay inspired by the structural rules. Use a topic-seeded RNG
    seed = sum(ord(c) for c in topic) % (2 ** 32)
    rng = random.Random(seed)

    first_question_templates = [
        "What if the obvious thing about {topic} is the wrong starting point?",
        "Why do we assume {topic} always follows the same rules?",
        "Has anyone asked whether {topic} begins in the place we think it does?",
    ]

    personal_reasoning_templates = [
        "I used to think {topic} meant following a fixed script: do X, then Y. Over time I've learned that this script is often a trap.",
        "My instinct about {topic} used to be simple: do the expected steps. Experience taught me that's brittle.",
        "Early on I had a naive theory about {topic}. What changed was noticing small mismatches between our models and real behavior.",
    ]

    example_templates = [
        "For example, people often treat {topic} as a checklist item; one team instead dug into a tiny user workflow and turned that insight into a durable advantage.",
        "Another story: an individual built a tiny tool around {topic} that solved an annoying edge-case — that small fix became the product's core.",
        "A different angle: rather than optimize the visible metric for {topic}, someone measured a subtle behavior and changed direction, producing outsized results.",
        "Consider a counterintuitive move: focusing on a marginal part of {topic} often uncovers leverage no one else is measuring.",
    ]

    build_ideas_templates = [
        "To make sense of this, think in layers: find the mismatch between what users do and what products assume, exploit a small repeatable advantage, then let it compound.",
        "A useful heuristic is: find a tiny advantage, make it repeatable, and keep iterating. That ordering explains many surprising successes.",
    ]

    unexpected_insight_templates = [
        "The surprising part is that the most reliable way to be original is to be boringly observant. The biggest leaps often follow from fixing small frictions.",
        "Often the novel move isn't grand — it's simply paying attention to what everyone else ignores, then iterating until it scales.",
    ]

    def choose_first_question():
        return rng.choice(first_question_templates).format(topic=topic)

    def choose_personal_reasoning():
        return rng.choice(personal_reasoning_templates).format(topic=topic)

    def example_paragraph(i, contexts):
        # Prefer a randomly chosen real retrieved context when available
        if contexts:
            # sample up to 3 different contexts deterministically by seed
            idx = rng.randrange(0, max(1, len(contexts)))
            ex = contexts[idx].get("paragraph", "")
            snippet = ex[:400].rstrip()
            return f"For example, consider this passage that inspired me: \"{snippet}\". It shapes how I think about {topic}."

        # Otherwise use a sampled template
        return rng.choice(example_templates).format(topic=topic)

    def choose_build_ideas():
        return rng.choice(build_ideas_templates)

    def choose_unexpected_insight():
        return rng.choice(unexpected_insight_templates)

    # Compose the essay sections with some variability in order and count
    parts = []
    parts.append(choose_first_question())
    parts.append("")
    parts.append(choose_personal_reasoning())
    parts.append("")
    # include 2-4 examples
    for i in range(rng.randint(2, 4)):
        parts.append(example_paragraph(i, contexts))
        parts.append("")
    parts.append(choose_build_ideas())
    parts.append("")
    parts.append(choose_unexpected_insight())
    # Remove consecutive duplicate paragraphs to avoid repetition and ensure topic appears
    deduped = []
    prev = None
    for p in parts:
        if p is None:
            continue
        text = p.strip()
        if not text:
            continue
        if text == prev:
            continue
        # Ensure topic appears in paragraph; if not, append a short tie-in
        if topic.lower() not in text.lower():
            text = text + "\n\n" + f"(This relates to {topic} because it highlights a common pattern.)"
        deduped.append(text)
        prev = text

    essay = "\n\n".join(deduped)
    return essay


def generate_essay(topic: str):
    logger = setup_logging()

    # Retrieve relevant contexts using cached model+index
    try:
        with st.spinner("Retrieving relevant Paul Graham paragraphs..."):
            contexts = search_with_index(topic, index_path=os.path.join(os.getcwd(), "pg_index.faiss"), meta_path=os.path.join(os.getcwd(), "embeddings_meta.json"))
    except Exception as e:
        logger.exception("Retrieval failed")
        contexts = []

    # dedupe contexts by paragraph text
    seen = set()
    dedup_contexts = []
    for c in contexts:
        p = (c.get("paragraph") or "").strip()
        if not p or p in seen:
            continue
        seen.add(p)
        dedup_contexts.append(c)
    contexts = dedup_contexts

    # Try API-based generation if OpenAI client and env key are present
    provided_key = os.getenv("OPENAI_API_KEY")
    if OpenAI is not None and provided_key:
        model = os.getenv("MODEL", "gpt-4o-mini")
        prompt = build_prompt(topic, contexts)
        try:
            client = OpenAI(api_key=provided_key)
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1200,
                temperature=0.8,
            )
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
                essay = "\n".join([p.get("text") if isinstance(p, dict) else str(p) for p in essay])
            essay = (essay or "").strip()
            return essay, contexts
        except Exception as e:
            logger.exception("API generation failed; falling back to local generator")
            st.warning(f"API generation failed; falling back to local generator: {e}")

    # Fallback: local generator that follows the user's structural rules
    essay = local_generate_essay(topic, contexts)
    return essay, contexts


def main():
    st.set_page_config(page_title="Paul Graham RAG Essay Generator", layout="wide")
    # Simple dark theme CSS to make UI more professional
    dark_css = """
    <style>
    .stApp { background-color: #0e1117; color: #e6edf3; }
    .css-1d391kg { background-color: #0e1117; }
    .stButton>button { background-color: #1f6feb; color: white; }
    .stDownloadButton>button { background-color: #1f6feb; color: white; }
    </style>
    """
    st.markdown(dark_css, unsafe_allow_html=True)

    st.title("Paul Graham–Inspired RAG Essay Generator")
    cols = st.columns([3, 1])
    with cols[0]:
        topic = st.text_input("Topic (one sentence)", value="surprises of startups")
    with cols[1]:
        st.write("\n")
        st.write("\n")
        st.write("Controls")
        st.write("Model: local fallback + retrieved contexts")

    generate = st.button("Generate")
    if generate:
        with st.spinner("Generating essay (retrieval + generation)..."):
            try:
                essay, contexts = generate_essay(topic)
            except Exception as e:
                logger = setup_logging()
                logger.exception("Generation failed")
                st.error(f"Generation failed: {e}")
                return

        if not essay:
            st.warning("No essay produced. Check logs or ensure an index exists.")
            return

        title = generate_title(topic, essay)

        st.subheader(title)
        st.markdown("---")

        # Show sources in a right-hand column
        left, right = st.columns([3, 1])
        with right:
            st.subheader("Retrieved Sources")
            if contexts:
                for c in contexts:
                    with st.expander(c.get("title") or c.get("filename") or "Source"):
                        st.write(c.get("paragraph"))
                        if c.get("url"):
                            st.markdown(f"[Source link]({c.get('url')})")
                        st.write(f"Score: {c.get('score'):.3f}")
            else:
                st.info("No retrieved contexts available — generation used local heuristics.")

        with left:
            st.subheader("Generated Essay")
            st.write(essay)

            pdf_bytes = text_to_pdf_bytes(title, essay)
            filename = sanitize_filename(title) or "essay"
            st.download_button("Download as PDF", data=pdf_bytes, file_name=f"{filename}.pdf", mime="application/pdf")


if __name__ == "__main__":
    main()
