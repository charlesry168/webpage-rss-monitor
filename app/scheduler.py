import logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.orm import Session
from app.database import SessionLocal, Monitor, Snapshot
from app.scraper import fetch_page, compute_diff

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()


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
            monitor.last_changed = datetime.utcnow()
            logger.info(f"Change detected for monitor {monitor_id}")

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
