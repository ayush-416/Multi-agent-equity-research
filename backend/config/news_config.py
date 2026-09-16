"""
News source credibility configuration for News Sentinel agent.

Categorizes news sources into trusted and unverified tiers for
story confirmation logic.
"""

# Trusted sources - high credibility, established business/financial news outlets
# Stories are marked "confirmed" when reported by ≥2 independent trusted sources
TRUSTED_SOURCES = {
    # Major Indian business newspapers
    "Economic Times",
    "The Economic Times",
    "ET Now",
    "LiveMint",
    "Mint",
    "Business Standard",
    "Business Today",
    "Financial Express",

    # Major international financial news
    "Reuters",
    "Bloomberg",
    "The Wall Street Journal",
    "Financial Times",

    # Indian market-focused platforms
    "Moneycontrol",
    "MoneyControl",
    "Investing.com",

    # Company investor relations (primary sources)
    "BSE",
    "NSE",
    "SEBI",

    # Major Indian newspapers with business coverage
    "The Hindu BusinessLine",
    "The Times of India",
    "Hindustan Times",
    "Indian Express",
}

# Unverified sources - all sources not in the trusted list
# These may include: blogs, aggregators, smaller regional outlets, social media
# Stories from only unverified sources are marked "unconfirmed"

# Normalization: convert source names to lowercase for case-insensitive matching
TRUSTED_SOURCES_NORMALIZED = {source.lower() for source in TRUSTED_SOURCES}


def is_trusted_source(source_name: str) -> bool:
    """
    Check if a source is in the trusted list.

    Args:
        source_name: Name of the news source

    Returns:
        True if source is trusted, False otherwise
    """
    if not source_name:
        return False

    source_normalized = source_name.lower().strip()

    # Exact match
    if source_normalized in TRUSTED_SOURCES_NORMALIZED:
        return True

    # Partial match (e.g., "Economic Times - Markets" contains "economic times")
    for trusted in TRUSTED_SOURCES_NORMALIZED:
        if trusted in source_normalized or source_normalized in trusted:
            return True

    return False


def get_source_tier(source_name: str) -> str:
    """
    Get the credibility tier of a source.

    Args:
        source_name: Name of the news source

    Returns:
        "trusted" or "unverified"
    """
    return "trusted" if is_trusted_source(source_name) else "unverified"
