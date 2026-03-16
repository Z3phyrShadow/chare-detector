# chare-detector

Automatic AFK tracker for Twitch streams. Watches a stream in real-time, detects when the streamer leaves their webcam, and logs AFK sessions to a dashboard.

## How It Works

The server runs a background poller on a configurable interval. Each cycle:

1. **Stream check** — Queries the Twitch API to confirm the stream is live. If offline, closes any open session.
2. **Frame grab** — Uses `streamlink` to pull a single frame from the live stream.
3. **Webcam detection** — Measures pixel complexity (std dev) of the top-left 30% of the frame. A real webcam feed is visually complex; a starting/ending screen is flat → `NO_CAM`.
4. **Face detection** — If the webcam is visible, runs the OpenCV ResNet-SSD DNN face detector on the corner crop. Falls back to a full-frame scan for fullscreen cam layouts.
5. **State decision:**
   - `PRESENT` — face detected in webcam area
   - `AFK` — webcam visible, no face found
   - `NO_CAM` — starting/ending screen detected, or stream unavailable
6. **Rolling AFK confirmation** — Requires 3 consecutive `AFK` signals (at 1s intervals) before opening an AFK event in the database. Resets immediately on any `PRESENT` signal.

## States

| State | Meaning | AFK timer |
|---|---|---|
| `PRESENT` | Streamer at camera | Stops |
| `AFK` | Camera on, streamer gone | Starts (after 3 confirmations) |
| `NO_CAM` | Starting/ending screen | No effect |
| `OFFLINE` | Stream is offline | — |

## Setup

### 1. Clone and install

```bash
git clone <repo-url>
cd chare-detector
uv sync
```

### 2. Configure

Copy `.env.example` to `.env` and fill in your credentials:

```env
TWITCH_CLIENT_ID=your_client_id
TWITCH_CLIENT_SECRET=your_client_secret
TWITCH_CHANNEL=channel_name
POLL_INTERVAL_SECONDS=30
```

**Get Twitch credentials:**
- Go to [dev.twitch.tv/console](https://dev.twitch.tv/console)
- Create a new application → copy Client ID and generate a Client Secret

### 3. Run

```bash
uv run uvicorn main:app --reload
```

Open [http://localhost:8000](http://localhost:8000) for the dashboard.

> **Note:** On first run, the DNN face detector model (~2MB) will be downloaded automatically to `models/`.

## Tech Stack

- **Backend:** FastAPI + SQLAlchemy (SQLite)
- **Vision:** OpenCV DNN (ResNet-SSD face detector) + streamlink
- **Frontend:** Vanilla HTML/CSS/JS
- **Stream:** Twitch API + streamlink

## Dashboard

The dashboard shows:
- Live streamer state (PRESENT / AFK / NO_CAM / OFFLINE)
- AFK time this stream
- AFK time this month
- Debug camera view with detection overlay (face confidence scores + webcam zone)

## Expose publicly (optional)

To access the dashboard remotely while running locally:

```bash
ngrok http 8000
```

Install ngrok from [ngrok.com](https://ngrok.com), run `ngrok config add-authtoken <token>` once, then the above command gives you a public HTTPS URL.
