import hashlib
import difflib
import httpx
from bs4 import BeautifulSoup
from typing import Optional, Tuple


async def fetch_page(url: str, css_selector: Optional[str] = None) -> Tuple[str, str]:
    """Fetch page content and return (text_content, content_hash)."""
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; WebpageRSSMonitor/1.0; +https://github.com/carlrygart/webpage-rss-monitor)"
    }
    async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
        response = await client.get(url, headers=headers)
        response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    for tag in soup(["script", "style", "meta", "noscript"]):
        tag.decompose()

    if css_selector:
        elements = soup.select(css_selector)
        text = "\n".join(el.get_text(separator=" ", strip=True) for el in elements)
    else:
        text = soup.get_text(separator="\n", strip=True)

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    clean_text = "\n".join(lines)

    content_hash = hashlib.sha256(clean_text.encode()).hexdigest()
    return clean_text, content_hash


def compute_diff(old_content: str, new_content: str) -> str:
    """Return a human-readable diff summary."""
    old_lines = old_content.splitlines()
    new_lines = new_content.splitlines()
    diff = list(difflib.unified_diff(old_lines, new_lines, lineterm="", n=2))
    if not diff:
        return "No changes detected."
    added = sum(1 for l in diff if l.startswith("+") and not l.startswith("+++"))
    removed = sum(1 for l in diff if l.startswith("-") and not l.startswith("---"))
    summary_lines = [f"+{added} lines added, -{removed} lines removed"]
    summary_lines += diff[:50]
    return "\n".join(summary_lines)
