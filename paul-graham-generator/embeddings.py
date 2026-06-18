import csv
import json
import logging
import os
from typing import List

import numpy as np
import functools

from sentence_transformers import SentenceTransformer
import faiss


def setup_logging():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")


def load_paragraphs(csv_path: str):
    rows = []
    if not os.path.isfile(csv_path):
        logging.error("CSV not found: %s", csv_path)
        return rows
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for r in reader:
            text = r.get("paragraph") or r.get("text") or ""
            if text:
                rows.append({
                    "filename": r.get("filename", ""),
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "paragraph_index": int(r.get("paragraph_index", 0)),
                    "paragraph": text,
                })
    return rows


def build_embeddings(rows: List[dict], model_name: str = "all-MiniLM-L6-v2", batch_size: int = 64):
    logging.info("Loading model: %s", model_name)
    model = SentenceTransformer(model_name)

    texts = [r["paragraph"] for r in rows]
    if not texts:
        logging.error("No paragraphs to embed")
        return None, None

    logging.info("Encoding %d paragraphs", len(texts))
    embeddings = model.encode(texts, batch_size=batch_size, show_progress_bar=True, convert_to_numpy=True)

    # ensure float32
    embeddings = np.asarray(embeddings, dtype="float32")

    # normalize for cosine similarity
    faiss.normalize_L2(embeddings)

    return embeddings, model


def create_faiss_index(embeddings: np.ndarray):
    d = embeddings.shape[1]
    index = faiss.IndexFlatIP(d)
    index.add(embeddings)
    return index


def save_index_and_meta(index: faiss.Index, meta: List[dict], index_path: str, meta_path: str):
    try:
        faiss.write_index(index, index_path)
        logging.info("Saved FAISS index to %s", index_path)
    except Exception as e:
        logging.error("Failed to save index: %s", e)

    try:
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        logging.info("Saved metadata to %s", meta_path)
    except Exception as e:
        logging.error("Failed to save metadata: %s", e)


def main(csv_path: str, index_path: str = "embeddings.index", meta_path: str = "embeddings_meta.json", model_name: str = "all-MiniLM-L6-v2"):
    setup_logging()
    rows = load_paragraphs(csv_path)
    if not rows:
        logging.error("No rows loaded from CSV. Exiting.")
        return

    embeddings, model = build_embeddings(rows, model_name=model_name)
    if embeddings is None:
        return

    index = create_faiss_index(embeddings)
    save_index_and_meta(index, rows, index_path, meta_path)


def load_index_and_meta(index_path: str = "pg_index.faiss", meta_path: str = "embeddings_meta.json"):
    if not os.path.isfile(index_path):
        logging.error("FAISS index not found: %s", index_path)
        return None, None
    try:
        index = faiss.read_index(index_path)
    except Exception as e:
        logging.error("Failed to read FAISS index: %s", e)
        return None, None

    meta = []
    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
    except Exception as e:
        logging.error("Failed to read metadata JSON: %s", e)

    return index, meta


@functools.lru_cache(maxsize=1)
def get_model_cached(model_name: str = "all-MiniLM-L6-v2"):
    logging.info("Loading SentenceTransformer model (cached): %s", model_name)
    return SentenceTransformer(model_name)


@functools.lru_cache(maxsize=1)
def load_index_and_meta_cached(index_path: str = "pg_index.faiss", meta_path: str = "embeddings_meta.json"):
    return load_index_and_meta(index_path, meta_path)


def search_with_index(query: str, index_path: str = "pg_index.faiss", meta_path: str = "embeddings_meta.json", model_name: str = "all-MiniLM-L6-v2", top_k: int = 5):
    """Cached search: loads model and index once, encodes query, and returns top_k results."""
    setup_logging()
    index, meta = load_index_and_meta_cached(index_path, meta_path)
    if index is None or not meta:
        logging.error("Index or metadata not available (cached search)")
        return []

    model = get_model_cached(model_name)
    q_emb = model.encode([query], convert_to_numpy=True)
    q_emb = np.asarray(q_emb, dtype="float32")
    faiss.normalize_L2(q_emb)

    try:
        D, I = index.search(q_emb, top_k)
    except Exception as e:
        logging.error("FAISS search failed (cached): %s", e)
        return []

    results = []
    for score, idx in zip(D[0], I[0]):
        if idx < 0 or idx >= len(meta):
            continue
        item = meta[idx]
        results.append({
            "paragraph": item.get("paragraph", ""),
            "filename": item.get("filename", ""),
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "paragraph_index": item.get("paragraph_index", None),
            "score": float(score),
        })

    return results


def retrieve_context(query: str, index_path: str = "pg_index.faiss", meta_path: str = "embeddings_meta.json", model_name: str = "all-MiniLM-L6-v2", top_k: int = 5):
    """Encode `query`, search FAISS index, and return top `top_k` paragraph contexts.

    Returns a list of dicts: {paragraph, filename, title, url, paragraph_index, score}
    """
    setup_logging()
    index, meta = load_index_and_meta(index_path, meta_path)
    if index is None or not meta:
        logging.error("Index or metadata not available")
        return []

    model = SentenceTransformer(model_name)
    q_emb = model.encode([query], convert_to_numpy=True)
    q_emb = np.asarray(q_emb, dtype="float32")
    faiss.normalize_L2(q_emb)

    try:
        D, I = index.search(q_emb, top_k)
    except Exception as e:
        logging.error("FAISS search failed: %s", e)
        return []

    results = []
    for score, idx in zip(D[0], I[0]):
        if idx < 0 or idx >= len(meta):
            continue
        item = meta[idx]
        results.append({
            "paragraph": item.get("paragraph", ""),
            "filename": item.get("filename", ""),
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "paragraph_index": item.get("paragraph_index", None),
            "score": float(score),
        })

    return results


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="Create FAISS embeddings from cleaned essays CSV")
    p.add_argument("--csv", default="cleaned_essays.csv", help="Input cleaned CSV")
    p.add_argument("--index", default="embeddings.index", help="Output FAISS index path")
    p.add_argument("--meta", default="embeddings_meta.json", help="Output metadata JSON path")
    p.add_argument("--model", default="all-MiniLM-L6-v2", help="SentenceTransformer model name")
    args = p.parse_args()
    main(args.csv, args.index, args.meta, args.model)
