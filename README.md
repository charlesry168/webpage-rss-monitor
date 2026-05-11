# Webpage RSS Monitor

> Turn any webpage into an RSS feed. Get notified when content changes.

[![CI](https://github.com/carlrygart/webpage-rss-monitor/actions/workflows/ci.yml/badge.svg)](https://github.com/carlrygart/webpage-rss-monitor/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## What it does

Monitor any webpage for changes and expose those changes as an RSS feed you can subscribe to in any feed reader (Feedly, NetNewsWire, etc.) or automate with tools like Zapier or n8n.

**Use cases:**
- Monitor competitor pricing pages
- Track job boards for new listings
- Watch government or regulatory pages
- Get notified when a product comes back in stock
- Follow changelog/release pages for tools you use

## Quick Start

```bash
# Clone and start
git clone https://github.com/carlrygart/webpage-rss-monitor.git
cd webpage-rss-monitor
docker-compose up
```

The API is now running at `http://localhost:8000`.

### Add a monitor

```bash
curl -X POST http://localhost:8000/monitors \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/pricing", "name": "Example Pricing", "check_interval": 3600}'
```

### Get the RSS feed

```
http://localhost:8000/feed/{monitor_id}.xml
```

Subscribe to this URL in any RSS reader.

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/monitors` | Add a new URL to monitor |
| `GET` | `/monitors` | List all monitors |
| `GET` | `/monitors/{id}` | Get a specific monitor |
| `PATCH` | `/monitors/{id}` | Update monitor settings |
| `DELETE` | `/monitors/{id}` | Remove a monitor |
| `GET` | `/feed/{id}.xml` | Get RSS feed for a monitor |
| `POST` | `/monitors/{id}/check` | Trigger immediate check |
| `GET` | `/monitors/{id}/snapshots` | List change history |
| `GET` | `/health` | Health check |

### Create Monitor — Request Body

```json
{
  "url": "https://example.com/page",
  "name": "My Monitor",
  "check_interval": 3600,
  "css_selector": ".main-content"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `url` | string | ✅ | Page URL to monitor |
| `name` | string | ✅ | Human-readable name |
| `check_interval` | int | | Seconds between checks (default: 3600) |
| `css_selector` | string | | CSS selector to monitor only part of page |

## Pricing

| Plan | Price | Monitors | Check Interval |
|------|-------|----------|----------------|
| **Free** | $0/mo | 3 URLs | 24h minimum |
| **Pro** | $9/mo | 50 URLs | 1h minimum |
| **Business** | $29/mo | 500 URLs | 15m minimum |

[👉 Sign up at webpage-monitor.dev](#) *(coming soon)*

## Self-Hosting

### Docker Compose (recommended)

```bash
docker-compose up -d
```

Data is persisted in a Docker volume.

### Local development

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///./monitors.db` | Database connection string |
| `PORT` | `8000` | API port |

## Running Tests

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  RSS Reader │────▶│  FastAPI App │────▶│  SQLite DB  │
└─────────────┘     └──────────────┘     └─────────────┘
                           │
                    ┌──────────────┐
                    │  APScheduler │
                    │  (polling)   │
                    └──────────────┘
                           │
                    ┌──────────────┐
                    │  httpx +     │
                    │  BeautifulSoup│
                    └──────────────┘
```

- **FastAPI** — async REST API
- **SQLite** — zero-config storage (swap for Postgres in production)
- **APScheduler** — in-process cron for URL polling
- **httpx** — async HTTP client for fetching pages
- **BeautifulSoup** — HTML parsing and text extraction

## Roadmap

- [ ] Email notifications on change
- [ ] Webhook support (POST to your endpoint)
- [ ] Postgres support for production deployments
- [ ] Web UI for managing monitors
- [ ] Hosted SaaS version
- [ ] Stripe billing integration

## License

MIT — see [LICENSE](LICENSE)

---

Built by [Carl Rygart](https://github.com/carlrygart)
