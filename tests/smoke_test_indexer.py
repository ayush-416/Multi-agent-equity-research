"""
Smoke test for RAG indexer with real PDFs and Google Gemini API.

This requires:
1. GOOGLE_API_KEY environment variable set
2. At least one PDF in data/filings/<COMPANY>/ directory

Run with: python -m pytest tests/smoke_test_indexer.py -v -s
Or directly: python tests/smoke_test_indexer.py
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

from backend.rag.indexer import (
    get_company_pdf_paths,
    ingest_company_filings,
    ingest_all_companies,
    FILINGS_DIR,
)


def test_smoke_get_pdf_paths():
    """Smoke test: Get PDF paths for existing companies."""
    print("\n=== Testing get_company_pdf_paths ===")

    # List all company directories
    if not FILINGS_DIR.exists():
        print(f"SKIP: {FILINGS_DIR} does not exist")
        return

    companies = [d.name for d in FILINGS_DIR.iterdir() if d.is_dir()]
    print(f"Found {len(companies)} company directories: {companies}")

    if not companies:
        print("SKIP: No company directories found")
        return

    # Test first company
    test_company = companies[0]
    print(f"\nTesting with company: {test_company}")

    pdf_paths = get_company_pdf_paths(test_company)
    print(f"Found {len(pdf_paths)} PDFs")

    for pdf_path in pdf_paths[:3]:  # Show first 3
        print(f"  - {pdf_path.name} ({pdf_path.stat().st_size} bytes)")

    assert isinstance(pdf_paths, list)
    print("PASSED")


def test_smoke_ingest_single_company():
    """Smoke test: Ingest PDFs for a single company."""
    print("\n=== Testing ingest_company_filings ===")

    # Check for API key
    if not os.getenv("GOOGLE_API_KEY"):
        print("SKIP: GOOGLE_API_KEY not set")
        return

    # Find a company with PDFs
    if not FILINGS_DIR.exists():
        print(f"SKIP: {FILINGS_DIR} does not exist")
        return

    companies = [d.name for d in FILINGS_DIR.iterdir() if d.is_dir()]
    if not companies:
        print("SKIP: No company directories found")
        return

    # Use first company with PDFs
    test_company = None
    for company in companies:
        if get_company_pdf_paths(company):
            test_company = company
            break

    if not test_company:
        print("SKIP: No companies with PDFs found")
        return

    print(f"Testing with company: {test_company}")

    # Test ingestion
    result = ingest_company_filings(test_company, force_reindex=False)

    print(f"Result: {result}")
    assert result["success"] is True
    assert result["company"] == test_company
    assert "documents_count" in result

    print(f"PASSED - Indexed {result['documents_count']} documents")


def test_smoke_ingest_all_companies():
    """Smoke test: Ingest PDFs for all companies."""
    print("\n=== Testing ingest_all_companies ===")

    # Check for API key
    if not os.getenv("GOOGLE_API_KEY"):
        print("SKIP: GOOGLE_API_KEY not set")
        return

    if not FILINGS_DIR.exists():
        print(f"SKIP: {FILINGS_DIR} does not exist")
        return

    # Test ingestion of all companies
    result = ingest_all_companies(force_reindex=False)

    print(f"\nResult summary:")
    print(f"  Success: {result['success']}")
    print(f"  Companies processed: {result['companies_processed']}")
    print(f"  Total files: {result['total_files']}")
    print(f"  Total documents: {result['total_documents']}")

    if "results" in result:
        print(f"\nPer-company results:")
        for company_result in result["results"]:
            status = "OK" if company_result["success"] else "FAIL"
            print(
                f"  {status} {company_result['company']}: "
                f"{company_result.get('documents_count', 0)} documents"
            )

    assert result["success"] is True
    print("\nPASSED")


def test_smoke_force_reindex():
    """Smoke test: Force reindex a company."""
    print("\n=== Testing force_reindex ===")

    # Check for API key
    if not os.getenv("GOOGLE_API_KEY"):
        print("SKIP: GOOGLE_API_KEY not set")
        return

    if not FILINGS_DIR.exists():
        print(f"SKIP: {FILINGS_DIR} does not exist")
        return

    # Find a company with PDFs
    companies = [d.name for d in FILINGS_DIR.iterdir() if d.is_dir()]
    test_company = None
    for company in companies:
        if get_company_pdf_paths(company):
            test_company = company
            break

    if not test_company:
        print("SKIP: No companies with PDFs found")
        return

    print(f"Testing force_reindex with company: {test_company}")

    # Force reindex
    result = ingest_company_filings(test_company, force_reindex=True)

    print(f"Result: {result}")
    assert result["success"] is True
    assert result["files_processed"] > 0
    assert result["documents_count"] > 0

    print(f"PASSED - Reindexed {result['documents_count']} documents")


if __name__ == "__main__":
    """Run smoke tests directly."""
    print("=" * 60)
    print("RAG INDEXER SMOKE TESTS")
    print("=" * 60)

    try:
        test_smoke_get_pdf_paths()
        test_smoke_ingest_single_company()
        test_smoke_ingest_all_companies()
        test_smoke_force_reindex()

        print("\n" + "=" * 60)
        print("ALL SMOKE TESTS PASSED")
        print("=" * 60)

    except AssertionError as e:
        print(f"\nFAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
