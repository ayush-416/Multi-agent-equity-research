"""
Email alerting system for FinSight AI stock tracking.

Sends alerts when confirmed negative news is detected for tracked stocks.
"""
import os
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


def send_alert_email(
    ticker: str,
    company_name: str,
    story_groups: List[Dict[str, Any]]
) -> bool:
    """
    Send alert email for confirmed negative news.

    Args:
        ticker: Stock ticker (e.g., "RELIANCE")
        company_name: Full company name
        story_groups: List of confirmed negative story groups

    Returns:
        True if email sent successfully, False otherwise
    """
    try:
        import resend
    except ImportError:
        logger.error("resend package not installed - cannot send alerts")
        return False

    # Get Resend API key
    api_key = os.getenv("RESEND_API_KEY")
    if not api_key:
        logger.error("RESEND_API_KEY not set in environment - cannot send alerts")
        return False

    resend.api_key = api_key

    # Build email content
    story_html = ""
    for i, story in enumerate(story_groups, 1):
        summary = story.get("summary", "No summary available")
        sources = story.get("trusted_sources", story.get("sources", []))
        source_list = ", ".join(sources[:5])  # Max 5 sources
        confidence = story.get("confidence_score", 0)

        story_html += f"""
        <div style="margin-bottom: 20px; padding: 15px; background-color: #fff3cd; border-left: 4px solid #ff9800;">
            <h3 style="margin-top: 0; color: #d32f2f;">Story {i}</h3>
            <p><strong>Summary:</strong> {summary}</p>
            <p><strong>Sources:</strong> {source_list}</p>
            <p><strong>Confidence:</strong> {confidence}%</p>
        </div>
        """

    html_content = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background-color: #d32f2f; color: white; padding: 20px; text-align: center; }}
            .content {{ padding: 20px; background-color: #f5f5f5; }}
            .footer {{ padding: 10px; text-align: center; font-size: 12px; color: #666; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>⚠️ FinSight Alert</h1>
            </div>
            <div class="content">
                <h2>Negative Confirmed News Detected</h2>
                <p><strong>Stock:</strong> {ticker} ({company_name})</p>
                <p><strong>Alert Type:</strong> Confirmed negative news from multiple trusted sources</p>
                <hr>
                <h3>Story Details:</h3>
                {story_html}
                <hr>
                <p style="color: #d32f2f;"><strong>⚠️ Action Recommended:</strong> Consider reviewing your position in {ticker}.</p>
                <p>This alert was triggered because multiple trusted news sources have reported negative developments.</p>
            </div>
            <div class="footer">
                <p>Sent by FinSight AI Stock Tracker</p>
                <p>This is an automated alert based on news sentiment analysis.</p>
            </div>
        </div>
    </body>
    </html>
    """

    # Prepare email parameters
    params = {
        "from": "FinSight AI <onboarding@resend.dev>",
        "to": ["ayush.achin2023@vitstudent.ac.in"],
        "subject": f"⚠️ FinSight Alert: Negative news on {ticker}",
        "html": html_content,
    }

    try:
        email = resend.Emails.send(params)
        logger.info(f"Alert email sent for {ticker}: {email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send alert email for {ticker}: {e}")
        return False


def should_send_alert(
    story_groups: List[Dict[str, Any]],
    seen_story_ids: List[str]
) -> tuple[bool, List[Dict[str, Any]], List[str]]:
    """
    Determine if an alert should be sent based on story groups.

    Only alerts on NEW confirmed negative stories.

    Args:
        story_groups: List of story groups from news sentinel
        seen_story_ids: List of story IDs already seen

    Returns:
        Tuple of (should_alert, new_confirmed_negative_stories, all_new_story_ids)
    """
    new_confirmed_negative = []
    all_new_ids = []

    for story in story_groups:
        # Generate story ID from summary (simple hash)
        story_summary = story.get("summary", "")
        story_id = str(hash(story_summary))
        all_new_ids.append(story_id)

        # Check if this is a new story
        if story_id in seen_story_ids:
            continue

        # Check if it's confirmed (≥2 trusted sources)
        is_confirmed = story.get("confirmed", False)

        # Check if sentiment is negative
        sentiment = story.get("sentiment", "").lower()
        is_negative = sentiment in ["negative", "bearish"]

        # Alert only on NEW + CONFIRMED + NEGATIVE
        if is_confirmed and is_negative:
            new_confirmed_negative.append(story)

    should_alert = len(new_confirmed_negative) > 0

    return should_alert, new_confirmed_negative, all_new_ids
