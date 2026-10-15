"""
Filing Analyst Agent: Analyzes company financial filings using RAG retrieval.

Retrieves and analyzes key information from company filings including business
overview, financial performance, risks, and outlook.
"""

import logging
import json
import re
import os
from typing import Dict, Any, List, Optional

from langchain_google_genai import ChatGoogleGenerativeAI
from backend.rag.retriever import retrieve_for_query

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Singleton instances for LLM and embedding client (loaded once)
_llm_instance: Optional[ChatGoogleGenerativeAI] = None
_embedding_client = None  # Will be initialized in retriever


def _get_llm() -> ChatGoogleGenerativeAI:
    """
    Get or create singleton LLM instance.

    Returns:
        ChatGoogleGenerativeAI instance
    """
    global _llm_instance

    if _llm_instance is None:
        google_api_key = os.getenv("GOOGLE_API_KEY")
        if not google_api_key:
            raise ValueError("GOOGLE_API_KEY environment variable not set")

        # Use configurable model (defaults to gemini-2.5-flash for free tier)
        model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

        _llm_instance = ChatGoogleGenerativeAI(
            model=model_name,
            temperature=0,
            google_api_key=google_api_key
        )
        logger.info(f"Initialized LLM singleton: {model_name}")

    return _llm_instance


def run_filing_analyst(ticker: str, company_name: str) -> Dict[str, Any]:
    """
    Analyze company financial filings using RAG retrieval.

    Args:
        ticker: Stock ticker symbol (e.g., "RELIANCE")
        company_name: Full company name (e.g., "Reliance Industries")

    Returns:
        Dict with keys:
        - status: "success", "partial_success", or "error"
        - ticker: Stock ticker
        - company_name: Company name
        - filing_summary: Brief summary of filing analysis
        - key_points: List of key business/financial points
        - risks: List of identified risk factors
        - outlook: Future outlook and capital expenditure plans
        - sources: List of source documents used
        - error: Error message if status is "error"
    """
    result = {
        "status": "error",
        "ticker": ticker,
        "company_name": company_name,
        "filing_summary": "",
        "key_points": [],
        "risks": [],
        "outlook": "",
        "sources": [],
        "error": None,
        "rag_status": "not_available",  # Track RAG retrieval status
        "context_retrieved": False  # Track if any context was found
    }

    try:
        logger.info(f"Starting filing analysis for {ticker} ({company_name})")

        # Define filing-focused questions
        questions = [
            "business overview and main operations",
            "revenue profit performance and financial metrics",
            "management discussion and analysis",
            "key risk factors and challenges",
            "capital expenditure future outlook and plans",
            "debt liquidity and financial position"
        ]

        # Retrieve context for each question
        all_contexts = []
        sources_set = set()

        for question in questions:
            logger.info(f"Retrieving context for: {question}")
            chunks = retrieve_for_query(
                company=company_name,
                query=question,
                top_k=3
            )

            if chunks:
                for chunk in chunks:
                    all_contexts.append({
                        "question": question,
                        "text": chunk["text"],
                        "metadata": chunk.get("metadata", {})
                    })

                    # Track sources
                    if "file_name" in chunk.get("metadata", {}):
                        sources_set.add(chunk["metadata"]["file_name"])

        # Check if we have any context
        if not all_contexts:
            logger.warning(f"No filing context retrieved for {company_name}")
            result["status"] = "partial_success"
            result["rag_status"] = "not_available"
            result["context_retrieved"] = False
            result["filing_summary"] = f"No indexed filings found for {company_name}"
            result["error"] = "No retrieved context from filings"
            return result

        logger.info(f"Retrieved {len(all_contexts)} context chunks from {len(sources_set)} sources")
        result["sources"] = sorted(list(sources_set))
        result["rag_status"] = "available"
        result["context_retrieved"] = True

        # Build context for LLM
        context_text = "\n\n---\n\n".join([
            f"Question: {ctx['question']}\nContent: {ctx['text']}"
            for ctx in all_contexts
        ])

        # Create prompt for LLM
        prompt = f"""You are a financial analyst analyzing company filings. Based ONLY on the provided filing excerpts, create a comprehensive analysis.

Company: {company_name} ({ticker})

Filing Context:
{context_text}

Instructions:
1. Answer ONLY from the provided context - do not add external knowledge
2. If information is not in the context, state "Not available in filings"
3. Be specific and cite key facts from the filings
4. Return your analysis as a JSON object with this exact structure:

{{
  "filing_summary": "2-3 sentence overview of the company and filings",
  "key_points": [
    "Business point 1",
    "Financial metric 1",
    "Management insight 1",
    "... (3-7 specific points)"
  ],
  "risks": [
    "Risk factor 1",
    "Risk factor 2",
    "... (3-5 identified risks)"
  ],
  "outlook": "Summary of future plans, capital expenditure, and outlook from filings"
}}

Return ONLY the JSON object, no markdown code fences or additional text."""

        # Call LLM (use singleton instance)
        try:
            llm = _get_llm()

            logger.info("Calling Gemini LLM for analysis")
            response = llm.invoke(prompt)
            response_text = response.content.strip()

            logger.info(f"LLM response length: {len(response_text)} characters")

            # Strip markdown code fences if present
            response_text = re.sub(r'^```(?:json)?\s*\n?', '', response_text)
            response_text = re.sub(r'\n?```\s*$', '', response_text)
            response_text = response_text.strip()

            # Parse JSON response
            try:
                analysis = json.loads(response_text)

                result["filing_summary"] = analysis.get("filing_summary", "")
                result["key_points"] = analysis.get("key_points", [])
                result["risks"] = analysis.get("risks", [])
                result["outlook"] = analysis.get("outlook", "")
                result["status"] = "success"

                logger.info(f"Filing analysis completed successfully for {ticker}")

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse LLM JSON response: {e}")
                logger.error(f"Response text: {response_text[:500]}")

                result["status"] = "partial_success"
                result["filing_summary"] = f"Analysis completed but response formatting issue"
                result["error"] = f"JSON parse error: {str(e)}"

                # Try to extract some info from raw text
                result["key_points"] = [
                    f"Raw analysis available (parsing issue): {response_text[:200]}..."
                ]

        except Exception as e:
            logger.error(f"LLM call failed: {e}", exc_info=True)
            result["status"] = "partial_success"
            result["filing_summary"] = f"Retrieved {len(all_contexts)} filing excerpts"
            result["error"] = f"LLM analysis failed: {str(e)}"
            result["key_points"] = [
                f"Context retrieved from {len(sources_set)} filing documents"
            ]

    except Exception as e:
        logger.error(f"Filing analysis failed for {ticker}: {e}", exc_info=True)
        result["status"] = "error"
        result["error"] = str(e)

    return result
