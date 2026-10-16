"""
Debug script for RAG retrieval issues.

Prints top 5 raw similarity scores without threshold or filter,
metadata keys stored on chunks, and embedding model/dimension/task_type
used at ingestion vs query time.

Usage:
    python scripts/debug_retrieval.py "Reliance Industries" "business overview"
"""

import sys
import os
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import logging
import re
from backend.rag.gemini_embedding import GeminiEmbedding
from backend.rag.vector_store import FAISSVectorStore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATA_DIR = PROJECT_ROOT / "data"
VECTOR_STORE_DIR = DATA_DIR / "vector_store"


def _normalize_company_name(company: str) -> str:
    """Normalize company name to match folder structure."""
    normalized = company.upper()
    normalized = re.sub(r'[^A-Z0-9]', '', normalized)

    for suffix in ["LIMITED", "LTD", "INDUSTRIES", "INC", "CORPORATION", "CORP"]:
        if normalized.endswith(suffix):
            normalized = normalized[:-len(suffix)]
            break

    return normalized


def debug_retrieval(company: str, query: str):
    """
    Debug retrieval for a company and query.

    Args:
        company: Company name (e.g., "Reliance Industries")
        query: Search query (e.g., "business overview")
    """
    print(f"\n{'='*80}")
    print(f"DEBUG RETRIEVAL")
    print(f"{'='*80}")
    print(f"Company: {company}")
    print(f"Query: {query}")
    print(f"{'='*80}\n")

    # Normalize company name
    company_normalized = _normalize_company_name(company)
    print(f"[OK] Normalized company name: '{company}' -> '{company_normalized}'")

    # Check if index exists
    company_store_path = VECTOR_STORE_DIR / company_normalized
    if not company_store_path.exists():
        print(f"[ERROR] No index found at {company_store_path}")
        print(f"\nAvailable indexes:")
        if VECTOR_STORE_DIR.exists():
            for idx_dir in VECTOR_STORE_DIR.iterdir():
                if idx_dir.is_dir():
                    print(f"  - {idx_dir.name}")
        else:
            print(f"  (vector store directory doesn't exist: {VECTOR_STORE_DIR})")
        return

    if not (company_store_path / "index.faiss").exists():
        print(f"[ERROR] Index for {company_normalized} is incomplete (no index.faiss)")
        return

    print(f"[OK] Index found at {company_store_path}")

    # Load vector store
    try:
        vector_store = FAISSVectorStore.load(company_store_path)
        print(f"[OK] Vector store loaded")
        print(f"  - Total chunks indexed: {vector_store.index.ntotal}")
        print(f"  - Dimension: {vector_store.index.d}")
    except Exception as e:
        print(f"[ERROR] Loading vector store: {e}")
        return

    # Check metadata
    print(f"\n{'='*80}")
    print(f"METADATA INSPECTION (first 3 chunks)")
    print(f"{'='*80}")

    if vector_store.metadata:
        for i, meta in enumerate(vector_store.metadata[:3]):
            print(f"\nChunk {i}:")
            print(f"  Keys: {list(meta.keys())}")
            for key, value in meta.items():
                if isinstance(value, str) and len(value) > 100:
                    print(f"  {key}: {value[:100]}...")
                else:
                    print(f"  {key}: {value}")
    else:
        print("  (No metadata available)")

    # Initialize embedding model for query
    print(f"\n{'='*80}")
    print(f"EMBEDDING MODEL")
    print(f"{'='*80}")

    try:
        google_api_key = os.getenv("GOOGLE_API_KEY")
        if not google_api_key:
            print(f"[ERROR] GOOGLE_API_KEY not set")
            return

        embed_model = GeminiEmbedding(
            api_key=google_api_key,
            model_name="models/gemini-embedding-001"
        )
        print(f"[OK] Embedding model: gemini-embedding-001")
        print(f"  - Task type: RETRIEVAL_QUERY")

        # Generate query embedding
        query_embedding = embed_model.embed_query(query)
        print(f"[OK] Query embedding generated")
        print(f"  - Dimension: {len(query_embedding)}")
        print(f"  - Sample values: {query_embedding[:5]}")

    except Exception as e:
        print(f"[ERROR] Generating query embedding: {e}")
        import traceback
        traceback.print_exc()
        return

    # Perform raw search (no threshold, return all results)
    print(f"\n{'='*80}")
    print(f"RAW SIMILARITY SEARCH (top 10, no threshold)")
    print(f"{'='*80}")

    try:
        import numpy as np

        # Convert to numpy array
        query_vec = np.array([query_embedding], dtype=np.float32)

        # Search FAISS index
        k = min(10, vector_store.index.ntotal)  # Get top 10 or all if less
        distances, indices = vector_store.index.search(query_vec, k)

        print(f"\nTop {k} results:")
        for rank, (dist, idx) in enumerate(zip(distances[0], indices[0]), 1):
            if idx < 0:  # FAISS returns -1 for missing results
                continue

            # Get metadata if available
            meta = vector_store.metadata[idx] if idx < len(vector_store.metadata) else {}
            text_preview = vector_store.texts[idx][:100] if idx < len(vector_store.texts) else "N/A"

            print(f"\n  Rank {rank}:")
            print(f"    Distance: {dist:.4f}")
            print(f"    Index: {idx}")
            print(f"    Company filter: {meta.get('company', 'N/A')}")
            print(f"    File: {meta.get('file_name', 'N/A')}")
            print(f"    Text preview: {text_preview}...")

        # Check if company filter matches
        print(f"\n{'='*80}")
        print(f"COMPANY FILTER ANALYSIS")
        print(f"{'='*80}")

        matching_chunks = 0
        for idx in range(min(100, len(vector_store.metadata))):
            meta = vector_store.metadata[idx]
            if meta.get('company') == company:
                matching_chunks += 1

        print(f"Chunks with company='{company}': {matching_chunks}")

        # Check normalized versions
        for idx in range(min(10, len(vector_store.metadata))):
            meta = vector_store.metadata[idx]
            stored_company = meta.get('company', '')
            print(f"  Chunk {idx} company: '{stored_company}'")

    except Exception as e:
        print(f"[ERROR] During raw search: {e}")
        import traceback
        traceback.print_exc()
        return

    print(f"\n{'='*80}")
    print(f"DIAGNOSIS")
    print(f"{'='*80}")

    if vector_store.index.ntotal == 0:
        print("[ERROR] Index is empty - no chunks indexed")
    elif len(distances[0]) == 0 or distances[0][0] > 1.0:
        print("[ERROR] No relevant chunks found (all distances > 1.0)")
        print("  Possible causes:")
        print("  - Query embedding dimension mismatch")
        print("  - Different task_type at ingestion vs query")
        print("  - Index corrupted")
    elif matching_chunks == 0:
        print("[ERROR] Company filter mismatch")
        print(f"  Expected: '{company}'")
        print(f"  Found in index: {set(m.get('company', 'N/A') for m in vector_store.metadata[:10])}")
    else:
        print("[OK] Retrieval appears to be working")
        print(f"  - Found {k} results")
        print(f"  - Top distance: {distances[0][0]:.4f}")
        print(f"  - Matching chunks: {matching_chunks}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python scripts/debug_retrieval.py <company> <query>")
        print('Example: python scripts/debug_retrieval.py "Reliance Industries" "business overview"')
        sys.exit(1)

    company = sys.argv[1]
    query = sys.argv[2]

    debug_retrieval(company, query)
