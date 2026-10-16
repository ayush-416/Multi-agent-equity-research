# RAG Retrieval Fix Summary

## Issue Found
The RAG retrieval was returning 0 chunks despite having a 311-document index for RELIANCE.

## Root Cause
The FAISS index is **corrupted**. When searching, FAISS returns `-1` for all indices, which means the vectors weren't properly stored or the index format is incompatible.

**Evidence:**
- Index exists: `data/vector_store/RELIANCE/index.faiss` (3.7MB)
- Documents exist: `data/vector_store/RELIANCE/documents.pkl` (284KB)
- Index reports 311 documents with dimension 3072
- Metadata is correct: company='RELIANCE', file names, etc.
- Embeddings are correct: query dimension 3072 matches index dimension
- **BUT**: FAISS search returns all `-1` indices = corrupted index

## Fix Applied

### 1. Added dotenv to retriever.py ✓
The retriever wasn't loading `.env`, so `GOOGLE_API_KEY` was unavailable.

**File modified:** `backend/rag/retriever.py`
- Added `from dotenv import load_dotenv` and `load_dotenv()`

### 2. Added properties to vector_store.py ✓
For debugging, added `.texts` and `.metadata` properties to FAISSVectorStore.

**File modified:** `backend/rag/vector_store.py`

### 3. Fixed Unicode in debug_retrieval.py ✓
Replaced Unicode checkmarks with ASCII `[OK]`/`[ERROR]` for Windows compatibility.

**File modified:** `scripts/debug_retrieval.py`

### 4. Re-indexing RELIANCE (IN PROGRESS)
Running: `ingest_company_filings('RELIANCE', force_reindex=True)`

This will:
- Delete the corrupted index
- Re-process the PDF: `06_RIL_IAR_2025-26_Standalone_22-05-26.pdf`
- Generate fresh embeddings with `task_type="retrieval_document"`
- Create a new FAISS index
- Save to `data/vector_store/RELIANCE/`

**Status:** Background process running (takes ~2-5 minutes for large PDFs)

---

## After Re-indexing Completes

### Test Retrieval
```bash
python -c "from backend.rag.retriever import retrieve_for_query; results = retrieve_for_query('Reliance Industries', 'business overview', top_k=3); print(f'Retrieved {len(results)} chunks'); [print(f'Chunk {i+1}: {r[\"text\"][:100]}...') for i, r in enumerate(results)]"
```

**Expected:** Should return 3+ chunks with text from the Reliance annual report.

### Test Debug Script
```bash
python scripts/debug_retrieval.py "Reliance Industries" "business overview"
```

**Expected:** Should show top 10 results with positive similarity scores (< 1.0).

### Test filing_analyst Agent
```bash
python -c "from backend.agents.filing_analyst import run_filing_analyst; result = run_filing_analyst('RELIANCE', 'Reliance Industries'); print(f'Status: {result[\"status\"]}'); print(f'Summary: {result[\"filing_summary\"]}')"
```

**Expected:** Status should be "ok" with a filing summary from the annual report.

---

## Why the Index Got Corrupted

Possible causes:
1. **Interrupted indexing** - Process killed mid-write
2. **FAISS version mismatch** - Different FAISS version used during indexing vs retrieval
3. **Incomplete write** - Disk space or permission issue during save
4. **Python environment change** - numpy/faiss-cpu version changed

The re-indexing will create a fresh, clean index.

---

## Files Modified (Already Done)
- `backend/rag/retriever.py` - Added dotenv loading
- `backend/rag/vector_store.py` - Added .texts and .metadata properties
- `scripts/debug_retrieval.py` - Fixed Unicode for Windows

## Next Steps (Manual)
1. Wait for re-indexing to complete (~2-5 minutes)
2. Run the test commands above
3. If HDFCBANK also has issues, re-index it too: `python -c "from backend.rag.indexer import ingest_company_filings; print(ingest_company_filings('HDFCBANK', force_reindex=True))"`
