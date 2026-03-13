import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    TWITCH_CLIENT_ID: str = ""
    TWITCH_CLIENT_SECRET: str = ""
    TWITCH_CHANNEL: str = "your_channel_here" # Target channel to monitor
    POLL_INTERVAL_SECONDS: int = 30
    
    class Config:
        env_file = ".env"

settings = Settings()
