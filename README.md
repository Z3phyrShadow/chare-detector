# Twitch AFK Detector

A lightweight, server-side AFK detector for Twitch streams designed to run on free hosting tiers (Render, Railway, etc.). 
It polls your stream every 30 seconds (only when online) and uses MediaPipe Face Detection to determine if you are present or AFK.

## Features
* **100% Free Hosting Friendly**: Only processes frames when the stream is online, checking every 30 seconds.
* **MediaPipe Face Detection**: Lightweight ML model that handles small cams or fullscreen automatically.
* **Public Dashboard**: A clean, dark-mode web dashboard showing real-time stream status, current AFK duration, and historical stats.

## Setup for Local Development
1. Clone the repository.
2. Ensure you have Python 3.10+ installed.
3. Install dependencies: `uv pip install -r requirements.txt` (or standard pip)
4. Rename `.env.example` to `.env` and fill in your details:
   * Get your Twitch Client ID & Secret from the [Twitch Dev Console](https://dev.twitch.tv/console).
5. Run the server: `uvicorn main:app --reload`
6. Visit `http://localhost:8000` to see the dashboard.

## Deployment to Render (Free Tier)
This repo includes a `Dockerfile` and `render.yaml` for easy deployment.
1. Push this code to a GitHub repository.
2. Sign up for [Render](https://render.com) and link your GitHub.
3. Create a new "Blueprint Instance" and point it to your repo.
4. Render will automatically detect the `render.yaml`.
5. Enter your Twitch API credentials (`TWITCH_CLIENT_ID`, `TWITCH_CLIENT_SECRET`, `TWITCH_CHANNEL`) in the Environment Variables section in the Render dashboard.

### Preventing Sleep
Render's free tier sleeps after 15 minutes of inactivity. To ensure the detector runs during your stream, set up a free [UptimeRobot](https://uptimerobot.com/) HTTPS monitor pointing to your Render URL (e.g., `https://your-app.onrender.com/api/status`) polling every 10 minutes. 

## Limitations & Best Practices
* **Face Detection**: The detector relies on finding a face. If you wear a full mask or turn completely away for 30s, it may trigger AFK.
* **False Positives**: To avoid brief false positive AFKs, the dashboard updates every 5 seconds, but the underlying check is every 30 seconds.
