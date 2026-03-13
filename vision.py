import cv2
import streamlink
import numpy as np
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# Initialize OpenCV Face Detector (Haar Cascade)
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

def grab_stream_frame(channel_name: str) -> Optional[np.ndarray]:
    """
    Uses streamlink to find the best quality stream for the channel,
    opens it with OpenCV, grabs a single frame, and returns it.
    """
    url = f"https://twitch.tv/{channel_name}"
    try:
        streams = streamlink.streams(url)
        if not streams:
            logger.warning(f"No streams found for {url}")
            return None
        
        # Get the highest quality stream URL
        best_stream = streams.get("best", streams.get("1080p60", streams.get("1080p", None)))
        if not best_stream:
            logger.warning(f"Could not determine best stream quality for {url}")
            return None
            
        stream_url = best_stream.url
        
        # Open the stream with OpenCV
        cap = cv2.VideoCapture(stream_url)
        if not cap.isOpened():
            logger.error(f"Failed to open video stream from {stream_url}")
            return None
            
        # Grab a single frame
        ret, frame = cap.read()
        cap.release()
        
        if not ret or frame is None:
            logger.error("Failed to read frame from video stream.")
            return None
            
        return frame
            
    except Exception as e:
        logger.error(f"Error grabbing stream frame for {channel_name}: {e}")
        return None

def detect_person(frame: np.ndarray) -> bool:
    """
    Processes a BGR image frame with OpenCV Haar Cascades for face detection.
    Returns True if at least one face is detected, False otherwise.
    """
    if frame is None:
        return False
        
    try:
        # Convert to grayscale for Haar Cascade
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Detect faces
        faces = face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=4,
            minSize=(30, 30)
        )
        
        # If detections exist, a person is present
        return len(faces) > 0
    except Exception as e:
        logger.error(f"Error during face detection: {e}")
        return False

def check_afk(channel_name: str) -> bool:
    """
    Grabs a frame and checks for a person.
    Returns True if AFK (no person detected), False otherwise.
    """
    frame = grab_stream_frame(channel_name)
    if frame is None:
        # If we can't grab a frame, assume there might be a stream issue, 
        # but don't strictly call it AFK to avoid false positives. 
        # Alternatively, returning True means "I don't see them" = AFK.
        return True
        
    person_present = detect_person(frame)
    return not person_present # AFK is true if person is NOT present
