import asyncio
import datetime
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import desc

import models
from database import engine, get_db, SessionLocal
from config import settings
from twitch_client import TwitchClient
from vision import analyze_frame

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Create database tables
models.Base.metadata.create_all(bind=engine)

# Initialize Twitch Client
twitch_client = TwitchClient(settings.TWITCH_CLIENT_ID, settings.TWITCH_CLIENT_SECRET)

# Global state for background task
is_running = True
current_camera_state = "NO_CAM"
afk_suspect_count = 0        # How many consecutive AFK signals we've seen
AFK_CONFIRM_THRESHOLD = 3   # Need this many consecutive AFK signals to officially start AFK

async def background_poller():
    """Background task to poll Twitch and Check AFK status."""
    logger.info("Starting background poller...")
    while is_running:
        sleep_interval = settings.POLL_INTERVAL_SECONDS
        try:
            db = SessionLocal()
            channel = settings.TWITCH_CHANNEL
            
            # 1. Check if stream is online
            stream_info = twitch_client.check_stream_online(channel)
            
            if not stream_info:
                logger.info(f"Stream {channel} is offline. Sleeping...")
                # Ensure active session is closed if there was one
                active_session = db.query(models.StreamSession).filter(
                    models.StreamSession.twitch_channel == channel,
                    models.StreamSession.is_active == True
                ).first()
                
                if active_session:
                    active_session.is_active = False
                    active_session.ended_at = datetime.datetime.utcnow()
                    # Also close any open AFK event
                    open_afk = db.query(models.AFKEvent).filter(
                        models.AFKEvent.session_id == active_session.id,
                        models.AFKEvent.ended_at == None
                    ).first()
                    if open_afk:
                        open_afk.ended_at = datetime.datetime.utcnow()
                        open_afk.duration_seconds = (open_afk.ended_at - open_afk.started_at).total_seconds()
                    db.commit()
            else:
                logger.info(f"Stream {channel} is online. Checking AFK...")
                # Ensure we have an active session for this stream
                active_session = db.query(models.StreamSession).filter(
                    models.StreamSession.twitch_channel == channel,
                    models.StreamSession.is_active == True
                ).first()
                
                if not active_session:
                    # New stream started
                    active_session = models.StreamSession(twitch_channel=channel, twitch_user_id=stream_info['user_id'])
                    db.add(active_session)
                    db.commit()
                    db.refresh(active_session)
                
                # 2. Check Camera State using vision
                camera_state = analyze_frame(channel)
                global current_camera_state
                current_camera_state = camera_state
                
                # Check for an ongoing AFK event
                open_afk = db.query(models.AFKEvent).filter(
                    models.AFKEvent.session_id == active_session.id,
                    models.AFKEvent.ended_at == None
                ).first()
                
                if camera_state == "AFK":
                    global afk_suspect_count
                    afk_suspect_count += 1
                    sleep_interval = 1  # 1s rapid checks during confirmation and AFK
                    
                    if afk_suspect_count >= AFK_CONFIRM_THRESHOLD:
                        # Confirmed AFK
                        if not open_afk:
                            logger.info(f"AFK confirmed for {channel} after {afk_suspect_count} checks!")
                            new_afk = models.AFKEvent(session_id=active_session.id)
                            db.add(new_afk)
                            db.commit()
                        else:
                            logger.info(f"Still AFK for {channel} (check #{afk_suspect_count})...")
                            open_afk.duration_seconds = (datetime.datetime.utcnow() - open_afk.started_at).total_seconds()
                            db.commit()
                    else:
                        logger.info(f"Possible AFK for {channel}: {afk_suspect_count}/{AFK_CONFIRM_THRESHOLD} checks...")
                        
                elif camera_state == "PRESENT":
                    afk_suspect_count = 0  # Reset immediately on any presence
                    if open_afk:
                        logger.info(f"AFK ended for {channel} (Present)!")
                        open_afk.ended_at = datetime.datetime.utcnow()
                        open_afk.duration_seconds = (open_afk.ended_at - open_afk.started_at).total_seconds()
                        db.commit()
                elif camera_state == "NO_CAM":
                    afk_suspect_count = 0  # Reset on no-cam too
                    if open_afk:
                        logger.info(f"AFK ended for {channel} (No Cam)!")
                        open_afk.ended_at = datetime.datetime.utcnow()
                        open_afk.duration_seconds = (open_afk.ended_at - open_afk.started_at).total_seconds()
                        db.commit()
                    logger.info(f"No Camera found for {channel}.")
            
            db.close()
            
        except Exception as e:
            logger.error(f"Error in background poller: {e}")
            
        # Sleep for the dynamic polling interval
        await asyncio.sleep(sleep_interval)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    task = asyncio.create_task(background_poller())
    yield
    # Shutdown
    global is_running
    is_running = False
    task.cancel()
    
