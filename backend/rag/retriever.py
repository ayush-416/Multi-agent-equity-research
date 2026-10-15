"""
RAG Retriever: Query and retrieve relevant chunks from FAISS.

Retrieves relevant document chunks for a company using vector similarity search with Google Gemini embeddings.
"""

import logging
import re
import os
from pathlib import Path
from typing import Dict, List, Optional, Any

from backend.rag.gemini_embedding import GeminiEmbedding
from backend.rag.vector_store import FAISSVectorStore

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Project root (reuse from indexer)
PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
VECTOR_STORE_DIR = DATA_DIR / "vector_store"

# Singleton embedding model (loaded once)
_embedding_model: Optional[GeminiEmbedding] = None


def _get_embedding_model() -> GeminiEmbedding:
    """
    Get or create singleton embedding model instance.

    Returns:
        GeminiEmbedding instance
    """
    global _embedding_model

    if _embedding_model is None:
        google_api_key = os.getenv("GOOGLE_API_KEY")
        if not google_api_key:
            raise ValueError("GOOGLE_API_KEY environment variable not set")

        _embedding_model = GeminiEmbedding(
            api_key=google_api_key,
            model_name="models/gemini-embedding-001"
        )
        logger.info("Initialized embedding model singleton")

    return _embedding_model


def _normalize_company_name(company: str) -> str:
    """
    Normalize company name to match folder structure.

    Examples:
    - "HDFC Bank" -> "HDFCBANK"
    - "hdfc bank" -> "HDFCBANK"
    - "Reliance Industries" -> "RELIANCE"
    """
    # First, remove spaces and special characters, then uppercase
    normalized = company.upper()
    normalized = re.sub(r'[^A-Z0-9]', '', normalized)

    # Then remove common suffixes AFTER concatenation
    for suffix in ["LIMITED", "LTD", "INDUSTRIES", "INC", "CORPORATION", "CORP"]:
        if normalized.endswith(suffix):
            normalized = normalized[:-len(suffix)]
            break

    return normalized


def retrieve_for_query(
    company: str,
    query: str,
    top_k: int = 5
) -> List[Dict[str, Any]]:
    """
    Retrieve relevant document chunks for a company query.

    Args:
        company: Company name (will be normalized to match indexed company)
        query: Search query text
        top_k: Number of top results to return (default: 5)

    Returns:
        List of dicts with keys:
        - text: The chunk text content
        - score: Relevance score
        - metadata: Dict with company, file_name, page_number, source_path

    Handles gracefully:
    - Missing/non-existent index for company
    - Empty query string
    - FAISS connection errors
    - Embedding API errors
    """
    result = []

    # Validate inputs
    if not query or not query.strip():
        logger.warning("Empty query provided")
        return result

    if not company or not company.strip():
        logger.warning("Empty company name provided")
        return result

    # Normalize company name to match folder structure
    company_normalized = _normalize_company_name(company)
    logger.info(f"Normalized company '{company}' to '{company_normalized}' for index lookup")

    try:
        # Check if index exists for company
        company_store_path = VECTOR_STORE_DIR / company_normalized
        if not company_store_path.exists():
            logger.warning(f"No index found for company: {company} (tried {company_normalized})")
            return result

        if not (company_store_path / "index.faiss").exists():
            logger.warning(f"Index for {company_normalized} is incomplete or corrupted")
            return result

        logger.info(f"Loading index for {company_normalized} from {company_store_path}")

        # Load the vector store
        vector_store = FAISSVectorStore.load(company_store_path)

        # Initialize embeddings (use singleton)
        embed_model = _get_embedding_model()

        # Generate query embedding
        logger.info(f"Generating query embedding for: {query[:50]}...")
        query_embedding = embed_model.embed_query(query)

        # Retrieve documents
        result = vector_store.search(query_embedding, top_k=top_k)

        logger.info(f"Retrieved {len(result)} chunks for query")

    except Exception as e:
        logger.error(f"Failed to retrieve for query: {e}", exc_info=True)

    return result
