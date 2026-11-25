import os


class Config:
    token: str = os.getenv("BOT_TOKEN", "")
    db_path: str = os.getenv("DATABASE_PATH", "data/kickoff.db")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
