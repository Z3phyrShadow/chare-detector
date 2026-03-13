import requests
import datetime
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class TwitchClient:
    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = None
        self.token_expires_at = None

    def _get_access_token(self) -> None:
        """Fetch App Access Token from Twitch."""
        url = f"https://id.twitch.tv/oauth2/token?client_id={self.client_id}&client_secret={self.client_secret}&grant_type=client_credentials"
        try:
            response = requests.post(url)
            response.raise_for_status()
            data = response.json()
            self.access_token = data.get("access_token")
            expires_in = data.get("expires_in", 3600)
            self.token_expires_at = datetime.datetime.now() + datetime.timedelta(seconds=expires_in - 60)
            logger.info("Successfully fetched new Twitch access token.")
        except Exception as e:
            logger.error(f"Failed to fetch Twitch access token: {e}")
            self.access_token = None

    def _ensure_token(self) -> None:
        if not self.access_token or not self.token_expires_at or datetime.datetime.now() >= self.token_expires_at:
            self._get_access_token()

    def check_stream_online(self, channel_name: str) -> Optional[Dict[str, Any]]:
        """Check if a specific channel is currently streaming."""
        self._ensure_token()
        if not self.access_token:
            return None

        url = f"https://api.twitch.tv/helix/streams?user_login={channel_name}"
        headers = {
            "Client-ID": self.client_id,
            "Authorization": f"Bearer {self.access_token}"
        }

        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            streams = data.get("data", [])
            if not streams:
                return None # Offline
            return streams[0] # Return stream info (Online)
        except Exception as e:
            logger.error(f"Failed to check stream status for {channel_name}: {e}")
            return None
