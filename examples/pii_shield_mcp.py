"""
PII Shield MCP Server:
Gives Claude a small regex-based tool for masking emails and phone numbers.
For fuller detection, use the pii-masker-ai package.
"""

from easy_mcp import EasyMCP
import re

mcp = EasyMCP("pii-shield-server", version="1.0.0", description="Data privacy tools for Claude")

EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
PHONE_PATTERN = re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}\b")


@mcp.tool()
def sanitize_prompt(text: str) -> str:
    """Sanitize sensitive emails and phone numbers from user text before storage.
    
    Args:
        text: The raw text that might contain sensitive personal data
    """
    cleaned = EMAIL_PATTERN.sub("[REDACTED_EMAIL]", text)
    cleaned = PHONE_PATTERN.sub("[REDACTED_PHONE]", cleaned)
    return cleaned


if __name__ == "__main__":
    mcp.run()
