import cv2
import streamlink
import numpy as np
import logging
import urllib.request
import os
from typing import Optional

logger = logging.getLogger(__name__)

# ── DNN Face Detector Setup ────────────────────────────────────────────────────

_MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")
_PROTO_PATH = os.path.join(_MODEL_DIR, "deploy.prototxt")
_MODEL_PATH = os.path.join(_MODEL_DIR, "res10_300x300_ssd_iter_140000.caffemodel")

_PROTO_URL = "https://raw.githubusercontent.com/opencv/opencv/master/samples/dnn/face_detector/deploy.prototxt"
_MODEL_URL = "https://github.com/opencv/opencv_3rdparty/raw/dnn_samples_face_detector_20170830/res10_300x300_ssd_iter_140000.caffemodel"

def _ensure_model():
    os.makedirs(_MODEL_DIR, exist_ok=True)
    if not os.path.exists(_PROTO_PATH):
        logger.info("Downloading DNN face detector prototxt...")
        urllib.request.urlretrieve(_PROTO_URL, _PROTO_PATH)
    if not os.path.exists(_MODEL_PATH):
        logger.info("Downloading DNN face detector weights (~2MB)...")
        urllib.request.urlretrieve(_MODEL_URL, _MODEL_PATH)

_net = None

def _get_net():
    global _net
    if _net is None:
        _ensure_model()
        _net = cv2.dnn.readNetFromCaffe(_PROTO_PATH, _MODEL_PATH)
        logger.info("DNN face detector loaded.")
    return _net

# ── Stream Frame Capture ───────────────────────────────────────────────────────

def grab_stream_frame(channel_name: str) -> Optional[np.ndarray]:
    url = f"https://twitch.tv/{channel_name}"
    try:
        streams = streamlink.streams(url)
        if not streams:
            return None
        best_stream = streams.get("best", streams.get("720p", streams.get("480p", None)))
        if not best_stream:
            return None
        cap = cv2.VideoCapture(best_stream.url)
        if not cap.isOpened():
            return None
        ret, frame = cap.read()
        cap.release()
        return frame if ret and frame is not None else None
    except Exception as e:
        logger.error(f"Error grabbing frame for {channel_name}: {e}")
        return None

# ── Step 1: Webcam vs NO_CAM Detection ────────────────────────────────────────
# Starting/ending screens are flat, simple graphics — very low pixel variance.
# A real webcam feed over a game is complex — high pixel variance.
# We measure the standard deviation of the top-left 30% crop to tell them apart.

WEBCAM_STD_THRESHOLD = 35.0  # Below this = simple screen = NO_CAM

def _get_corners(frame: np.ndarray):
    """Returns (x, y, w, h) for each of the 4 corner crops (30% of frame each)."""
    h, w = frame.shape[:2]
    cw, ch = int(w * 0.30), int(h * 0.30)
    return [
        (0,    0,    cw, ch),  # Top-left
        (w-cw, 0,    cw, ch),  # Top-right
        (0,    h-ch, cw, ch),  # Bottom-left
        (w-cw, h-ch, cw, ch),  # Bottom-right
    ]

def is_webcam_visible(frame: np.ndarray) -> bool:
    """
    Returns True if any corner looks like a webcam feed (complex natural scene).
    Starting/ending screens are flat everywhere — all corners will have low std dev.
    """
    corners = _get_corners(frame)
    std_devs = []
    for (cx, cy, cw, ch) in corners:
        crop = frame[cy:cy+ch, cx:cx+cw]
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        std_devs.append(float(np.std(gray)))
    best = max(std_devs)
    logger.debug(f"Corner std_devs: {[f'{s:.1f}' for s in std_devs]}  best={best:.1f}")
    return best > WEBCAM_STD_THRESHOLD

# ── Step 2: Face Detection in Webcam Area ─────────────────────────────────────

