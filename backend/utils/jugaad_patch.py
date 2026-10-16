"""
Monkey-patch for jugaad-data to fix Windows compatibility issues.

Issue: jugaad-data cache filenames contain ':' from timestamps (e.g., "2024-01-01 10:30:45")
which causes [Errno 22] Invalid argument on Windows.

Solution: Patch NSEHistory to sanitize cache filenames by replacing ':' with '-'.
"""

import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

_patched = False


def apply_jugaad_patch():
    """
    Apply Windows compatibility patch to jugaad-data.

    Safe to call multiple times - only patches once.
    """
    global _patched

    if _patched:
        return

    try:
        # Check if jugaad-data is installed
        try:
            from jugaad_data.nse import NSEHistory
        except ImportError:
            logger.warning("jugaad-data not installed, skipping patch")
            return

        # Only patch on Windows
        if sys.platform != "win32":
            logger.info("Not on Windows, skipping jugaad-data patch")
            _patched = True
            return

        logger.info("Applying Windows compatibility patch to jugaad-data")

        # Patch the _cache_file_name method to sanitize filenames
        original_cache_file_name = NSEHistory._cache_file_name

        def patched_cache_file_name(self, dt):
            """Sanitized cache filename for Windows."""
            original_name = original_cache_file_name(self, dt)
            # Replace colons with hyphens to make it Windows-compatible
            sanitized = original_name.replace(':', '-')
            return sanitized

        NSEHistory._cache_file_name = patched_cache_file_name

        logger.info("jugaad-data patch applied successfully")
        _patched = True

    except Exception as e:
        logger.error(f"Failed to apply jugaad-data patch: {e}", exc_info=True)
        # Don't raise - allow code to continue even if patch fails
