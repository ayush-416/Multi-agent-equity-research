

def _try_scraper_fallback(ticker: str, company_name: str) -> Optional[Dict[str, Any]]:
    """
    Try to get ratios from scraper when yfinance fails.

    Args:
        ticker: Stock ticker
        company_name: Company name

    Returns:
        Complete ratio_cruncher result dict or None
    """
    try:
        from backend.tools.financial_tools import get_scraper_data
        from backend.utils.scraper_helpers import derive_ratios_from_scraper

        logger.info(f"Attempting scraper fallback for {ticker}")
        scraper_data = get_scraper_data(ticker)

        if not scraper_data:
            logger.warning(f"No scraper data available for {ticker}")
            return None

        # Derive ratios from scraper
        derived = derive_ratios_from_scraper(scraper_data)

        if not derived.get("ratios"):
            logger.warning(f"Could not derive ratios from scraper data for {ticker}")
            return None

        ratios = derived["ratios"]
        currency = derived.get("currency", "INR")

        logger.info(f"Derived {len(ratios)} ratios from scraper (currency: {currency})")

        # Check for currency mismatch warning
        if currency != "INR":
            logger.warning(f"Ratios are in {currency}, not INR - may not align with Indian stock prices")

        result = {
            "status": "success",
            "ticker": ticker,
            "company_name": company_name,
            "sector": "",  # Not available from scraper
            "ratios": ratios,
            "sector_benchmarks": {},  # Will be empty without sector
            "strengths": [],
            "concerns": [],
            "valuation_summary": "",
            "error": None,
            "source": "scraper",
            "currency": currency
        }

        # Analyze strengths and concerns
        strengths, concerns = _analyze_ratios(ratios, {})
        result["strengths"] = strengths
        result["concerns"] = concerns

        # Generate valuation summary
        result["valuation_summary"] = _generate_valuation_summary(
            ratios, {}, company_name
        )

        return result

    except Exception as e:
        logger.error(f"Scraper fallback failed for {ticker}: {e}", exc_info=True)
        return None
