import json, os, sqlite3
import numpy as np
import pandas as pd
from .config import DB_PATH, PROJECT_ROOT, embed_documents, embed_query

properties_df = pd.read_csv(PROJECT_ROOT / "data" / "properties.csv")
faqs_df = pd.read_csv(PROJECT_ROOT / "data" / "faqs.csv")

# 2.2 Structured DB (SQLite) — used for exact facts: price, availability, possession, RDA eligibility
# Fresh project-local file each run; avoids pandas.to_sql()'s type-inference quirks and stale/corrupted DB files.
DB_PATH = DB_PATH

# if os.path.exists(DB_PATH):
#     try:
#         os.remove(DB_PATH)
#     except PermissionError:
#         print(f"Warning: could not remove {DB_PATH}; it may be open in another process/tool.")

def _sqlite_value(value):
    if pd.isna(value):
        return None
    return value.item() if hasattr(value, "item") else value

def init_property_db():
    numeric_cols = {
        "price_pkr",
        "price_usd_est",
        "installments_months",
        "rental_yield_pct",
        "bedrooms"
    }

    columns = list(properties_df.columns)

    column_defs = [
        f'"{c}" {"REAL" if c in numeric_cols else "TEXT"}'
        for c in columns
    ]

    conn = sqlite3.connect(DB_PATH, timeout=10)

    try:
        conn.execute(
            f'CREATE TABLE IF NOT EXISTS properties ({", ".join(column_defs)})'
        )

        # Keep the property DB synchronized with properties.csv
        conn.execute("DELETE FROM properties")

        quoted_cols = ", ".join(f'"{c}"' for c in columns)
        placeholders = ", ".join("?" for _ in columns)

        rows = [
            tuple(_sqlite_value(v) for v in row)
            for row in properties_df.itertuples(
                index=False,
                name=None
            )
        ]

        conn.executemany(
            f'INSERT INTO properties ({quoted_cols}) VALUES ({placeholders})',
            rows
        )

        conn.commit()

    finally:
        conn.close()

init_property_db()

def sql_query(sql: str, params: tuple = ()):
    """Run a read-only SQL query against the properties table. Used as a tool for exact numeric/boolean facts."""
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()



# 2.3 Vector store — plain NumPy cosine similarity over Gemini embeddings (no ChromaDB / no native deps).
# At this dataset size (8 properties, 10 FAQs) this is just as accurate as a real vector DB and cannot
# hard-crash the kernel, unlike ChromaDB's onnxruntime/hnswlib native dependencies.

class SimpleVectorStore:
    """Minimal in-memory vector store: cosine similarity over a NumPy matrix. No native dependencies."""
    def __init__(self, name, texts, ids):
        self.name = name
        self.texts = list(texts)
        self.ids = list(ids)
        embeddings = embed_documents(self.texts, task_type="RETRIEVAL_DOCUMENT")
        matrix = np.array(embeddings, dtype=np.float32)
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1e-8
        self.matrix = matrix / norms  # pre-normalize once so query time is a single dot product

    def query(self, query_text, k=3):
        q = np.array(embed_query(query_text), dtype=np.float32)
        q = q / (np.linalg.norm(q) + 1e-8)
        scores = self.matrix @ q
        top_idx = np.argsort(-scores)[:k]
        return [self.texts[i] for i in top_idx]

def property_to_doc(row):
    return (f"{row['title']} in {row['society']}, {row['city']}. Type: {row['type']}, {row['bedrooms']} bed, "
            f"{row['size']}. Price PKR {row['price_pkr']:,} (~USD {row['price_usd_est']:,}). "
            f"Payment plan: {row['payment_plan']} over {row['installments_months']} months. "
            f"Status: {row['possession_status']} ({row['possession_date']}). Developer: {row['developer']} "
            f"({row['developer_track_record']}). RDA eligible: {row['rda_eligible']}. "
            f"Rental yield ~{row['rental_yield_pct']}%. Near: {row['near_landmarks']}. Notes: {row['notes']}")

_faq_store = None
_property_store = None

def _stores():
    global _faq_store, _property_store
    if _faq_store is None:
        faq_texts = (faqs_df["question"] + " -- " + faqs_df["answer"]).tolist()
        faq_ids = [f"faq_{i}" for i in range(len(faqs_df))]
        _faq_store = SimpleVectorStore("nrp_faqs", faq_texts, faq_ids)
    if _property_store is None:
        prop_texts = [property_to_doc(r) for _, r in properties_df.iterrows()]
        prop_ids = properties_df["property_id"].tolist()
        _property_store = SimpleVectorStore("nrp_properties", prop_texts, prop_ids)
    return _faq_store, _property_store


# 2.4 Retriever functions (semantic) — brochures/FAQs/descriptions go here, NOT exact prices (that's SQL's job)
def rag_search_faqs(query: str, k: int = 3):
    """Semantic search over the FAQ knowledge base. Use for policy/process/trust questions."""
    return _stores()[0].query(query, k=k)

def rag_search_properties(query: str, k: int = 3):
    """Semantic search over property descriptions. Use for fuzzy/descriptive matching (e.g. 'good rental yield near Islamabad airport')."""
    return _stores()[1].query(query, k=k)



# 2.6 Property recommendation combining structured filters + purpose/currency awareness
def recommend_properties(budget_pkr: float = None, city: str = None, purpose: str = None,
                          bedrooms: int = None, min_rda: bool = None, top_n: int = 3):
    """Filter properties by budget/city/purpose/bedrooms/RDA-eligibility and rank by fit.
    purpose: 'investment' favors high rental_yield_pct; 'own_use' favors Ready possession_status.
    """
    df = properties_df.copy()
    if budget_pkr:
        df = df[df["price_pkr"] <= budget_pkr * 1.15]  # small headroom
    if city:
        df = df[df["city"].str.lower() == city.lower()]
    if bedrooms is not None:
        df = df[
            (df["bedrooms"] == bedrooms)
            & (~df["type"].isin(["Plot", "Commercial"]))
        ]
    if min_rda:
        df = df[df["rda_eligible"] == "Yes"]
    if df.empty:
        return []
    if purpose == "investment":
        df = df.sort_values("rental_yield_pct", ascending=False)
    elif purpose == "own_use":
        df = df.assign(_ready=(df["possession_status"] == "Ready").astype(int)).sort_values("_ready", ascending=False)
    else:
        df = df.sort_values("price_pkr")
    return df.head(top_n).to_dict("records")

