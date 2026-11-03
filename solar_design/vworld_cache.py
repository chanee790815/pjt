"""VWorld 필지 조회 — Streamlit 서버 캐시·Cloud 완화 (1단계)."""

from __future__ import annotations

import hashlib
import os

import streamlit as st

from solar_design.utils import get_secret


def is_streamlit_cloud() -> bool:
    """Community Cloud 등 원격 호스트 추정."""
    if get_secret("DEPLOY_TARGET", "").lower() in ("cloud", "streamlit"):
        return True
    for env in ("STREAMLIT_CLOUD", "IS_STREAMLIT_CLOUD"):
        if os.environ.get(env, "").lower() in ("1", "true", "yes"):
            return True
    addr = (
        (os.environ.get("STREAMLIT_SERVER_ADDRESS") or "")
        + (os.environ.get("HOSTNAME") or "")
    ).lower()
    return "streamlit.app" in addr or "snowflake" in addr


def vworld_key_fingerprint() -> str:
    key = get_secret("VWORLD_API_KEY") or get_secret("VWORLD_KEY") or ""
    if not key:
        return "no-key"
    return hashlib.sha256(key.encode()).hexdigest()[:12]


def max_vworld_http_attempts() -> int:
    return 2 if is_streamlit_cloud() else 3


@st.cache_data(ttl=86400, show_spinner=False)
def cached_fetch_parcel(lon5: float, lat5: float, key_fp: str) -> tuple[dict | None, str | None]:
    """
    동일 좌표·키 — 24h 서버 캐시 (Cloud에서 재조회 부담 감소).
    반환 parcel은 JSON-serializable dict.
    """
    from solar_design.vworld_client import get_parcel_by_point_direct

    attempts = 2 if is_streamlit_cloud() else 3
    parcel, err = get_parcel_by_point_direct(lon5, lat5, max_http_attempts=attempts)
    if parcel:
        return parcel, None
    return None, err


def fetch_parcel_network(
    lon: float,
    lat: float,
    *,
    use_disk_cache: bool = True,
) -> tuple[dict | None, str | None]:
    """use_disk_cache=False → 갱신·테스트 버튼용 (항상 네트워크)."""
    lon5, lat5 = round(lon, 5), round(lat, 5)
    fp = vworld_key_fingerprint()
    if use_disk_cache and fp != "no-key":
        parcel, err = cached_fetch_parcel(lon5, lat5, fp)
        if parcel:
            return parcel, None
        if err and is_streamlit_cloud():
            return None, err
    from solar_design.vworld_client import get_parcel_by_point_direct

    return get_parcel_by_point_direct(
        lon, lat, max_http_attempts=max_vworld_http_attempts()
    )
