"""공통 유틸: Secrets, 세션 상태, UI 스타일."""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any, Optional

import streamlit as st

PACKAGE_DIR = Path(__file__).resolve().parent
DATA_DIR = PACKAGE_DIR.parent / "data"

SESSION_SITES = "sd_parcel_sites"
SESSION_ACTIVE_SITE_ID = "sd_active_site_id"
SESSION_MAP_STYLE = "sd_map_style"
SESSION_VWORLD_CACHE = "sd_vworld_parcel_cache"
SESSION_MODULE_MODEL = "sd_selected_module_model"


def _secret_str(v: Any) -> str:
    if v is None:
        return ""
    s = str(v).strip()
    return s


def get_secret(key: str, default: str = "") -> str:
    """Streamlit Secrets → 환경변수 순 (Juso/Kakao 등 키 이름 여러 형태 허용)."""
    env = os.environ.get(key, "").strip()
    if env:
        return env

    aliases: list[str] = [key]
    if key == "JUSO_API_KEY":
        aliases.extend(["JUSO_CONFIRM_KEY", "JUSO_confmKey", "confmKey"])

    try:
        for name in aliases:
            if name in st.secrets:
                s = _secret_str(st.secrets[name])
                if s:
                    return s
            v = st.secrets.get(name)
            if v is not None and not isinstance(v, dict):
                s = _secret_str(v)
                if s:
                    return s
    except Exception:
        pass

    for section, field in (
        ("solar_design", key),
        ("juso", "JUSO_API_KEY"),
        ("juso", "api_key"),
        ("juso", "confmKey"),
    ):
        try:
            nested = st.secrets.get(section) or {}
            if isinstance(nested, dict):
                if section == "juso" and key == "JUSO_API_KEY":
                    for fname in ("JUSO_API_KEY", "api_key", "confmKey", "confirmKey"):
                        s = _secret_str(nested.get(fname))
                        if s:
                            return s
                else:
                    s = _secret_str(nested.get(field))
                    if s:
                        return s
        except Exception:
            pass

    # 실수로 [passwords] 블록 안에 넣은 경우
    if key in ("JUSO_API_KEY", "JUSO_CONFIRM_KEY", "KAKAO_REST_API_KEY"):
        try:
            pw = st.secrets.get("passwords")
            if isinstance(pw, dict):
                for name in aliases:
                    if name in pw:
                        s = _secret_str(pw.get(name))
                        if s:
                            return s
        except Exception:
            pass
    return default


def diagnose_secrets_for_solar() -> list[str]:
    """키 값은 노출하지 않고 Secrets 배치만 안내."""
    lines: list[str] = []
    if get_secret("JUSO_API_KEY") or get_secret("JUSO_CONFIRM_KEY"):
        lines.append("Juso 승인키: 앱에서 인식됨")
    else:
        lines.append("Juso 승인키: 인식되지 않음")
        try:
            if "JUSO_API_KEY" in st.secrets:
                lines.append("→ `JUSO_API_KEY` 항목은 있으나 값이 비었거나 읽기 실패")
            pw = st.secrets.get("passwords")
            if isinstance(pw, dict) and (
                "JUSO_API_KEY" in pw or "JUSO_CONFIRM_KEY" in pw
            ):
                lines.append(
                    "→ `JUSO_API_KEY`가 **[passwords] 안**에 있습니다. "
                    "**[passwords] 위(맨 위)** 로 옮긴 뒤 Save · Reboot 하세요."
                )
            juso = st.secrets.get("juso")
            if isinstance(juso, dict):
                lines.append("→ `[juso]` 섹션이 있습니다. confmKey 또는 api_key 확인")
        except Exception as e:
            lines.append(f"→ Secrets 진단 중 오류: {e}")
        if len(lines) == 1:
            lines.append(
                "→ Cloud **Settings → Secrets**에 "
                "`JUSO_API_KEY = \"승인키\"` 가 **[passwords] 밖**에 있는지 확인"
            )
    return lines


def new_site_id() -> str:
    return uuid.uuid4().hex[:12]


def empty_land_info() -> dict:
    return {
        "소재지": "",
        "지번": "",
        "지목": "정보 없음",
        "필지_면적_m2": None,
        "용도지역": "정보 없음",
        "용도지구": "정보 없음",
        "국토계획법_지역지구": "정보 없음",
        "기타법령_지역지구": "정보 없음",
        "공시지가": "정보 없음",
        "도로_접면": "추가 확인 필요",
        "지형_경사": "정보 없음",
        "인허가_법령상_제한": [],
        "인허가_담당자_확인": ["용도지역·지구 최종 확인", "농지·산지 해당 여부", "개발행위허가·신재생에너지 설치 가능 여부"],
        "데이터_출처": "",
    }