def detect_face_in_frame(frame: np.ndarray, confidence_threshold: float = 0.5) -> bool:
    """
    Runs DNN face detection on the given frame (or crop).
    Returns True if any face is found above confidence_threshold.
    """
    net = _get_net()
    h, w = frame.shape[:2]
    blob = cv2.dnn.blobFromImage(cv2.resize(frame, (300, 300)), 1.0,
                                  (300, 300), (104.0, 177.0, 123.0))
    net.setInput(blob)
    detections = net.forward()
    for i in range(detections.shape[2]):
        if float(detections[0, 0, i, 2]) >= confidence_threshold:
            return True
    return False

def detect_face_in_corner(frame: np.ndarray) -> bool:
    """
    Scans all 4 corners for a face using DNN detection.
    Falls back to a full-frame scan for fullscreen cam layouts.
    """
    corners = _get_corners(frame)
    for (cx, cy, cw, ch) in corners:
        crop = frame[cy:cy+ch, cx:cx+cw]
        if detect_face_in_frame(crop):
            return True

    # Fallback: fullscreen cam — scan the whole frame at higher confidence
    return detect_face_in_frame(frame, confidence_threshold=0.7)

# ── Main Analysis ──────────────────────────────────────────────────────────────

def analyze_frame(channel_name: str, save_debug: bool = True) -> str:
    """
    Two-step detection:
      Step 1 — Is the webcam visible? (complexity check)
      Step 2 — Is the streamer's face in the webcam? (DNN face detector)
    Returns 'PRESENT', 'AFK', or 'NO_CAM'.
    """
    frame = grab_stream_frame(channel_name)
    if frame is None:
        return "NO_CAM"

    try:
        h, w = frame.shape[:2]

        # — Step 1: Check webcam visibility —
        webcam_on = is_webcam_visible(frame)

        if not webcam_on:
            status = "NO_CAM"
        else:
            # — Step 2: Check for face in webcam corner —
            face_found = detect_face_in_corner(frame)
            status = "PRESENT" if face_found else "AFK"

        # — Debug image —
        if save_debug:
            debug = frame.copy()
            corners = _get_corners(frame)

            # Compute best std dev for label
            best_std = max(
                float(np.std(cv2.cvtColor(frame[cy:cy+ch, cx:cx+cw], cv2.COLOR_BGR2GRAY)))
                for (cx, cy, cw, ch) in corners
            )

            # Draw all corner zones + DNN detections in each
            zone_color = (0, 180, 0) if webcam_on else (0, 0, 180)
            net = _get_net() if webcam_on else None
            for (cx, cy, cw, ch) in corners:
                cv2.rectangle(debug, (cx, cy), (cx+cw, cy+ch), zone_color, 2)
                if webcam_on:
                    crop = frame[cy:cy+ch, cx:cx+cw]
                    blob = cv2.dnn.blobFromImage(cv2.resize(crop, (300, 300)), 1.0,
                                                  (300, 300), (104.0, 177.0, 123.0))
                    net.setInput(blob)
                    dets = net.forward()
                    for i in range(dets.shape[2]):
                        conf = float(dets[0, 0, i, 2])
                        if conf >= 0.4:
                            box = dets[0, 0, i, 3:7] * np.array([cw, ch, cw, ch])
                            x1, y1, x2, y2 = box.astype(int)
                            face_color = (0, 255, 0) if conf >= 0.5 else (0, 180, 255)
                            cv2.rectangle(debug, (cx+x1, cy+y1), (cx+x2, cy+y2), face_color, 2)
                            cv2.putText(debug, f"{conf:.2f}", (cx+x1, cy+y1-5),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, face_color, 1)

            # Status label
            color = (0, 255, 0) if status == "PRESENT" else ((0, 0, 255) if status == "AFK" else (120, 120, 120))
            cv2.putText(debug, f"State: {status}  |  cam_std: {best_std:.1f}", (10, 35),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, color, 2)
            cv2.imwrite("static/debug.jpg", debug)

        return status

    except Exception as e:
        logger.error(f"Error during frame analysis: {e}")
        return "NO_CAM"
