import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import patch, AsyncMock, MagicMock

TEST_DB_URL = "sqlite:///./test_monitors.db"


@pytest.fixture(scope="module")
def db_engine():
    engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
    return engine


@pytest.fixture(scope="module")
def client(db_engine):
    from app.database import Base, get_db

    Base.metadata.create_all(bind=db_engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    mock_scheduler = MagicMock()
    mock_scheduler.get_job.return_value = None

    with patch("app.scheduler.scheduler", mock_scheduler):
        from app.main import app
        app.dependency_overrides[get_db] = override_get_db

        from fastapi.testclient import TestClient
        with patch("app.main.scheduler", mock_scheduler):
            with TestClient(app) as c:
                yield c

    Base.metadata.drop_all(bind=db_engine)


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


@patch("app.main.check_monitor", new_callable=AsyncMock)
@patch("app.main.schedule_monitor")
def test_create_and_get_monitor(mock_schedule, mock_check, client):
    r = client.post("/monitors", json={
        "url": "https://example.com",
        "name": "Example Monitor",
        "check_interval": 600,
    })
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "Example Monitor"
    assert "example.com" in data["url"]
    assert data["check_interval"] == 600
    monitor_id = data["id"]

    r2 = client.get(f"/monitors/{monitor_id}")
    assert r2.status_code == 200
    assert r2.json()["id"] == monitor_id


def test_get_monitor_not_found(client):
    r = client.get("/monitors/nonexistent-id")
    assert r.status_code == 404


@patch("app.main.check_monitor", new_callable=AsyncMock)
@patch("app.main.schedule_monitor")
def test_list_monitors(mock_schedule, mock_check, client):
    r = client.get("/monitors")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


@patch("app.main.check_monitor", new_callable=AsyncMock)
@patch("app.main.schedule_monitor")
def test_get_rss_feed(mock_schedule, mock_check, client):
    create_r = client.post("/monitors", json={"url": "https://rsstest.com", "name": "RSS Test"})
    monitor_id = create_r.json()["id"]

    r = client.get(f"/feed/{monitor_id}.xml")
    assert r.status_code == 200
    assert "application/rss+xml" in r.headers["content-type"]
    assert "<?xml" in r.text
    assert "RSS Test" in r.text


def test_rss_escape_xml():
    from app.rss import _escape_xml
    assert _escape_xml("a & b") == "a &amp; b"
    assert _escape_xml("<script>") == "&lt;script&gt;"
    assert _escape_xml('"quoted"') == "&quot;quoted&quot;"


def test_compute_diff_changed():
    from app.scraper import compute_diff
    old = "line1\nline2\nline3"
    new = "line1\nline2 changed\nline3\nline4"
    diff = compute_diff(old, new)
    assert "+" in diff


def test_compute_diff_no_change():
    from app.scraper import compute_diff
    content = "same content\nno changes here"
    diff = compute_diff(content, content)
    assert "No changes" in diff


def test_rss_build_feed_with_snapshots():
    from app.rss import build_rss_feed
    from app.database import Monitor, Snapshot
    from datetime import datetime

    monitor = Monitor()
    monitor.id = "test-id"
    monitor.name = "Test Monitor"
    monitor.url = "https://example.com"
    monitor.created_at = datetime(2026, 1, 1)
    monitor.last_changed = datetime(2026, 1, 2)

    snap = Snapshot()
    snap.id = "snap-id-1"
    snap.monitor_id = "test-id"
    snap.captured_at = datetime(2026, 1, 2)
    snap.content_hash = "abc123"
    snap.content = "hello world"
    snap.diff_summary = "+1 lines added\n+new line"

    feed = build_rss_feed(monitor, [snap])
    assert "<?xml" in feed
    assert "Test Monitor" in feed
    assert "https://example.com" in feed
    assert "snap-id-1" in feed


def test_rss_build_empty_feed():
    from app.rss import build_rss_feed
    from app.database import Monitor
    from datetime import datetime

    monitor = Monitor()
    monitor.id = "empty-id"
    monitor.name = "Empty Monitor"
    monitor.url = "https://empty.com"
    monitor.created_at = datetime(2026, 1, 1)
    monitor.last_changed = None

    feed = build_rss_feed(monitor, [])
    assert "<?xml" in feed
    assert "Empty Monitor" in feed