def default_site(
    *,
    road: str = "",
    jibun: str = "",
    lat: float | None = None,
    lon: float | None = None,
) -> dict:
    return {
        "id": new_site_id(),
        "address_road": road,
        "address_jibun": jibun,
        "lat": lat,
        "lon": lon,
        "pnu": "",
        "boundary_geojson": None,
        "boundary_source": "",
        "land_info": empty_land_info(),
        "selected": True,
        "notes": "",
    }


def get_sites() -> list:
    if SESSION_SITES not in st.session_state:
        st.session_state[SESSION_SITES] = []
    return st.session_state[SESSION_SITES]


def set_sites(sites: list) -> None:
    st.session_state[SESSION_SITES] = sites


def _vworld_cache() -> dict:
    if SESSION_VWORLD_CACHE not in st.session_state:
        st.session_state[SESSION_VWORLD_CACHE] = {}
    return st.session_state[SESSION_VWORLD_CACHE]


def vworld_cache_key(lat: float, lon: float) -> str:
    return f"{round(lat, 5):.5f},{round(lon, 5):.5f}"


def get_cached_vworld_parcel(lat: float, lon: float) -> dict | None:
    """세션 내 성공한 필지 조회 결과 (VWorld 재호출 방지)."""
    hit = _vworld_cache().get(vworld_cache_key(lat, lon))
    return hit if isinstance(hit, dict) else None


def get_cached_vworld_parcel_by_pnu(pnu: str) -> dict | None:
    pnu = (pnu or "").strip()
    if not pnu:
        return None
    for parcel in _vworld_cache().values():
        if isinstance(parcel, dict) and (parcel.get("pnu") or "").strip() == pnu:
            return parcel
    return None


def store_vworld_parcel_cache(lat: float, lon: float, parcel: dict) -> None:
    if not parcel:
        return
    _vworld_cache()[vworld_cache_key(lat, lon)] = parcel
    pnu = (parcel.get("pnu") or "").strip()
    if pnu:
        _vworld_cache()[f"pnu:{pnu}"] = parcel


def get_active_site() -> Optional[dict]:
    sites = get_sites()
    if not sites:
        return None
    aid = st.session_state.get(SESSION_ACTIVE_SITE_ID)
    if aid:
        for s in sites:
            if s.get("id") == aid:
                return s
    return sites[0]


def load_json_data(filename: str) -> list:
    path = DATA_DIR / filename
    if not path.exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def render_step_wizard(current: int) -> None:
    steps = [
        "① 부지 선택",
        "② 부지 정보",
        "③ 자동 배치",
        "④ 그림자·일조",
        "⑤ 발전량·사업성",
        "⑥ 결과 비교",
    ]
    cols = st.columns(len(steps))
    for i, (col, label) in enumerate(zip(cols, steps), start=1):
        with col:
            if i == current:
                st.markdown(
                    f"<div style='text-align:center;font-weight:700;color:#2e7d32;"
                    f"border-bottom:3px solid #43a047;padding:6px 2px;'>{label}</div>",
                    unsafe_allow_html=True,
                )
            elif i < current:
                st.markdown(
                    f"<div style='text-align:center;color:#666;padding:6px 2px;'>{label}</div>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f"<div style='text-align:center;color:#bbb;padding:6px 2px;'>{label}</div>",
                    unsafe_allow_html=True,
                )


def render_solar_design_css() -> None:
    st.markdown(
        """
        <style>
        .sd-panel-title { font-size:14px; font-weight:700; color:#1b5e20; margin-bottom:8px; }
        .sd-card {
            background:#f1f8e9; border:1px solid #c5e1a5; border-radius:8px;
            padding:10px 12px; margin-bottom:8px; font-size:13px;
        }
        .sd-warn { color:#e65100; font-size:12px; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def api_status_line() -> str:
    parts = []
    if get_secret("JUSO_API_KEY") or get_secret("JUSO_CONFIRM_KEY"):
        parts.append("도로명주소(Juso) ✓")
    else:
        parts.append("도로명주소(Juso) — 키 미설정")
    if get_secret("KAKAO_REST_API_KEY"):
        parts.append("Kakao REST ✓")
    else:
        parts.append("Kakao REST — 키 미설정")
    if get_secret("VWORLD_API_KEY"):
        parts.append("VWorld 키✓(연결은 갱신·테스트로 확인)")
        dom = get_secret("VWORLD_DOMAIN") or "pmteampjt26.streamlit.app(기본)"
        parts.append(f"domain={dom}")
    else:
        parts.append("VWorld — 키 미설정(필지경계는 미연동)")
    return " | ".join(parts)
