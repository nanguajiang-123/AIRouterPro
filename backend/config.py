from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv

# ── project root anchor ────────────────────────────────────────────────────
# config.py is at backend/config.py  →  parent.parent = project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Load .env from project root (works regardless of CWD)
load_dotenv(PROJECT_ROOT / ".env")


def _get_str(name: str, default: str) -> str:
    value = os.getenv(name)
    return value if value not in (None, "") else default


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    # ── server ───────────────────────────────────────────────────────────
    base_url: str
    base_port: int

    # ── logging ──────────────────────────────────────────────────────────
    log_level: str
    log_file: str

    # ── ODL northbound (REST API) ────────────────────────────────────────
    odl_north_ip: str
    odl_north_port: int
    odl_north_user: str
    odl_north_pass: str

    # ── ODL southbound (OpenFlow) ────────────────────────────────────────
    odl_south_ip: str
    odl_south_port: int
    odl_south_user: str
    odl_south_pass: str

    # ── DeepSearch LLM (intent classification) ──────────────────────────
    deepsearch_api_key: str
    deepsearch_url: str

    # ── XCHiRL routing model ────────────────────────────────────────────
    xchirl_model_path: str

    # ── derived ──────────────────────────────────────────────────────────
    @property
    def xchirl_model_abs_path(self) -> str:
        """返回绝对路径（支持相对 .env 的相对路径）。"""
        p = Path(self.xchirl_model_path)
        return str(p if p.is_absolute() else PROJECT_ROOT / p)
    @property
    def odl_north_base_url(self) -> str:
        return f"http://{self.odl_north_ip}:{self.odl_north_port}"


def get_settings() -> Settings:
    return Settings(
        # server
        base_url=_get_str("BASE_URL", "127.0.0.1"),
        base_port=_get_int("BASE_PORT", 8000),
        # logging
        log_level=_get_str("LOG_LEVEL", "INFO"),
        log_file=_get_str("LOG_FILE", "logs/app.log"),
        # ODL north
        odl_north_ip=_get_str("ODL_NORTH_IP", "127.0.0.1"),
        odl_north_port=_get_int("ODL_NORTH_PORT", 8181),
        odl_north_user=_get_str("ODL_NORTH_USER", "admin"),
        odl_north_pass=_get_str("ODL_NORTH_PASS", "admin"),
        # ODL south
        odl_south_ip=_get_str("ODL_SOUTH_IP", "127.0.0.1"),
        odl_south_port=_get_int("ODL_SOUTH_PORT", 6633),
        odl_south_user=_get_str("ODL_SOUTH_USER", "admin"),
        odl_south_pass=_get_str("ODL_SOUTH_PASS", "admin"),
        # DeepSearch
        deepsearch_api_key=_get_str("DEEPSEARCH_API_KEY", ""),
        deepsearch_url=_get_str("DEEPSEARCH_API_URL", ""),
        # XCHiRL
        xchirl_model_path=_get_str("XCHIRL_MODEL_PATH", ""),
    )


settings = get_settings()
