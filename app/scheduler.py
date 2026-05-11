import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import httpx
from sqlalchemy.orm import Session
from app.database import SessionLocal, Monitor, Snapshot
from app.scraper import fetch_page, compute_diff

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()


async def fire_webhook(monitor: Monitor, snapshot: "Snapshot", diff_summary: str):
    if not monitor.webhook_url:
        return
    payload = {
        "event": "change_detected",
        "monitor_id": monitor.id,
        "monitor_name": monitor.name,
        "url": monitor.url,
        "detected_at": datetime.now(timezone.utc).isoformat(),
        "diff_summary": diff_summary,
        "snapshot_id": snapshot.id,
    }
    body = json.dumps(payload, default=str).encode()
    req_headers = {"Content-Type": "application/json", "User-Agent": "webpage-rss-monitor/1.0"}
    if monitor.webhook_secret:
        sig = hmac.new(monitor.webhook_secret.encode(), body, hashlib.sha256).hexdigest()
        req_headers["X-Webhook-Signature"] = f"sha256={sig}"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(monitor.webhook_url, content=body, headers=req_headers)
            logger.info(f"Webhook fired for {monitor.id}: HTTP {resp.status_code}")
    except Exception as exc:
        logger.warning(f"Webhook failed for {monitor.id}: {exc}")


async def check_monitor(monitor_id: str):
    db: Session = SessionLocal()
    try:
        monitor = db.query(Monitor).filter(Monitor.id == monitor_id, Monitor.is_active == True).first()
        if not monitor:
            return

        logger.info(f"Checking monitor {monitor_id}: {monitor.url}")
        new_content, new_hash = await fetch_page(monitor.url, monitor.css_selector)

        last_snap = (
            db.query(Snapshot)
            .filter(Snapshot.monitor_id == monitor_id)
            .order_by(Snapshot.captured_at.desc())
            .first()
        )

        monitor.last_checked = datetime.utcnow()

        if last_snap is None or last_snap.content_hash != new_hash:
            diff_summary = compute_diff(last_snap.content if last_snap else "", new_content)
            snap = Snapshot(
                monitor_id=monitor_id,
                content_hash=new_hash,
                content=new_content,
                diff_summary=diff_summary,
            )
            db.add(snap)
            db.flush()
            monitor.last_changed = datetime.utcnow()
            logger.info(f"Change detected for monitor {monitor_id}")
            db.commit()
            await fire_webhook(monitor, snap, diff_summary)
            return

        db.commit()
    except Exception as e:
        logger.error(f"Error checking monitor {monitor_id}: {e}")
        db.rollback()
    finally:
        db.close()


def schedule_monitor(monitor_id: str, interval_seconds: int):
    job_id = f"monitor_{monitor_id}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
    scheduler.add_job(
        check_monitor,
        "interval",
        seconds=interval_seconds,
        id=job_id,
        args=[monitor_id],
        replace_existing=True,
        max_instances=1,
    )


def unschedule_monitor(monitor_id: str):
    job_id = f"monitor_{monitor_id}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
