"""
Smoke test for RAG retriever with real indexed PDFs and Google Gemini API.

This requires:
1. GOOGLE_API_KEY environment variable set
2. FAISS indexes already created (run Phase 2A indexer first)
3. At least one company indexed in data/vector_store

Run with: python -m pytest tests/smoke_test_retriever.py -v -s
Or directly: python tests/smoke_test_retriever.py
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

from backend.rag.retriever import (
    retrieve_for_query,
    setup_embeddings,
    VECTOR_STORE,
)


def test_smoke_setup_embeddings():
    """Smoke test: Setup embeddings with real API key."""
    print("\n=== Testing setup_embeddings ===")

    if not os.getenv("GOOGLE_API_KEY"):
        print("SKIP: GOOGLE_API_KEY not set")
        return

    try:
        embed_model = setup_embeddings()
        assert embed_model is not None
        print("PASSED - Embeddings configured successfully")
    except Exception as e:
        print(f"FAILED: {e}")
        raise


def test_smoke_retrieve_basic():
    """Smoke test: Basic retrieval from indexed company."""
    print("\n=== Testing retrieve_for_query (basic) ===")

    if not os.getenv("GOOGLE_API_KEY"):
        print("SKIP: GOOGLE_API_KEY not set")
        return

    if not VECTOR_STORE.exists():
        print(f"SKIP: FAISS store does not exist at {VECTOR_STORE}")
        print("Run Phase 2A indexer first: python tests/smoke_test_indexer.py")
        return

    # Find an indexed company
    try:
        chroma_client = chromadb.PersistentClient(path=str(VECTOR_STORE))
        collections = chroma_client.list_collections()

        if not collections:
            print("SKIP: No indexed companies found")
            print("Run Phase 2A indexer first: python tests/smoke_test_indexer.py")
            return

        # Get first company
        collection = collections[0]
        company_name = collection.name.replace("company_", "").replace("_", " ").upper()

        print(f"Testing with indexed company: {company_name}")
        print(f"Collection: {collection.name}, Documents: {collection.count()}")

        # Test retrieval
        query = "financial performance revenue profit"
        results = retrieve_for_query(company_name, query, top_k=3)

        print(f"\nQuery: '{query}'")
        print(f"Retrieved {len(results)} results")

        for i, result in enumerate(results, 1):
            print(f"\n--- Result {i} ---")
            print(f"Score: {result.get('score', 'N/A')}")
            print(f"Metadata: {result.get('metadata', {})}")
            print(f"Text preview: {result['text'][:150]}...")

        assert len(results) > 0
        assert all("text" in r for r in results)
        assert all("metadata" in r for r in results)

        print("\nPASSED - Retrieved results successfully")

    except Exception as e:
        print(f"FAILED: {e}")
        raise


def test_smoke_retrieve_multiple_queries():
    """Smoke test: Test multiple different queries."""
    print("\n=== Testing multiple queries ===")

    if not os.getenv("GOOGLE_API_KEY"):
        print("SKIP: GOOGLE_API_KEY not set")
        return

    if not VECTOR_STORE.exists():
        print(f"SKIP: FAISS store does not exist")
        return

    try:
        chroma_client = chromadb.PersistentClient(path=str(VECTOR_STORE))
        collections = chroma_client.list_collections()

        if not collections:
            print("SKIP: No indexed companies found")
            return

        company_name = collections[0].name.replace("company_", "").replace("_", " ").upper()

        queries = [
            "revenue and earnings",
            "risk factors",
            "business operations",
        ]

        for query in queries:
            print(f"\nQuery: '{query}'")
            results = retrieve_for_query(company_name, query, top_k=2)
            print(f"  Retrieved: {len(results)} chunks")

            assert isinstance(results, list)

        print("\nPASSED - Multiple queries executed successfully")

    except Exception as e:
        print(f"FAILED: {e}")
        raise


def test_smoke_top_k_variation():
    """Smoke test: Test different top_k values."""
    print("\n=== Testing top_k parameter ===")

    if not os.getenv("GOOGLE_API_KEY"):
        print("SKIP: GOOGLE_API_KEY not set")
        return

    if not VECTOR_STORE.exists():
        print(f"SKIP: FAISS store does not exist")
        return

    try:
        chroma_client = chromadb.PersistentClient(path=str(VECTOR_STORE))
        collections = chroma_client.list_collections()

        if not collections:
            print("SKIP: No indexed companies found")
            return

        company_name = collections[0].name.replace("company_", "").replace("_", " ").upper()
        query = "financial information"

        for top_k in [1, 3, 5]:
            results = retrieve_for_query(company_name, query, top_k=top_k)
            print(f"top_k={top_k}: Retrieved {len(results)} results")

            # Should retrieve at most top_k results
            assert len(results) <= top_k

        print("\nPASSED - top_k parameter works correctly")

    except Exception as e:
        print(f"FAILED: {e}")
        raise


def test_smoke_missing_company():
    """Smoke test: Graceful handling of non-existent company."""
    print("\n=== Testing missing company handling ===")

    if not os.getenv("GOOGLE_API_KEY"):
        print("SKIP: GOOGLE_API_KEY not set")
        return

    if not VECTOR_STORE.exists():
        print(f"SKIP: FAISS store does not exist")
        return

    try:
        results = retrieve_for_query("NONEXISTENT_COMPANY_XYZ", "test query")

        assert results == []
        print("PASSED - Gracefully handled missing company")

    except Exception as e:
        print(f"FAILED: {e}")
        raise


def test_smoke_empty_query():
    """Smoke test: Graceful handling of empty query."""
    print("\n=== Testing empty query handling ===")

    try:
        results = retrieve_for_query("TESTCO", "")
        assert results == []

        results = retrieve_for_query("TESTCO", "   ")
        assert results == []

        print("PASSED - Gracefully handled empty query")

    except Exception as e:
        print(f"FAILED: {e}")
        raise


def test_smoke_json_serializable():
    """Smoke test: Verify output is JSON serializable."""
    print("\n=== Testing JSON serialization ===")

    if not os.getenv("GOOGLE_API_KEY"):
        print("SKIP: GOOGLE_API_KEY not set")
        return

    if not VECTOR_STORE.exists():
        print(f"SKIP: FAISS store does not exist")
        return

    try:
        import json

        chroma_client = chromadb.PersistentClient(path=str(VECTOR_STORE))
        collections = chroma_client.list_collections()

        if not collections:
            print("SKIP: No indexed companies found")
            return

        company_name = collections[0].name.replace("company_", "").replace("_", " ").upper()
        results = retrieve_for_query(company_name, "test", top_k=2)

        # Should be JSON serializable
        json_str = json.dumps(results)
        parsed = json.loads(json_str)

        assert isinstance(parsed, list)
        if parsed:
            assert "text" in parsed[0]
            assert "metadata" in parsed[0]

        print("PASSED - Output is JSON serializable")

    except Exception as e:
        print(f"FAILED: {e}")
        raise


if __name__ == "__main__":
    """Run smoke tests directly."""
    print("=" * 60)
    print("RAG RETRIEVER SMOKE TESTS")
    print("=" * 60)

    try:
        test_smoke_setup_embeddings()
        test_smoke_retrieve_basic()
        test_smoke_retrieve_multiple_queries()
        test_smoke_top_k_variation()
        test_smoke_missing_company()
        test_smoke_empty_query()
        test_smoke_json_serializable()

        print("\n" + "=" * 60)
        print("ALL SMOKE TESTS PASSED ✓")
        print("=" * 60)

    except AssertionError as e:
        print(f"\nFAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
