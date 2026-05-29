from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import os
from dotenv import load_dotenv

@dataclass(frozen=True)
class Settings:
    supabase_url: str
    supabase_key: str
    output_dir: Path

def load_settings() -> Settings:
    load_dotenv()
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise RuntimeError("Missing SUPABASE_URL or SUPABASE_KEY in .env")
    return Settings(url, key, Path(os.getenv("OUTPUT_DIR", "output")))
