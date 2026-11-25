import os


def _webapp_url() -> str | None:
    url = os.getenv("WEBAPP_URL")
    if url:
        return url.rstrip("/") + "/"
    domain = os.getenv("RAILWAY_PUBLIC_DOMAIN")
    return f"https://{domain}/" if domain else None


class Config:
    token: str = os.getenv("BOT_TOKEN", "")
    db_path: str = os.getenv("DATABASE_PATH", "data/kickoff.db")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    port: int = int(os.getenv("PORT", "8080"))
    webapp_url: str | None = _webapp_url()
    football_data_key: str = os.getenv("FOOTBALL_DATA_KEY", "")
