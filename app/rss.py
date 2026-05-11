from datetime import datetime
from typing import List
from app.database import Monitor, Snapshot


def build_rss_feed(monitor: Monitor, snapshots: List[Snapshot]) -> str:
    """Build an RSS 2.0 XML feed for a monitor."""
    pub_date = monitor.last_changed or monitor.created_at
    pub_date_str = pub_date.strftime("%a, %d %b %Y %H:%M:%S +0000") if pub_date else ""

    items_xml = ""
    for snap in snapshots[:20]:
        title = f"Change detected on {monitor.name}"
        link = monitor.url
        description = _escape_xml(snap.diff_summary or "Content changed.")
        pub = snap.captured_at.strftime("%a, %d %b %Y %H:%M:%S +0000")
        guid = snap.id
        items_xml += f"""
    <item>
      <title>{_escape_xml(title)}</title>
      <link>{_escape_xml(link)}</link>
      <description><![CDATA[<pre>{snap.diff_summary or ""}</pre>]]></description>
      <pubDate>{pub}</pubDate>
      <guid isPermaLink="false">{guid}</guid>
    </item>"""

    feed = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>Monitor: {_escape_xml(monitor.name)}</title>
    <link>{_escape_xml(monitor.url)}</link>
    <description>Change feed for {_escape_xml(monitor.url)}</description>
    <lastBuildDate>{pub_date_str}</lastBuildDate>
    <atom:link href="" rel="self" type="application/rss+xml"/>{items_xml}
  </channel>
</rss>"""
    return feed


def _escape_xml(text: str) -> str:
    if not text:
        return ""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )
