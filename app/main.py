import logging
from contextlib import asynccontextmanager
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.responses import Response
from pydantic import BaseModel, HttpUrl
from sqlalchemy.orm import Session
from datetime import datetime

from app.database import init_db, get_db, Monitor, Snapshot, SessionLocal
from app.rss import build_rss_feed
from app.scheduler import scheduler, schedule_monitor, unschedule_monitor, check_monitor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    scheduler.start()
    db = SessionLocal()
    try:
        monitors = db.query(Monitor).filter(Monitor.is_active == True).all()
        for m in monitors:
            schedule_monitor(m.id, m.check_interval)
        logger.info(f"Scheduled {len(monitors)} monitors on startup")
    finally:
        db.close()
    yield
    scheduler.shutdown()


app = FastAPI(
    title="Webpage RSS Monitor",
    description="Monitor webpages for changes and get RSS feeds",
    version="1.0.0",
    lifespan=lifespan,
)


# --- Schemas ---

class MonitorCreate(BaseModel):
    url: HttpUrl
    name: str
    check_interval: int = 3600
    css_selector: Optional[str] = None
    api_key: Optional[str] = None
    webhook_url: Optional[str] = None
    webhook_secret: Optional[str] = None


class MonitorResponse(BaseModel):
    id: str
    url: str
    name: str
    check_interval: int
    created_at: datetime
    last_checked: Optional[datetime]
    last_changed: Optional[datetime]
    is_active: bool
    css_selector: Optional[str]
    webhook_url: Optional[str]

    class Config:
        from_attributes = True


class MonitorUpdate(BaseModel):
    name: Optional[str] = None
    check_interval: Optional[int] = None
    css_selector: Optional[str] = None
    is_active: Optional[bool] = None
    webhook_url: Optional[str] = None
    webhook_secret: Optional[str] = None


# --- Routes ---

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/monitors", response_model=MonitorResponse, status_code=201)
async def create_monitor(payload: MonitorCreate, db: Session = Depends(get_db)):
    monitor = Monitor(
        url=str(payload.url),
        name=payload.name,
        check_interval=payload.check_interval,
        css_selector=payload.css_selector,
        api_key=payload.api_key,
        webhook_url=payload.webhook_url,
        webhook_secret=payload.webhook_secret,
    )
    db.add(monitor)
    db.commit()
    db.refresh(monitor)

    schedule_monitor(monitor.id, monitor.check_interval)
    # Do an immediate first check
    await check_monitor(monitor.id)

    db.refresh(monitor)
    return monitor


@app.get("/monitors", response_model=List[MonitorResponse])
def list_monitors(db: Session = Depends(get_db)):
    return db.query(Monitor).order_by(Monitor.created_at.desc()).all()


@app.get("/monitors/{monitor_id}", response_model=MonitorResponse)
def get_monitor(monitor_id: str, db: Session = Depends(get_db)):
    monitor = db.query(Monitor).filter(Monitor.id == monitor_id).first()
    if not monitor:
        raise HTTPException(status_code=404, detail="Monitor not found")
    return monitor


@app.patch("/monitors/{monitor_id}", response_model=MonitorResponse)
def update_monitor(monitor_id: str, payload: MonitorUpdate, db: Session = Depends(get_db)):
    monitor = db.query(Monitor).filter(Monitor.id == monitor_id).first()
    if not monitor:
        raise HTTPException(status_code=404, detail="Monitor not found")

    if payload.name is not None:
        monitor.name = payload.name
    if payload.check_interval is not None:
        monitor.check_interval = payload.check_interval
        schedule_monitor(monitor.id, monitor.check_interval)
    if payload.css_selector is not None:
        monitor.css_selector = payload.css_selector
    if payload.is_active is not None:
        monitor.is_active = payload.is_active
        if not payload.is_active:
            unschedule_monitor(monitor.id)
        else:
            schedule_monitor(monitor.id, monitor.check_interval)
    if payload.webhook_url is not None:
        monitor.webhook_url = payload.webhook_url
    if payload.webhook_secret is not None:
        monitor.webhook_secret = payload.webhook_secret

    db.commit()
    db.refresh(monitor)
    return monitor


@app.delete("/monitors/{monitor_id}", status_code=204)
def delete_monitor(monitor_id: str, db: Session = Depends(get_db)):
    monitor = db.query(Monitor).filter(Monitor.id == monitor_id).first()
    if not monitor:
        raise HTTPException(status_code=404, detail="Monitor not found")

    unschedule_monitor(monitor_id)
    db.query(Snapshot).filter(Snapshot.monitor_id == monitor_id).delete()
    db.delete(monitor)
    db.commit()


@app.get("/feed/{monitor_id}.xml")
def get_feed(monitor_id: str, db: Session = Depends(get_db)):
    monitor = db.query(Monitor).filter(Monitor.id == monitor_id).first()
    if not monitor:
        raise HTTPException(status_code=404, detail="Monitor not found")

    snapshots = (
        db.query(Snapshot)
        .filter(Snapshot.monitor_id == monitor_id)
        .order_by(Snapshot.captured_at.desc())
        .limit(20)
        .all()
    )

    rss_xml = build_rss_feed(monitor, snapshots)
    return Response(content=rss_xml, media_type="application/rss+xml")


@app.post("/monitors/{monitor_id}/check")
async def trigger_check(monitor_id: str, db: Session = Depends(get_db)):
    monitor = db.query(Monitor).filter(Monitor.id == monitor_id).first()
    if not monitor:
        raise HTTPException(status_code=404, detail="Monitor not found")
    await check_monitor(monitor_id)
    db.refresh(monitor)
    return {"status": "checked", "last_checked": monitor.last_checked}


@app.get("/monitors/{monitor_id}/snapshots")
def list_snapshots(monitor_id: str, limit: int = 10, db: Session = Depends(get_db)):
    monitor = db.query(Monitor).filter(Monitor.id == monitor_id).first()
    if not monitor:
        raise HTTPException(status_code=404, detail="Monitor not found")

    snaps = (
        db.query(Snapshot)
        .filter(Snapshot.monitor_id == monitor_id)
        .order_by(Snapshot.captured_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": s.id,
            "captured_at": s.captured_at,
            "content_hash": s.content_hash,
            "diff_summary": s.diff_summary,
        }
        for s in snaps
    ]