app = FastAPI(lifespan=lifespan)

# API Endpoints
@app.get("/api/status")
def get_status(db: Session = Depends(get_db)):
    """Returns the current online status and active AFK status if any."""
    channel = settings.TWITCH_CHANNEL
    active_session = db.query(models.StreamSession).filter(
                    models.StreamSession.twitch_channel == channel,
                    models.StreamSession.is_active == True
                ).first()
    
    if not active_session:
        return {"online": False, "state": "OFFLINE", "is_afk": False, "current_afk_duration": 0}
        
    open_afk = db.query(models.AFKEvent).filter(
                    models.AFKEvent.session_id == active_session.id,
                    models.AFKEvent.ended_at == None
                ).first()
                
    if open_afk:
        duration = int((datetime.datetime.utcnow() - open_afk.started_at).total_seconds())
        return {"online": True, "state": "AFK", "is_afk": True, "current_afk_duration": duration}
    
    return {"online": True, "state": current_camera_state, "is_afk": False, "current_afk_duration": 0}

@app.get("/api/stats")
def get_stats(db: Session = Depends(get_db)):
    """Returns overall stats for the dashboard."""
    channel = settings.TWITCH_CHANNEL
    
    # Last stream calculation
    last_session = db.query(models.StreamSession).filter(
        models.StreamSession.twitch_channel == channel
    ).order_by(desc(models.StreamSession.started_at)).first()
    
    last_stream_time = None
    if last_session:
        last_stream_time = last_session.started_at.isoformat() + "Z"
        
    # AFK this stream
    afk_this_stream = 0
    if last_session and last_session.is_active:
         events = db.query(models.AFKEvent).filter(models.AFKEvent.session_id == last_session.id).all()
         for e in events:
             if e.ended_at:
                 afk_this_stream += e.duration_seconds
             else:
                 afk_this_stream += (datetime.datetime.utcnow() - e.started_at).total_seconds()
                 
    # AFK this month (simplified tracking last 30 days)
    thirty_days_ago = datetime.datetime.utcnow() - datetime.timedelta(days=30)
    recent_sessions = db.query(models.StreamSession).filter(
        models.StreamSession.twitch_channel == channel,
        models.StreamSession.started_at >= thirty_days_ago
    ).all()
    
    afk_this_month = 0
    recent_session_ids = [s.id for s in recent_sessions]
    if recent_session_ids:
        events = db.query(models.AFKEvent).filter(models.AFKEvent.session_id.in_(recent_session_ids)).all()
        for e in events:
            if e.ended_at:
                afk_this_month += e.duration_seconds
            else:
                 afk_this_month += (datetime.datetime.utcnow() - e.started_at).total_seconds()
                 
    return {
        "channel": channel,
        "last_stream": last_stream_time,
        "afk_this_stream": int(afk_this_stream),
        "afk_this_month": int(afk_this_month)
    }

# Mount static files for the frontend AFTER API routes
import os
os.makedirs("static", exist_ok=True)
app.mount("/", StaticFiles(directory="static", html=True), name="static")
