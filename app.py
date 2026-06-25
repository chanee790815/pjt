import streamlit as st
import pandas as pd
import datetime
import gspread
from gspread.exceptions import APIError, WorksheetNotFound
from google.oauth2.service_account import Credentials
import requests
import time
import plotly.express as px
import plotly.graph_objects as go
import io
import streamlit.components.v1 as components
import numpy as np
import json
import pathlib
import os
import re
from typing import Optional
import hmac
import hashlib
import base64
import html as html_module
import copy

# 1. 페이지 설정
st.set_page_config(page_title="PM 통합 공정 관리 v4.5.22", page_icon="🏗️", layout="wide")

# --- [UI] 스타일 ---
st.markdown("""
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    html, body, [class*="css"] { font-family: 'Pretendard', sans-serif; }
    
    /* 메인 제목 반응형 최적화 */
    h1 {
        font-size: clamp(1.5rem, 6vw, 2.5rem) !important; 
        word-break: keep-all !important; 
        line-height: 1.3 !important;
    }
    
    .footer { position: fixed; left: 0; bottom: 0; width: 100%; background-color: rgba(128, 128, 128, 0.15); backdrop-filter: blur(5px); text-align: center; padding: 5px; font-size: 11px; z-index: 100; }
    
    /* 박스 디자인 (반투명 회색 배경) 및 자동 줄바꿈 최적화 */
    .weekly-box { background-color: rgba(128, 128, 128, 0.1); padding: 10px 12px; border-radius: 6px; margin-top: 4px; font-size: 12.5px; line-height: 1.6; border: 1px solid rgba(128, 128, 128, 0.2); white-space: normal; word-break: keep-all; word-wrap: break-word; }
    .history-box { background-color: rgba(128, 128, 128, 0.1); padding: 15px; border-radius: 8px; border-left: 5px solid #2196f3; margin-bottom: 20px; white-space: normal; word-break: keep-all; word-wrap: break-word; }
    .stMetric { background-color: rgba(128, 128, 128, 0.05); padding: 15px; border-radius: 10px; border: 1px solid rgba(128, 128, 128, 0.2); }
    
    /* 태그 및 뱃지 */
    .pm-tag { background-color: rgba(25, 113, 194, 0.15); color: #339af0; padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: 600; border: 1px solid rgba(25, 113, 194, 0.3); display: inline-block; }
    .status-badge { padding: 3px 8px; border-radius: 12px; font-size: 11px; font-weight: 700; display: inline-block; white-space: nowrap; }
    .status-normal { background-color: rgba(33, 150, 243, 0.15); color: #42a5f5; border: 1px solid rgba(33, 150, 243, 0.3); }
    .status-delay { background-color: rgba(244, 67, 54, 0.15); color: #ef5350; border: 1px solid rgba(244, 67, 54, 0.3); }
    .status-done { background-color: rgba(76, 175, 80, 0.15); color: #66bb6a; border: 1px solid rgba(76, 175, 80, 0.3); }
    
    /* 컴팩트 버튼 디자인 */
    div[data-testid="stButton"] button {
        min-height: 26px !important;
        height: 26px !important;
        padding: 0px 4px !important;
        font-size: 11.5px !important;
        border-radius: 6px !important;
        font-weight: 600 !important;
        line-height: 1 !important;
        margin: 0 !important;
        margin-top: 2px !important;
        width: 100% !important;
    }
    
    /* 진행바 마진 최적화 */
    div[data-testid="stProgressBar"] { margin-bottom: 0px !important; margin-top: 5px !important; }
    
    /* ========================================================= */
    /* 모바일 세로 모드에서 버튼이 밑으로 떨어지는 현상 강제 차단 */
    /* ========================================================= */
    @media (max-width: 768px) {
        div[data-testid="stContainer"] div[data-testid="stHorizontalBlock"] {
            flex-direction: row !important; /* 강제 가로 배치 */
            flex-wrap: nowrap !important;   /* 줄바꿈 금지 */
            align-items: flex-start !important; /* 위쪽 정렬 */
            gap: 5px !important;
        }
        /* 제목 부분 영역 확보 */
        div[data-testid="stContainer"] div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:first-child {
            width: calc(100% - 80px) !important;
            flex: 1 1 auto !important;
            min-width: 0 !important;
        }
        /* 버튼 부분 영역 고정 */
        div[data-testid="stContainer"] div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:last-child {
            width: 75px !important;
            flex: 0 0 75px !important;
            min-width: 75px !important;
        }
        .metric-container { flex-wrap: wrap; }
    }

    /* ========================================================= */
    /* [상단 메뉴] 가로 메뉴 바 */
    /* ========================================================= */
    [data-testid="stVerticalBlock"] > div:has([data-testid="column"]) [data-testid="stHorizontalBlock"] {
        gap: 8px;
    }

    /* ========================================================= */
    /* [간트 차트] 상단 기간 표시줄 틀 고정 (스크롤 시 상단 고정) */
    /* ========================================================= */
    .gantt-sticky-header {
        position: sticky;
        top: 0;
        z-index: 60;
        background: linear-gradient(180deg, #f0f4f8 0%, #e8eef4 100%);
        padding: 10px 14px;
        margin: 0 -1rem 8px -1rem;
        border-bottom: 2px solid rgba(33, 150, 243, 0.35);
        font-weight: 700;
        font-size: 14px;
        color: #1565c0;
        box-shadow: 0 2px 6px rgba(0,0,0,0.06);
    }
    @media (max-width: 768px) {
        .gantt-sticky-header { font-size: 13px; padding: 8px 10px; }
    }

    /* ========================================================= */
    /* [간트 차트] 상단 월 눈금(틀 고정) + 본문 스크롤 */
    /* ========================================================= */
    .gantt-freeze-panel {
        border: 1px solid rgba(128, 128, 128, 0.28);
        border-radius: 8px;
        overflow: hidden;
        background: #fafbfc;
        margin-bottom: 8px;
    }
    .gantt-month-ruler-wrap {
        display: flex;
        align-items: stretch;
        background: linear-gradient(180deg, #eef3f8 0%, #e3eaf2 100%);
        border-bottom: 2px solid rgba(33, 150, 243, 0.28);
    }
    .gantt-month-ruler-spacer {
        flex: 0 0 78px;
        min-width: 78px;
        border-right: 1px solid rgba(128, 128, 128, 0.2);
        background: rgba(255, 255, 255, 0.55);
    }
    .gantt-month-ruler-track {
        flex: 1 1 auto;
        display: flex;
        justify-content: space-between;
        gap: 4px;
        padding: 7px 92px 7px 8px;
        font-size: 11px;
        font-weight: 700;
        color: #1565c0;
        overflow: hidden;
        white-space: nowrap;
    }
    .gantt-month-cell {
        flex: 1 1 0;
        text-align: center;
        min-width: 0;
    }
    @media (max-width: 768px) {
        .gantt-month-ruler-spacer { flex: 0 0 62px; min-width: 62px; }
        .gantt-month-ruler-track { padding-right: 72px; font-size: 10px; }
    }

    /* ========================================================= */
    /* [일일보고] 엑셀 양식형 화면 */
    /* ========================================================= */
    .daily-report-viewport {
        overflow-x: auto;
        margin: 8px 0 16px 0;
        border: 1px solid #b4b4b4;
        border-radius: 4px;
        background: #fff;
    }
    .daily-report-sheet {
        min-width: 920px;
        font-family: 'Pretendard', 'Malgun Gothic', sans-serif;
        font-size: 12px;
        color: #111;
    }
    .daily-report-top {
        display: flex;
        align-items: stretch;
        border-bottom: 1px solid #b4b4b4;
    }
    .daily-report-date-box {
        flex: 0 0 200px;
        background: #4f81bd;
        color: #fff;
        font-size: 22px;
        font-weight: 700;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 18px 12px;
        border-right: 1px solid #b4b4b4;
        text-align: center;
        line-height: 1.35;
    }
    .daily-report-legend {
        flex: 1 1 auto;
        display: grid;
        grid-template-columns: 1fr 1fr;
        border-collapse: collapse;
    }
    .daily-report-legend-cell {
        border: 1px solid #b4b4b4;
        border-top: none;
        padding: 5px 8px;
        font-size: 11px;
        background: #fff;
        vertical-align: middle;
    }
    .daily-report-legend-cell b { font-size: 12px; }
    .daily-report-legend-note {
        grid-column: 1 / -1;
        text-align: right;
        font-size: 10px;
        color: #444;
        padding: 2px 8px 4px;
        background: #fafafa;
        border-bottom: 1px solid #b4b4b4;
    }
    .daily-report-table {
        width: 100%;
        border-collapse: collapse;
        table-layout: fixed;
    }
    .daily-report-table th {
        background: #d9d9d9;
        border: 1px solid #808080;
        padding: 6px 4px;
        font-weight: 700;
        text-align: center;
        font-size: 12px;
    }
    .daily-report-table td {
        border: 1px solid #808080;
        padding: 5px 6px;
        vertical-align: middle;
        line-height: 1.45;
        word-break: keep-all;
        overflow-wrap: break-word;
    }
    .daily-report-table .dr-col-id { width: 52px; text-align: center; }
    .daily-report-table .dr-col-major { width: 88px; text-align: center; font-weight: 600; background: #fafafa; }
    .daily-report-table .dr-col-sub { width: 108px; text-align: center; }
    .daily-report-table .dr-col-work { text-align: left; }
    .daily-report-table .dr-col-pct { width: 72px; text-align: center; }
    .daily-report-table .dr-col-note { width: 140px; text-align: left; font-size: 11px; }
    .daily-report-project-tag {
        padding: 4px 10px;
        background: #eef4fb;
        border-bottom: 1px solid #c5d3e3;
        font-size: 12px;
        font-weight: 600;
        color: #1565c0;
    }
    @media (max-width: 768px) {
        .daily-report-date-box { flex: 0 0 140px; font-size: 16px; padding: 12px 8px; }
    }
    .daily-report-viewport--dashboard {
        max-height: 420px;
        overflow: auto;
        margin: 4px 0 0 0;
    }
    .daily-report-viewport--dashboard .daily-report-sheet {
        min-width: 520px;
        font-size: 11px;
    }
    .daily-report-viewport--dashboard .daily-report-date-box {
        flex: 0 0 130px;
        font-size: 15px;
        padding: 10px 8px;
    }
    .daily-report-top--compact {
        border-bottom: 1px solid #b4b4b4;
    }
    .dashboard-report-split-title {
        font-size: 13px;
        font-weight: 700;
        margin: 8px 0 6px 0;
        color: #333;
    }
    @media print {
        .daily-report-viewport { border: none; overflow: visible; }
    }

    /* ========================================================= */
    /* [보고서 인쇄/PDF 최적화 CSS] */
    /* ========================================================= */
    @media print {
        /* 불필요한 UI 숨기기 */
        header[data-testid="stHeader"] { display: none !important; }
        section[data-testid="stSidebar"] { display: none !important; }
        .footer { display: none !important; }
        iframe { display: none !important; } /* 인쇄 버튼 자체 숨김 */
        button { display: none !important; } /* 화면 내 다른 버튼들 숨김 */
        
        /* 여백 최소화 및 배경색 강제 인쇄 설정 */
        .block-container { max-width: 100% !important; padding: 10px !important; margin: 0 !important; }
        * { -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }
        
        /* 카드가 페이지 중간에 잘리는 것 방지 */
        div[data-testid="stContainer"] { page-break-inside: avoid; }
    }
    </style>
    <div class="footer">시스템 상태: 정상 (v4.5.22) | PDF/보고서 인쇄 기능 추가</div>
    """, unsafe_allow_html=True)

# ---------------------------------------------------------
# [SECTION 1] 백엔드 엔진 & 유틸리티
# ---------------------------------------------------------

# --- [파일 캐시] 구글 시트 데이터를 로컬 파일로 저장/로드 (앱 재시작 후에도 유지) ---
CACHE_DIR = pathlib.Path("pms_sheet_cache")
FILE_CACHE_TTL = int(os.environ.get("PMS_CACHE_TTL", "300"))  # 초 (기본 5분). 0이면 파일 캐시 미사용
SHEET_CACHE_ENABLED = os.environ.get("PMS_SHEET_CACHE", "true").strip().lower() not in (
    "0", "false", "no", "off",
)
WORKSHEET_LIST_CACHE = CACHE_DIR / "worksheet_list.json"  # 프로젝트 목록 캐시 파일
MENU_VISIBILITY_CACHE = CACHE_DIR / "menu_visibility.json"  # 일반 사용자 메뉴 숨김 설정

ALL_PMO_MENUS = [
    "통합 대시보드",
    "주간 최종 보고(표)",
    "일일보고",
    "프로젝트 상세",
    "일 발전량 분석",
    "경영지표(KPI)",
    "마스터 설정",
]
ADMIN_MENU = "마스터 설정"
ADMIN_USER_ID = "admin"
MENU_CONFIG_SHEET = "Control_Center"
MENU_CONFIG_KEY = "hidden_pmo_menus"
DAILY_REPORT_SHEET = "일일보고"
DAILY_REPORT_COLUMNS = [
    "날짜",
    "프로젝트명",
    "구분",
    "대분류",
    "세부항목",
    "업무내용",
    "공정율(%)",
    "비고",
    "저장시각",
    "저장자",
]


def is_admin_user() -> bool:
    return str(st.session_state.get("user_id", "")).strip().lower() == ADMIN_USER_ID


def _normalize_hidden_menu_list(hidden) -> list:
    if not isinstance(hidden, list):
        return []
    return [m for m in hidden if m in ALL_PMO_MENUS and m != ADMIN_MENU]


def _load_user_hidden_menus_from_file() -> list:
    if not MENU_VISIBILITY_CACHE.exists():
        return []
    try:
        with open(MENU_VISIBILITY_CACHE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return _normalize_hidden_menu_list(data.get("hidden_menus", []))
    except Exception:
        pass
    return []


def _load_user_hidden_menus_from_sheet(sh) -> Optional[list]:
    try:
        ws = safe_api_call(sh.worksheet, MENU_CONFIG_SHEET)
        rows = safe_api_call(ws.get_all_values)
        for row in rows:
            if len(row) >= 2 and str(row[0]).strip() == MENU_CONFIG_KEY:
                parsed = json.loads(str(row[1]).strip() or "[]")
                return _normalize_hidden_menu_list(parsed)
    except Exception:
        pass
    return None


def _save_user_hidden_menus_to_sheet(sh, hidden: list) -> None:
    valid = _normalize_hidden_menu_list(hidden)
    payload = json.dumps(valid, ensure_ascii=False)
    try:
        ws = safe_api_call(sh.worksheet, MENU_CONFIG_SHEET)
    except WorksheetNotFound:
        ws = safe_api_call(sh.add_worksheet, title=MENU_CONFIG_SHEET, rows="100", cols="10")
        safe_api_call(ws.update, "A1", [["설정키", "설정값"]])
    rows = safe_api_call(ws.get_all_values)
    target_row = None
    for idx, row in enumerate(rows, start=1):
        if row and str(row[0]).strip() == MENU_CONFIG_KEY:
            target_row = idx
            break
    if target_row is None:
        safe_api_call(ws.append_row, [MENU_CONFIG_KEY, payload])
    else:
        safe_api_call(ws.update, f"B{target_row}", [[payload]])


def load_user_hidden_menus(sh=None) -> list:
    """파일 캐시 + 구글 시트(Control_Center)에서 숨김 메뉴 로드 (시트 우선)"""
    if sh is not None:
        sheet_hidden = _load_user_hidden_menus_from_sheet(sh)
        if sheet_hidden is not None:
            _save_file_cache(MENU_VISIBILITY_CACHE, {"hidden_menus": sheet_hidden})
            return sheet_hidden
    return _load_user_hidden_menus_from_file()


def save_user_hidden_menus(sh, hidden: list) -> None:
    valid = _normalize_hidden_menu_list(hidden)
    _save_file_cache(MENU_VISIBILITY_CACHE, {"hidden_menus": valid})
    if sh is not None:
        _save_user_hidden_menus_to_sheet(sh, valid)


def get_pmo_menus_for_current_user(sh=None) -> list:
    """현재 로그인 사용자에게 표시할 PMO 메뉴 (admin은 전체, 일반 사용자는 숨김 설정 반영)"""
    if is_admin_user():
        return list(ALL_PMO_MENUS)
    hidden = set(load_user_hidden_menus(sh))
    hidden.add(ADMIN_MENU)
    return [m for m in ALL_PMO_MENUS if m not in hidden]


def _sheet_name_to_filename(name: str) -> str:
    """시트명을 파일명으로 사용 가능하게 정리"""
    safe = "".join(c if c.isalnum() or c in (" ", "-", "_") else "_" for c in str(name).strip())
    return (safe[:50] + "_" + str(hash(name) % 10000)) if len(safe) > 50 else safe

def _load_file_cache(cache_path: pathlib.Path, ttl_seconds: int):
    """파일 캐시가 있고 TTL 이내면 데이터 반환, 아니면 None"""
    if not cache_path.exists():
        return None
    try:
        mtime = cache_path.stat().st_mtime
        if (time.time() - mtime) > ttl_seconds:
            return None
        with open(cache_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def _save_file_cache(cache_path: pathlib.Path, data) -> None:
    """데이터를 JSON 파일로 저장"""
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=None)
    except Exception:
        pass

def clear_file_cache(worksheet_name: str = None, preserve_menu_config: bool = True):
    """파일 캐시 삭제. worksheet_name 이 None 이면 전체 삭제 (메뉴 표시 설정 파일은 유지 가능)"""
    if not CACHE_DIR.exists():
        return
    if worksheet_name is None:
        for f in CACHE_DIR.glob("*.json"):
            if preserve_menu_config and f.name == MENU_VISIBILITY_CACHE.name:
                continue
            try:
                f.unlink()
            except Exception:
                pass
    else:
        p = CACHE_DIR / f"{_sheet_name_to_filename(worksheet_name)}.json"
        if p.exists():
            try:
                p.unlink()
            except Exception:
                pass
    # head 캐시는 시트별 파일명에 _head_ 가 들어감
    if worksheet_name:
        for f in CACHE_DIR.glob(f"*{_sheet_name_to_filename(worksheet_name)}*head*"):
            try:
                f.unlink()
            except Exception:
                pass
    else:
        for f in CACHE_DIR.glob("*head*"):
            try:
                f.unlink()
            except Exception:
                pass


def refresh_sheet_data_cache(project_names=None, invalidate_editor: bool = True) -> None:
    """
    구글 시트 읽기 캐시(메모리 + 파일)를 비우고 다음 조회 시 시트에서 다시 읽게 함.
    project_names 가 있으면 해당 프로젝트 파일 캐시만 삭제.
    """
    cached_get_all_values.clear()
    cached_get_all_records.clear()
    cached_get_head.clear()
    if project_names:
        for p in project_names:
            clear_file_cache(p, preserve_menu_config=True)
    else:
        clear_file_cache(preserve_menu_config=True)
    if invalidate_editor:
        invalidate_process_edit_cache(project_names if project_names else None)
        if project_names:
            for p in project_names:
                st.session_state.pop(f"process_edit_sig_{p}", None)
        else:
            for key in list(st.session_state.keys()):
                if str(key).startswith("process_edit_sig_"):
                    st.session_state.pop(key, None)
    st.session_state["sheet_cache_refreshed_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def render_sidebar_cache_controls():
    """사이드바: 캐시 안내 + 수동 새로고침 (5분 캐시는 유지, 필요 시 즉시 갱신)"""
    st.sidebar.divider()
    if SHEET_CACHE_ENABLED and FILE_CACHE_TTL > 0:
        refreshed = st.session_state.get("sheet_cache_refreshed_at")
        if refreshed:
            st.sidebar.caption(f"📦 시트 캐시: 최근 새로고침 {refreshed}")
        else:
            st.sidebar.caption(f"📦 시트 캐시: 최대 {FILE_CACHE_TTL // 60}분 유지 (빠른 조회용)")
    else:
        st.sidebar.caption("📦 시트 캐시: 꺼짐 (매번 구글 시트 조회)")
    if st.sidebar.button("🔄 구글 시트 새로고침", use_container_width=True, key="sidebar_refresh_sheet_cache"):
        with st.spinner("구글 시트에서 최신 데이터를 불러오는 중…"):
            refresh_sheet_data_cache()
        st.rerun()


def safe_api_call(func, *args, **kwargs):
    """API 할당량 초과(429) 방지를 위한 자동 재시도 함수"""
    retries = 5
    for i in range(retries):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if "429" in str(e) and i < retries - 1:
                time.sleep(2 ** i)
                continue
            else:
                raise e

# --- [세션 유지] WebSocket 순단·백그라운드 탭 등으로 세션이 끊길 때 로그인이 풀리는 완화 ---
# 1) 같은 폴더의 `.streamlit/config.toml` → server.disconnectedSessionTTL (기본 120초보다 크게)
# 2) 아래 URL 토큰: 재접속 시 브라우저 URL에 pm_auth 가 남아 있으면 서명 검증 후 로그인 복구
LOGIN_URL_TOKEN_PARAM = "pm_auth"
LOGIN_URL_TOKEN_TTL_SEC = int(os.environ.get("PM_LOGIN_TOKEN_TTL", str(7 * 24 * 3600)))  # 기본 7일


def _session_signing_secret() -> Optional[bytes]:
    """Secrets의 SESSION_SIGNING_KEY(권장) 없으면 passwords 항목으로부터 안정적인 파생키."""
    try:
        raw = str(st.secrets.get("SESSION_SIGNING_KEY", "")).strip()
        if raw and raw.lower() not in ("none", "null"):
            return raw.encode("utf-8")
    except Exception:
        pass
    try:
        pw = st.secrets.get("passwords")
        if isinstance(pw, dict) and pw:
            return hashlib.sha256(json.dumps(pw, sort_keys=True, ensure_ascii=False).encode("utf-8")).digest()
    except Exception:
        pass
    return None


def _persist_login_to_url(user_id: str) -> None:
    """로그인 직후 URL에 서명 토큰을 붙여, 세션 ID가 바뀌어도 같은 탭에서 복구 가능하게 함."""
    secret = _session_signing_secret()
    if not secret or not user_id:
        return
    try:
        exp = int(time.time()) + LOGIN_URL_TOKEN_TTL_SEC
        body = json.dumps({"u": user_id, "exp": exp}, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        sig = hmac.new(secret, body, hashlib.sha256).hexdigest()
        token = base64.urlsafe_b64encode(body).decode("ascii").rstrip("=") + "." + sig
        st.query_params[LOGIN_URL_TOKEN_PARAM] = token
    except Exception:
        pass


def _try_restore_login_from_query() -> None:
    if st.session_state.get("logged_in", False):
        return
    secret = _session_signing_secret()
    if not secret:
        return
    try:
        token = st.query_params.get(LOGIN_URL_TOKEN_PARAM)
        if not token or "." not in token:
            return
        b64, sig = token.split(".", 1)
        pad = "=" * ((4 - len(b64) % 4) % 4)
        body = base64.urlsafe_b64decode(b64 + pad)
        expected = hmac.new(secret, body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, sig):
            return
        obj = json.loads(body.decode("utf-8"))
        uid = str(obj.get("u", "")).strip()
        exp = int(obj.get("exp", 0))
        if not uid or exp < int(time.time()):
            return
        if uid not in st.secrets.get("passwords", {}):
            return
        st.session_state["logged_in"] = True
        st.session_state["user_id"] = uid
    except Exception:
        pass


def _clear_login_url_token() -> None:
    try:
        if LOGIN_URL_TOKEN_PARAM in st.query_params:
            del st.query_params[LOGIN_URL_TOKEN_PARAM]
    except Exception:
        pass


def check_login():
    if st.session_state.get("logged_in", False):
        return True
    _try_restore_login_from_query()
    if st.session_state.get("logged_in", False):
        return True
    st.title("🏗️ PM 통합 관리 시스템")
    with st.form("login"):
        u_id = st.text_input("ID")
        u_pw = st.text_input("Password", type="password")
        if st.form_submit_button("로그인"):
            if u_id in st.secrets["passwords"] and u_pw == st.secrets["passwords"][u_id]:
                st.session_state["logged_in"] = True
                st.session_state["user_id"] = u_id
                _persist_login_to_url(u_id)
                st.rerun()
            else:
                st.error("정보 불일치")
    return False

@st.cache_resource
def get_client():
    try:
        key_dict = dict(st.secrets["gcp_service_account"])
        if "private_key" in key_dict: 
            key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")
        creds = Credentials.from_service_account_info(
            key_dict,
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ]
        )
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"구글 클라우드 연결 실패: {e}")
        return None

# -------------------------------
# [성능 개선] 구글 시트 읽기 캐시
# -------------------------------

@st.cache_data(ttl=300, show_spinner=False)
def cached_get_all_values(spreadsheet_name: str, worksheet_name: str):
    """지정 워크시트 전체 데이터를 5분간 메모리 + 파일 캐시"""
    if SHEET_CACHE_ENABLED and FILE_CACHE_TTL > 0 and spreadsheet_name == "pms_db":
        cache_path = CACHE_DIR / f"{_sheet_name_to_filename(worksheet_name)}.json"
        loaded = _load_file_cache(cache_path, FILE_CACHE_TTL)
        if loaded is not None:
            return loaded
    client = get_client()
    if client is None:
        return []
    sh = safe_api_call(client.open, spreadsheet_name)
    ws = safe_api_call(sh.worksheet, worksheet_name)
    data = safe_api_call(ws.get_all_values)
    if SHEET_CACHE_ENABLED and FILE_CACHE_TTL > 0 and spreadsheet_name == "pms_db":
        cache_path = CACHE_DIR / f"{_sheet_name_to_filename(worksheet_name)}.json"
        _save_file_cache(cache_path, data)
    return data

@st.cache_data(ttl=300, show_spinner=False)
def cached_get_all_records(spreadsheet_name: str, worksheet_name: str):
    """get_all_records 결과를 5분간 캐싱"""
    client = get_client()
    if client is None:
        return []
    sh = safe_api_call(client.open, spreadsheet_name)
    ws = safe_api_call(sh.worksheet, worksheet_name)
    return safe_api_call(ws.get_all_records)

@st.cache_data(ttl=300, show_spinner=False)
def cached_get_head(spreadsheet_name: str, worksheet_name: str, max_rows: int = 200):
    """
    대시보드용: 상단 N행(A1~J{max_rows})만 읽어서 평균 진척 계산
    → 프로젝트별 행이 많아져도 속도 유지. 파일 캐시 지원.
    """
    if SHEET_CACHE_ENABLED and FILE_CACHE_TTL > 0 and spreadsheet_name == "pms_db":
        cache_path = CACHE_DIR / f"{_sheet_name_to_filename(worksheet_name)}_head_{max_rows}.json"
        loaded = _load_file_cache(cache_path, FILE_CACHE_TTL)
        if loaded is not None:
            return loaded
    client = get_client()
    if client is None:
        return []
    sh = safe_api_call(client.open, spreadsheet_name)
    ws = safe_api_call(sh.worksheet, worksheet_name)
    rng = f"A1:J{max_rows}"
    data = safe_api_call(ws.get, rng)
    if SHEET_CACHE_ENABLED and FILE_CACHE_TTL > 0 and spreadsheet_name == "pms_db":
        cache_path = CACHE_DIR / f"{_sheet_name_to_filename(worksheet_name)}_head_{max_rows}.json"
        _save_file_cache(cache_path, data)
    return data

# -------------------------------
# [예측] Open-Meteo 기반 내일 일사량/발전시간 예측
# -------------------------------

# 지점명 자동 변환 실패 시 사용할 기본 좌표 (지점명 정확히 일치)
# 필요 시 여기에 "지점명": (위도, 경도) 추가 (예: "서산(당진)": (36.78, 126.45))
GEO_FALLBACK_COORDS = {
    "서산(당진)": (36.7840, 126.4500),
    "당진": (36.8940, 126.6290),
    "서산": (36.7840, 126.4500),
    "여주": (37.2983, 127.6370),
    "부산": (35.1796, 129.0756),
}

SOLAR_CLIMATOLOGY_YEARS = 10
SOLAR_ANALYSIS_FOCUS_YEARS = [2024, 2025]

def _geocode_one_query(query: str):
    """단일 쿼리로 Open-Meteo Geocoding 시도"""
    if not query or not query.strip():
        return None
    url = "https://geocoding-api.open-meteo.com/v1/search"
    params = {"name": query.strip(), "count": 1, "language": "ko", "format": "json"}
    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        j = r.json()
        results = j.get("results") or []
        if not results:
            return None
        top = results[0]
        return {
            "name": top.get("name"),
            "country": top.get("country"),
            "admin1": top.get("admin1"),
            "latitude": top.get("latitude"),
            "longitude": top.get("longitude"),
        }
    except Exception:
        return None

@st.cache_data(ttl=24 * 3600, show_spinner=False)
def geocode_location_open_meteo(name: str):
    """지점명 -> 위/경도 (Open-Meteo Geocoding). 여러 쿼리 변형 시도 + 사전 좌표 fallback."""
    q = str(name).strip()
    if not q:
        return None
    # 1) 사전에 등록된 좌표가 있으면 사용
    if q in GEO_FALLBACK_COORDS:
        lat, lon = GEO_FALLBACK_COORDS[q]
        return {"name": q, "country": "South Korea", "admin1": None, "latitude": lat, "longitude": lon}
    # 2) API로 쿼리 변형 여러 개 시도
    to_try = [q]
    if "(" in q and ")" in q:
        to_try.append(q.split("(")[0].strip())
        inner = q[q.index("(") + 1 : q.index(")")].strip()
        if inner:
            to_try.append(inner)
        to_try.append(q.replace("(", " ").replace(")", " ").strip())
    elif "," in q:
        for part in q.split(","):
            if part.strip():
                to_try.append(part.strip())
    seen = set()
    for query in to_try:
        query = (query or "").strip()
        if not query or query in seen:
            continue
        seen.add(query)
        result = _geocode_one_query(query)
        if result and result.get("latitude") is not None and result.get("longitude") is not None:
            return result
    return None

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_open_meteo_daily_forecast(latitude: float, longitude: float, timezone: str = "Asia/Seoul"):
    """
    일 단위 예보:
    - shortwave_radiation_sum: MJ/m² (Open-Meteo 문서 기준)
    """
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "daily": "shortwave_radiation_sum,cloud_cover_mean,temperature_2m_max,temperature_2m_min,precipitation_sum",
        "forecast_days": 7,
        "timezone": timezone,
    }
    r = requests.get(url, params=params, timeout=15)
    r.raise_for_status()
    return r.json()

def _pick_daily_value(forecast_json: dict, target_date: datetime.date, key: str):
    daily = (forecast_json or {}).get("daily") or {}
    times = daily.get("time") or []
    values = daily.get(key) or []
    if not times or not values:
        return None
    t_str = target_date.strftime("%Y-%m-%d")
    try:
        idx = times.index(t_str)
        return values[idx]
    except ValueError:
        return None


def get_location_lat_lon(name: str):
    """지점명 → (위도, 경도, geocode 정보 dict)"""
    geo = geocode_location_open_meteo(name)
    if geo and geo.get("latitude") is not None and geo.get("longitude") is not None:
        return float(geo["latitude"]), float(geo["longitude"]), geo
    return None, None, geo


@st.cache_data(ttl=7 * 24 * 3600, show_spinner=False)
def fetch_open_meteo_archive_daily(
    latitude: float,
    longitude: float,
    start_date: str,
    end_date: str,
    timezone: str = "Asia/Seoul",
):
    """Open-Meteo Archive API — 과거 일별 일사량(MJ/m²)"""
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": start_date,
        "end_date": end_date,
        "daily": "shortwave_radiation_sum",
        "timezone": timezone,
    }
    r = requests.get(url, params=params, timeout=90)
    r.raise_for_status()
    return r.json()


def archive_json_to_daily_df(archive_json: dict) -> pd.DataFrame:
    daily = (archive_json or {}).get("daily") or {}
    times = daily.get("time") or []
    rad = daily.get("shortwave_radiation_sum") or []
    if not times:
        return pd.DataFrame(columns=["날짜", "일사량합계"])
    df = pd.DataFrame(
        {
            "날짜": pd.to_datetime(times),
            "일사량합계": pd.to_numeric(rad, errors="coerce"),
        }
    )
    return df.dropna(subset=["일사량합계"])


def fetch_climatology_daily_df(latitude: float, longitude: float, end_year: int) -> pd.DataFrame:
    """직전 N년(기본 10년) 일별 일사량 reanalysis 데이터"""
    start_year = end_year - SOLAR_CLIMATOLOGY_YEARS
    start_date = f"{start_year}-01-01"
    end_date = f"{end_year - 1}-12-31"
    try:
        archive = fetch_open_meteo_archive_daily(latitude, longitude, start_date, end_date)
        return archive_json_to_daily_df(archive)
    except Exception:
        return pd.DataFrame(columns=["날짜", "일사량합계"])


def build_monthly_climatology(daily_df: pd.DataFrame) -> pd.DataFrame:
    """10년 일별 데이터 → 월별 평균 일사량(기후값)"""
    if daily_df is None or daily_df.empty:
        return pd.DataFrame(columns=["월", "기후_월평균_일사량"])
    tmp = daily_df.copy()
    tmp["월"] = tmp["날짜"].dt.month
    monthly = (
        tmp.groupby("월", as_index=False)["일사량합계"]
        .mean()
        .rename(columns={"일사량합계": "기후_월평균_일사량"})
    )
    monthly["월"] = monthly["월"].astype(int)
    return monthly.sort_values("월")


def summarize_yearly_radiation(actual_df: pd.DataFrame, years: list) -> pd.DataFrame:
    """실측(또는 시트) 데이터의 연도별 일평균·연합계 일사량"""
    if actual_df is None or actual_df.empty:
        return pd.DataFrame()
    tmp = actual_df.copy()
    tmp["연도"] = tmp["날짜"].dt.year
    rows = []
    for yr in years:
        sub = tmp[tmp["연도"] == yr]
        if sub.empty:
            continue
        rows.append(
            {
                "연도": int(yr),
                "일수": len(sub),
                "일평균_일사량": round(float(sub["일사량합계"].mean()), 2),
                "연합계_일사량": round(float(sub["일사량합계"].sum()), 1),
                "일평균_발전시간": round(float(sub["발전시간"].mean()), 2) if "발전시간" in sub.columns else None,
            }
        )
    return pd.DataFrame(rows)


def build_yearly_vs_climatology_table(
    actual_df: pd.DataFrame,
    clim_daily_df: pd.DataFrame,
    years: list = None,
) -> pd.DataFrame:
    """연도별 실측 일평균 일사량 vs 직전 10년 기후 평균 비교표"""
    if years is None:
        years = SOLAR_ANALYSIS_FOCUS_YEARS
    if clim_daily_df is None or clim_daily_df.empty:
        return pd.DataFrame()
    climate_daily_mean = float(clim_daily_df["일사량합계"].mean())
    climate_annual_sum = float(clim_daily_df.groupby(clim_daily_df["날짜"].dt.year)["일사량합계"].sum().mean())
    yearly = summarize_yearly_radiation(actual_df, years)
    if yearly.empty:
        return pd.DataFrame()
    yearly["기후_10년_일평균"] = round(climate_daily_mean, 2)
    yearly["기후_10년_연평균합계"] = round(climate_annual_sum, 1)
    yearly["일평균_편차(MJ/m²)"] = (yearly["일평균_일사량"] - yearly["기후_10년_일평균"]).round(2)
    yearly["일평균_편차(%)"] = (
        (yearly["일평균_일사량"] / yearly["기후_10년_일평균"] - 1.0) * 100.0
    ).round(1)
    yearly["연합계_편차(%)"] = (
        (yearly["연합계_일사량"] / yearly["기후_10년_연평균합계"] - 1.0) * 100.0
    ).round(1)
    return yearly


def build_monthly_comparison_df(
    actual_df: pd.DataFrame,
    clim_monthly_df: pd.DataFrame,
    years: list = None,
) -> pd.DataFrame:
    """월별: 10년 기후평균 vs 지정 연도(2024·2025 등) 실측 월평균"""
    if years is None:
        years = SOLAR_ANALYSIS_FOCUS_YEARS
    if actual_df is None or actual_df.empty or clim_monthly_df is None or clim_monthly_df.empty:
        return pd.DataFrame()
    tmp = actual_df.copy()
    tmp["월"] = tmp["날짜"].dt.month
    tmp["연도"] = tmp["날짜"].dt.year
    out = clim_monthly_df.copy()
    for yr in years:
        sub = tmp[tmp["연도"] == yr]
        if sub.empty:
            continue
        m = sub.groupby("월", as_index=False)["일사량합계"].mean().rename(
            columns={"일사량합계": f"{yr}년_월평균"}
        )
        out = out.merge(m, on="월", how="left")
    return out.sort_values("월")


def estimate_generation_hours_from_radiation(radiation_mj_m2: float, ref_df: pd.DataFrame = None) -> float:
    """발전시간 추정 — 참조 지점 회귀식 우선, 없으면 PR 0.8"""
    if ref_df is not None and not ref_df.empty:
        pred, _, _ = fit_predict_generation_hours(ref_df, radiation_mj_m2)
        return pred
    return max(0.0, min(24.0, float((radiation_mj_m2 / 3.6) * 0.8)))


def build_solar_db_rows_from_archive(
    location_name: str,
    archive_df: pd.DataFrame,
    ref_df: pd.DataFrame = None,
) -> list:
    """Archive 일사량 → Solar_DB 저장용 행 목록"""
    rows = []
    for _, r in archive_df.iterrows():
        rad = float(r["일사량합계"])
        gen_h = estimate_generation_hours_from_radiation(rad, ref_df)
        rows.append(
            [
                pd.Timestamp(r["날짜"]).strftime("%Y-%m-%d"),
                str(location_name),
                round(gen_h, 2),
                round(rad, 2),
            ]
        )
    return rows


def append_solar_db_rows(sh, rows: list, overwrite_location_dates: bool = True) -> int:
    """Solar_DB 시트에 발전량 행 추가 (동일 지점·날짜 덮어쓰기 옵션)"""
    if not rows:
        return 0
    try:
        ws = safe_api_call(sh.worksheet, "Solar_DB")
    except WorksheetNotFound:
        ws = safe_api_call(sh.add_worksheet, title="Solar_DB", rows="5000", cols="10")
        safe_api_call(ws.append_row, ["날짜", "지점", "발전시간", "일사량합계"])
    existing = safe_api_call(ws.get_all_values)
    header = existing[0] if existing else ["날짜", "지점", "발전시간", "일사량합계"]
    upload_dates_by_loc = {}
    for row in rows:
        if len(row) >= 2:
            upload_dates_by_loc.setdefault(str(row[1]).strip(), set()).add(str(row[0])[:10])
    if overwrite_location_dates and existing and len(existing) > 1:
        kept = [header]
        for row in existing[1:]:
            if len(row) < 2:
                kept.append(row)
                continue
            d = str(row[0]).strip()[:10]
            loc = str(row[1]).strip()
            if loc in upload_dates_by_loc and d in upload_dates_by_loc[loc]:
                continue
            kept.append(row)
        safe_api_call(ws.clear)
        if kept:
            safe_api_call(ws.update, "A1", kept)
    for row in rows:
        safe_api_call(ws.append_row, row, value_input_option="USER_ENTERED")
    cached_get_all_records.clear()
    return len(rows)


def render_solar_climatology_analysis(sel_loc: str, f_df: pd.DataFrame, df_db: pd.DataFrame):
    """연평균 일사량 vs 과거 10년 평균 분석 (2024·2025 중심)"""
    st.subheader("📈 연평균 일사량 vs 과거 10년 평균")
    st.caption(
        f"**{sel_loc}** 지점의 **2024·2025년** 실측(시트) 일사량을 "
        f"Open-Meteo 재분석 기반 **직전 {SOLAR_CLIMATOLOGY_YEARS}년({SOLAR_ANALYSIS_FOCUS_YEARS[0]-SOLAR_CLIMATOLOGY_YEARS}~{SOLAR_ANALYSIS_FOCUS_YEARS[0]-1})** "
        "기후 평균과 비교합니다. (기상청 실측과 reanalysis 간 오차가 있을 수 있습니다.)"
    )
    lat, lon, geo = get_location_lat_lon(sel_loc)
    if lat is None or lon is None:
        st.warning("좌표를 찾지 못해 10년 평균 비교를 할 수 없습니다. `GEO_FALLBACK_COORDS`에 지점을 등록하세요.")
        return

    place = " / ".join([str(x) for x in [geo.get("name"), geo.get("admin1"), geo.get("country")] if x]) if geo else sel_loc
    st.caption(f"분석 좌표: {place} (lat={lat:.4f}, lon={lon:.4f})")

    baseline_end_year = max(SOLAR_ANALYSIS_FOCUS_YEARS)
    with st.spinner(f"과거 {SOLAR_CLIMATOLOGY_YEARS}년 일사량 기후 데이터 조회 중…"):
        clim_daily = fetch_climatology_daily_df(lat, lon, baseline_end_year)
    if clim_daily.empty:
        st.error("10년 기후 데이터를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.")
        return

    clim_monthly = build_monthly_climatology(clim_daily)
    loc_all = df_db[df_db["지점"] == sel_loc].copy() if df_db is not None and not df_db.empty else f_df.copy()
    if loc_all.empty:
        compare_years = []
    else:
        compare_years = [y for y in SOLAR_ANALYSIS_FOCUS_YEARS if y in loc_all["날짜"].dt.year.unique()]
        if not compare_years:
            yrs = sorted(loc_all["날짜"].dt.year.unique().tolist())
            compare_years = yrs[-2:] if yrs else []
    yearly_tbl = build_yearly_vs_climatology_table(loc_all, clim_daily, compare_years)

    if yearly_tbl.empty:
        st.info(f"{sel_loc} 지점의 2024·2025년(또는 비교 대상 연도) 데이터가 없습니다. 아래 **지역 데이터 생성**에서 먼저 데이터를 만드세요.")
    else:
        c1, c2 = st.columns(2)
        for i, (_, row) in enumerate(yearly_tbl.iterrows()):
            col = c1 if i % 2 == 0 else c2
            delta_pct = row["일평균_편차(%)"]
            col.metric(
                f"{int(row['연도'])}년 일평균 일사량",
                f"{row['일평균_일사량']:.2f} MJ/m²",
                delta=f"{delta_pct:+.1f}% vs 10년 평균",
                delta_color="normal" if delta_pct >= 0 else "inverse",
            )
        st.dataframe(
            yearly_tbl.rename(
                columns={
                    "일평균_일사량": "실측_일평균",
                    "연합계_일사량": "실측_연합계",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )

        fig_year = go.Figure()
        fig_year.add_trace(
            go.Bar(
                x=[f"{int(y)}년" for y in yearly_tbl["연도"]],
                y=yearly_tbl["일평균_일사량"],
                name="실측 일평균",
                marker_color=["#1976d2", "#42a5f5"][: len(yearly_tbl)],
                text=yearly_tbl["일평균_편차(%)"].apply(lambda v: f"{v:+.1f}%"),
                textposition="outside",
            )
        )
        fig_year.add_hline(
            y=float(yearly_tbl["기후_10년_일평균"].iloc[0]),
            line_dash="dash",
            line_color="#ef5350",
            annotation_text=f"10년 평균 {yearly_tbl['기후_10년_일평균'].iloc[0]:.2f}",
            annotation_position="top right",
        )
        fig_year.update_layout(
            title=f"[{sel_loc}] 연도별 일평균 일사량 vs 10년 기후 평균",
            yaxis_title="일평균 일사량 (MJ/m²)",
            height=380,
            showlegend=False,
        )
        st.plotly_chart(fig_year, use_container_width=True)

    monthly_cmp = build_monthly_comparison_df(loc_all, clim_monthly, compare_years)
    if not monthly_cmp.empty:
        fig_m = go.Figure()
        fig_m.add_trace(
            go.Scatter(
                x=monthly_cmp["월"],
                y=monthly_cmp["기후_월평균_일사량"],
                mode="lines+markers",
                name=f"10년 월평균 ({baseline_end_year - SOLAR_CLIMATOLOGY_YEARS}~{baseline_end_year - 1})",
                line=dict(color="#ef5350", width=3, dash="dash"),
            )
        )
        palette = ["#1976d2", "#66bb6a", "#ffa726"]
        for i, yr in enumerate(compare_years):
            col_name = f"{yr}년_월평균"
            if col_name in monthly_cmp.columns:
                fig_m.add_trace(
                    go.Bar(
                        x=monthly_cmp["월"],
                        y=monthly_cmp[col_name],
                        name=f"{yr}년 실측",
                        marker_color=palette[i % len(palette)],
                        opacity=0.85,
                    )
                )
        fig_m.update_layout(
            title=f"[{sel_loc}] 월별 일평균 일사량 — 10년 기후평균 vs 실측",
            xaxis_title="월",
            yaxis_title="월평균 일사량 (MJ/m²)",
            barmode="group",
            height=420,
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
        )
        st.plotly_chart(fig_m, use_container_width=True)
        st.dataframe(monthly_cmp, use_container_width=True, hide_index=True)


def render_yeoju_data_builder(sh, df_db: pd.DataFrame):
    """여주(및 신규 지점) Archive 기반 발전량·일사량 데이터 생성 → Solar_DB 저장"""
    st.subheader("🏗️ 신규 지역 데이터 생성 (여주 등)")
    st.caption(
        "Open-Meteo 과거 재분석 일사량으로 **일사량합계**를 채우고, "
        "참조 지점 회귀식(또는 PR 0.8)으로 **발전시간**을 추정해 `Solar_DB`에 저장합니다. "
        "실제 발전량이 확보되면 시트에서 발전시간만 수정하세요."
    )
    preset_locs = sorted(set(list(GEO_FALLBACK_COORDS.keys()) + ["여주"]))
    db_locs = sorted(df_db["지점"].dropna().astype(str).unique().tolist()) if df_db is not None and not df_db.empty else []
    new_loc = st.selectbox(
        "생성할 지점",
        preset_locs,
        index=preset_locs.index("여주") if "여주" in preset_locs else 0,
        key="solar_new_loc_builder",
    )
    if new_loc in db_locs:
        st.info(f"`{new_loc}` 데이터가 이미 Solar_DB에 있습니다. 저장 시 **같은 날짜는 덮어씁니다.**")

    b1, b2, b3 = st.columns(3)
    with b1:
        gen_start = st.date_input("시작일", value=datetime.date(2024, 1, 1), key="solar_gen_start")
    with b2:
        gen_end = st.date_input("종료일", value=datetime.date(2025, 12, 31), key="solar_gen_end")
    with b3:
        ref_opts = ["PR 0.8 추정"] + [loc for loc in db_locs if loc != new_loc]
        ref_loc = st.selectbox("발전시간 추정 참조", ref_opts, key="solar_gen_ref")

    lat, lon, geo = get_location_lat_lon(new_loc)
    if lat is None:
        st.error(f"`{new_loc}` 좌표를 찾지 못했습니다. `GEO_FALLBACK_COORDS`에 추가해 주세요.")
        return
    st.caption(f"좌표: lat={lat:.4f}, lon={lon:.4f}")

    ref_df = None
    if ref_loc != "PR 0.8 추정" and df_db is not None and not df_db.empty:
        ref_df = df_db[df_db["지점"] == ref_loc].copy()

    if st.button("🔍 미리보기 (다운로드 없이 조회)", key="solar_gen_preview", use_container_width=True):
        with st.spinner("Archive 일사량 조회 중…"):
            archive = fetch_open_meteo_archive_daily(
                lat, lon, gen_start.strftime("%Y-%m-%d"), gen_end.strftime("%Y-%m-%d")
            )
            preview_df = archive_json_to_daily_df(archive)
        if preview_df.empty:
            st.warning("해당 기간 데이터가 없습니다.")
        else:
            preview_df = preview_df.copy()
            preview_df["발전시간"] = preview_df["일사량합계"].apply(
                lambda v: estimate_generation_hours_from_radiation(float(v), ref_df)
            )
            preview_df["지점"] = new_loc
            st.metric("생성 일수", f"{len(preview_df)}일")
            st.metric("기간 일평균 일사량", f"{preview_df['일사량합계'].mean():.2f} MJ/m²")
            st.metric("기간 일평균 발전시간(추정)", f"{preview_df['발전시간'].mean():.2f} h")
            st.dataframe(preview_df.tail(30), use_container_width=True)
            st.session_state[f"solar_gen_preview_{new_loc}"] = preview_df

    if st.button("💾 Solar_DB에 저장", type="primary", key="solar_gen_save", use_container_width=True):
        with st.spinner("데이터 생성 및 저장 중…"):
            archive = fetch_open_meteo_archive_daily(
                lat, lon, gen_start.strftime("%Y-%m-%d"), gen_end.strftime("%Y-%m-%d")
            )
            archive_df = archive_json_to_daily_df(archive)
            if archive_df.empty:
                st.error("저장할 데이터가 없습니다.")
            else:
                rows = build_solar_db_rows_from_archive(new_loc, archive_df, ref_df)
                cnt = append_solar_db_rows(sh, rows, overwrite_location_dates=True)
                st.success(f"`{new_loc}` {cnt}건을 Solar_DB에 저장했습니다. 상단에서 지역을 새로고침 후 10년 비교 분석을 확인하세요.")
                time.sleep(1)
                st.rerun()


def fit_predict_generation_hours(hist_df: pd.DataFrame, radiation_mj_m2: float):
    """
    과거(실제) 데이터를 활용해 '일사량합계(MJ/m²) -> 발전시간(h)'로 회귀/비율 기반 예측
    반환: (pred_hours, method, r2_or_none)
    """
    try:
        x = pd.to_numeric(hist_df.get("일사량합계"), errors="coerce")
        y = pd.to_numeric(hist_df.get("발전시간"), errors="coerce")
        m = x.notna() & y.notna()
        if m.sum() >= 12:
            # 1차 선형회귀
            a, b = np.polyfit(x[m].to_numpy(), y[m].to_numpy(), 1)
            yhat = a * x[m] + b
            ss_res = float(((y[m] - yhat) ** 2).sum())
            ss_tot = float(((y[m] - y[m].mean()) ** 2).sum())
            r2 = None if ss_tot <= 0 else (1.0 - (ss_res / ss_tot))
            pred = float(a * radiation_mj_m2 + b)
            pred = max(0.0, min(24.0, pred))
            return pred, "linear_regression", r2

        # 비율 기반(발전시간 / (kWh/m²)) 평균으로 추정
        if m.sum() >= 5:
            kwh_m2 = (x[m] / 3.6).replace([np.inf, -np.inf], np.nan)
            ratio = (y[m] / kwh_m2).replace([np.inf, -np.inf], np.nan).dropna()
            if len(ratio) >= 5:
                r = float(ratio.clip(lower=0).median())
                pred = float((radiation_mj_m2 / 3.6) * r)
                pred = max(0.0, min(24.0, pred))
                return pred, "ratio_median", None

        # 마지막 fallback (기존 로직과 유사)
        pred = float((radiation_mj_m2 / 3.6) * 0.8)
        pred = max(0.0, min(24.0, pred))
        return pred, "fallback_pr0.8", None
    except Exception:
        pred = float((radiation_mj_m2 / 3.6) * 0.8)
        pred = max(0.0, min(24.0, pred))
        return pred, "fallback_pr0.8", None

def calc_planned_progress(start, end, target_date=None):
    if target_date is None: 
        target_date = datetime.date.today()
    try:
        s = pd.to_datetime(start).date()
        e = pd.to_datetime(end).date()
        if pd.isna(s) or pd.isna(e): 
            return 0.0
        if target_date < s: 
            return 0.0
        if target_date > e: 
            return 100.0
        total_days = (e - s).days
        if total_days <= 0: 
            return 100.0
        passed_days = (target_date - s).days
        return min(100.0, max(0.0, (passed_days / total_days) * 100))
    except: 
        return 0.0


def _task_duration_days(start, end) -> float:
    """공정 1건의 가중치 = 일정 기간(일). 날짜 없으면 1일."""
    try:
        s = pd.to_datetime(start, errors="coerce")
        e = pd.to_datetime(end, errors="coerce")
        if pd.isna(s) or pd.isna(e):
            return 1.0
        days = abs((pd.Timestamp(e) - pd.Timestamp(s)).days)
        return float(max(1, days))
    except Exception:
        return 1.0


def calc_weighted_progress_mean(df: pd.DataFrame, progress_values: pd.Series) -> float:
    """
    공정 진행률의 기간 가중 평균.
    실적% = Σ(진행률 × 공정일수) / Σ(공정일수)
    """
    if df is None or df.empty or progress_values is None or len(progress_values) == 0:
        return 0.0
    p = pd.to_numeric(progress_values, errors="coerce").fillna(0).astype(float)
    if len(df) != len(p):
        return float(p.mean())
    weights = df.apply(
        lambda r: _task_duration_days(r.get("시작일"), r.get("종료일")),
        axis=1,
    ).astype(float)
    total_w = float(weights.sum())
    if total_w <= 0:
        return float(p.mean())
    return float((p * weights).sum() / total_w)


def calc_weighted_actual_progress(df: pd.DataFrame) -> float:
    """실적(실행) 진행률 — 기간 가중 평균"""
    if df.empty or "진행률" not in df.columns:
        return 0.0
    return round(calc_weighted_progress_mean(df, df["진행률"]), 1)


def calc_weighted_planned_progress(df: pd.DataFrame, target_date=None) -> float:
    """계획 진행률 — 기간 가중 평균"""
    if df.empty:
        return 0.0
    planned = df.apply(
        lambda r: calc_planned_progress(r.get("시작일"), r.get("종료일"), target_date),
        axis=1,
    )
    return round(calc_weighted_progress_mean(df, planned), 1)


def navigate_to_project(p_name):
    st.session_state.selected_menu = "프로젝트 상세"
    st.session_state.selected_pjt = p_name

def set_top_menu(menu_name: str):
    """상단 메뉴 클릭 시 선택 메뉴 변경 (콜백 종료 후 Streamlit이 자동 리런)"""
    st.session_state.selected_menu = menu_name


SCHEDULE_COLUMNS = ["시작일", "종료일", "대분류", "구분", "진행상태", "비고", "진행률"]


def _sheet_data_signature(data: list) -> str:
    """구글 시트 원본 데이터 변경 여부 감지용 (엑셀 업로드 후 화면 갱신)"""
    try:
        payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        return hashlib.md5(payload.encode("utf-8")).hexdigest()
    except Exception:
        return str(time.time())


def invalidate_process_edit_cache(project_names=None):
    """엑셀 업로드·시트 동기화 후 프로젝트 상세 편집기 세션 캐시 무효화"""
    if project_names is None:
        st.session_state.pop("process_edit_df", None)
        st.session_state.pop("process_edit_pjt", None)
        st.session_state.pop("process_edit_invalidated_pjts", None)
        return
    names = {str(p).strip() for p in project_names if str(p).strip()}
    if not names:
        return
    invalidated = set(st.session_state.get("process_edit_invalidated_pjts") or [])
    invalidated.update(names)
    st.session_state["process_edit_invalidated_pjts"] = invalidated
    if st.session_state.get("process_edit_pjt") in names:
        st.session_state.pop("process_edit_df", None)
        st.session_state.pop("process_edit_pjt", None)


def _excel_cell_to_sheet_str(val) -> str:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    if isinstance(val, (datetime.date, datetime.datetime)):
        return val.strftime("%Y-%m-%d")
    if hasattr(val, "strftime"):
        try:
            return val.strftime("%Y-%m-%d")
        except Exception:
            pass
    s = str(val).strip()
    if not s or s.lower() in ("nan", "none", "nat"):
        return ""
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        return s[:10]
    try:
        parsed = pd.to_datetime(s, errors="coerce")
        if pd.notna(parsed):
            return parsed.strftime("%Y-%m-%d")
    except Exception:
        pass
    return s


def _normalize_excel_schedule_df(df_up: pd.DataFrame) -> pd.DataFrame:
    """엑셀 시트 → 공정표 A~G열 DataFrame (헤더·빈행·날짜 형식 정리)"""
    if df_up is None or df_up.empty:
        return pd.DataFrame(columns=SCHEDULE_COLUMNS)

    df = df_up.copy()
    df.columns = [str(c).strip() for c in df.columns]
    rename_map = {}
    for i, col in enumerate(df.columns):
        if col in SCHEDULE_COLUMNS:
            rename_map[col] = col
        elif i < len(SCHEDULE_COLUMNS):
            rename_map[col] = SCHEDULE_COLUMNS[i]
    df = df.rename(columns=rename_map)
    for col in SCHEDULE_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    df = df[SCHEDULE_COLUMNS]
    df = df.dropna(how="all")
    df = df[~df.apply(lambda r: str(r.get("시작일", "")).strip() == "시작일", axis=1)]

    for col in ("시작일", "종료일"):
        df[col] = df[col].apply(_excel_cell_to_sheet_str)
    for col in ("대분류", "구분", "진행상태", "비고"):
        df[col] = df[col].apply(
            lambda v: "" if pd.isna(v) else str(v).strip().replace("nan", "").replace("None", "")
        )
    df["진행률"] = pd.to_numeric(df["진행률"], errors="coerce").fillna(0)
    return df.reset_index(drop=True)


def _extract_pm_weekly_from_sheet_rows(existing_rows: list):
    pm, this_w, next_w = "", "", ""
    if len(existing_rows) > 1:
        row = existing_rows[1]
        if len(row) > 7:
            pm = str(row[7]).strip()
        if len(row) > 8:
            this_w = str(row[8]).strip()
        if len(row) > 9:
            next_w = str(row[9]).strip()
    return pm, this_w, next_w


def _schedule_df_to_sheet_rows(df: pd.DataFrame, pm: str = "", this_w: str = "", next_w: str = "") -> list:
    """공정표 DataFrame → 구글 시트 A1 형식 (헤더 + PM/금주/차주 열 포함)"""
    header = SCHEDULE_COLUMNS + ["PM", "금주", "차주"]
    rows = [header]
    if df.empty:
        rows.append([""] * 7 + [pm, this_w, next_w])
        return rows
    for i, (_, row) in enumerate(df.iterrows()):
        r7 = [_excel_cell_to_sheet_str(row[c]) for c in SCHEDULE_COLUMNS]
        r7[6] = str(int(row["진행률"])) if pd.notna(row["진행률"]) else "0"
        if i == 0:
            r7.extend([pm, this_w, next_w])
        else:
            r7.extend([pm, "", ""])
        rows.append(r7)
    return rows


def sync_worksheet_from_excel_df(ws, df_up: pd.DataFrame) -> int:
    """엑셀 DataFrame을 프로젝트 시트 형식에 맞게 업로드 (PM·금주·차주 유지)"""
    existing = safe_api_call(ws.get_all_values)
    pm, this_w, next_w = _extract_pm_weekly_from_sheet_rows(existing)
    df_norm = _normalize_excel_schedule_df(df_up)
    full_data = _schedule_df_to_sheet_rows(df_norm, pm, this_w, next_w)
    safe_api_call(ws.clear)
    safe_api_call(ws.update, "A1", full_data)
    return len(df_norm)


def _gantt_month_labels(min_d: pd.Timestamp, max_d: pd.Timestamp) -> list:
    """간트 상단 월 눈금 라벨 (26.4 형식)"""
    start = pd.Timestamp(year=min_d.year, month=min_d.month, day=1)
    end = pd.Timestamp(year=max_d.year, month=max_d.month, day=1)
    months = pd.date_range(start, end, freq="MS")
    if len(months) == 0:
        return [f"{min_d.year % 100}.{min_d.month}"]
    return [f"{d.year % 100}.{d.month}" for d in months]


def _render_gantt_month_ruler(min_d: pd.Timestamp, max_d: pd.Timestamp) -> None:
    """차트 본문 스크롤 시에도 남는 상단 월(년.월) 눈금 — 엑셀 틀 고정 상단 행과 유사"""
    labels = _gantt_month_labels(min_d, max_d)
    cells = "".join(f'<span class="gantt-month-cell">{lbl}</span>' for lbl in labels)
    st.markdown(
        f"""
        <div class="gantt-freeze-panel">
            <div class="gantt-month-ruler-wrap">
                <div class="gantt-month-ruler-spacer" title="공정명 영역"></div>
                <div class="gantt-month-ruler-track">{cells}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_print_button():
    """자바스크립트를 이용해 브라우저 인쇄(PDF 저장) 창을 띄우는 버튼"""
    components.html(
        """
        <script>
            function printApp() {
                window.parent.print();
            }
        </script>
        <style>
            body { margin: 0; padding: 0; background-color: transparent; }
            .print-btn {
                float: right;
                background-color: #f8f9fa;
                color: #212529;
                border: 1px solid #dee2e6;
                padding: 6px 14px;
                border-radius: 6px;
                font-size: 13px;
                font-weight: bold;
                cursor: pointer;
                font-family: sans-serif;
                box-shadow: 0 1px 2px rgba(0,0,0,0.05);
                transition: all 0.2s;
            }
            .print-btn:hover {
                background-color: #e9ecef;
                border-color: #ced4da;
            }
        </style>
        <button class="print-btn" onclick="printApp()">🖨️ PDF 저장 / 인쇄</button>
        """,
        height=40
    )

# ---------------------------------------------------------
# [SECTION 2] 뷰(View) 함수
# ---------------------------------------------------------

def build_project_status_report_df(pjt_list):
    """
    구글 시트 프로젝트 탭과 동일 규칙으로 집계 (통합 대시보드와 동일 데이터 소스).
    - PM/금주/차주: 2행 H,I,J
    - 진행률: 공정표 '진행률' 열 기간(일정) 가중 평균, 계획: 시작~종료일 기준 calc_planned_progress 기간 가중 평균
    """
    def _extract_capacity_mw(project_name: str):
        """
        프로젝트명 끝의 용량 표기에서 MW 추출.
        예) '..._1MW', '..._0.4MW', '... 2MW' -> 1.0, 0.4, 2.0
        """
        s = str(project_name or "").strip()
        if not s:
            return ""
        m = re.search(r"(?:[_\s-])(\d+(?:\.\d+)?)\s*mw\s*$", s, flags=re.IGNORECASE)
        if not m:
            return ""
        try:
            return float(m.group(1))
        except Exception:
            return ""

    rows = []
    for p_name in pjt_list:
        try:
            data = cached_get_head("pms_db", p_name, max_rows=200)
            pm_name = "미지정"
            this_w = "금주 실적 미입력"
            next_w = "차주 계획 미입력"
            if len(data) > 0:
                header = data[0][:7]
                df = (
                    pd.DataFrame([r[:7] for r in data[1:]], columns=header)
                    if len(data) > 1
                    else pd.DataFrame(columns=header)
                )
                if len(data) > 1 and len(data[1]) > 7 and str(data[1][7]).strip():
                    pm_name = str(data[1][7]).strip()
                if len(data) > 1 and len(data[1]) > 8 and str(data[1][8]).strip():
                    this_w = str(data[1][8]).strip()
                if len(data) > 1 and len(data[1]) > 9 and str(data[1][9]).strip():
                    next_w = str(data[1][9]).strip()
            else:
                df = pd.DataFrame()
            if not df.empty and "진행률" in df.columns:
                avg_act = calc_weighted_actual_progress(df)
                avg_plan = calc_weighted_planned_progress(df)
            else:
                avg_act = 0.0
                avg_plan = 0.0
            status_ui = "정상"
            if (avg_plan - avg_act) >= 10:
                status_ui = "지연"
            elif avg_act >= 100:
                status_ui = "완료"
            rows.append(
                {
                    "프로젝트명": p_name,
                    "용량(MW)": _extract_capacity_mw(p_name),
                    "담당자": pm_name,
                    "진행률_실적%": avg_act,
                    "계획진행률%": avg_plan,
                    "상태": status_ui,
                    "금주_주요": this_w,
                    "차주_주요": next_w,
                }
            )
        except Exception:
            pass
    return pd.DataFrame(rows)


def _gemini_api_key():
    """Cloud Secrets / 로컬 secrets.toml / 환경변수 순으로 후보를 읽음 (이름 오타·앱 혼동 완화)."""

    def _clean(val):
        if val is None:
            return ""
        s = str(val).strip()
        if not s or s.lower() in ("none", "null", "your-api-key-here"):
            return ""
        return s

    k = _clean(os.environ.get("GEMINI_API_KEY"))
    if k:
        return k

    try:
        if "GEMINI_API_KEY" in st.secrets:
            k = _clean(st.secrets["GEMINI_API_KEY"])
            if k:
                return k
        g = st.secrets.get("gemini") or {}
        if isinstance(g, dict):
            k = _clean(g.get("api_key"))
            if k:
                return k
        if "GOOGLE_API_KEY" in st.secrets:
            k = _clean(st.secrets["GOOGLE_API_KEY"])
            if k:
                return k
    except Exception:
        pass
    return ""


def _gemini_key_debug_hint() -> str:
    """키 값은 노출하지 않고, 어떤 경로에 값이 있는지만 표시 (Cloud 설정 확인용)."""
    parts = []
    env_set = bool((os.environ.get("GEMINI_API_KEY") or "").strip())
    parts.append(f"- 환경변수 `GEMINI_API_KEY`: {'있음' if env_set else '없음'}")
    try:
        sk = st.secrets.get("GEMINI_API_KEY")
        parts.append(
            f"- Secrets 최상위 `GEMINI_API_KEY`: {'있음(비어 있지 않음)' if sk is not None and str(sk).strip() else '없음 또는 빈 값'}"
        )
        g = st.secrets.get("gemini")
        if isinstance(g, dict):
            ga = g.get("api_key")
            parts.append(
                f"- `[gemini]` → `api_key`: {'있음' if ga is not None and str(ga).strip() else '없음'}"
            )
        gk = st.secrets.get("GOOGLE_API_KEY")
        parts.append(
            f"- `GOOGLE_API_KEY` (별칭): {'있음' if gk is not None and str(gk).strip() else '없음'}"
        )
    except Exception as e:
        parts.append(f"- Secrets 읽기 예외: `{e}`")
    parts.append(
        f"**→ 앱이 실제 사용할 키: {'인식됨' if _gemini_api_key() else '아직 없음'}**"
    )
    return "\n".join(parts)


def _gemini_user_facing_error(exc: BaseException) -> str:
    """화면에 키·전체 URL이 노출되지 않도록 정리 (스크린샷 유출 방지)."""
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        code = exc.response.status_code
        if code == 429:
            return (
                "Gemini **요청 한도(429)**에 걸렸습니다. API 키는 이미 전달된 상태입니다. "
                "1~5분 뒤 다시 시도하거나, [Google AI Studio](https://aistudio.google.com/)에서 "
                "**사용량·무료 한도**를 확인하세요. (테스트를 짧은 간격으로 많이 누르면 자주 발생합니다.)"
            )
        if code == 403:
            return "Gemini **접근 거부(403)**입니다. API 키 활성화·제한(지역/IP)을 확인하세요."
        if code == 400:
            return "Gemini **요청 오류(400)**입니다. 잠시 후 다시 시도해 주세요."
        return f"Gemini HTTP 오류 ({code}). 잠시 후 다시 시도해 주세요."
    s = str(exc)
    s = re.sub(r"key=AIza[A-Za-z0-9_-]{10,}", "key=(숨김)", s)
    s = re.sub(r"\?key=[^&\s\"']+", "?key=(숨김)", s)
    return f"Gemini API 오류: {s}"


def call_gemini_summarize_table(df_report: pd.DataFrame):
    """
    금주/차주 텍스트를 핵심 위주로 짧게 요약한 열을 추가한 표 반환.
    secrets: GEMINI_API_KEY 또는 [gemini] api_key
    """
    key = _gemini_api_key()
    if not key:
        return (
            None,
            "Gemini API 키를 찾지 못했습니다. **같은 앱**(예: `pjt`의 Secrets)에 "
            "`GEMINI_API_KEY = \"...\"` 가 있는지 확인하고, 저장 후 **Reboot** 하세요. "
            "아래 Expander의 진단 표를 참고하세요.",
        )
    if df_report.empty:
        return None, "요약할 데이터가 없습니다."
    payload = df_report[
        ["프로젝트명", "담당자", "진행률_실적%", "금주_주요", "차주_주요"]
    ].to_dict(orient="records")
    prompt = (
        "다음은 프로젝트 주간보고 표(JSON)입니다. 각 항목에 대해 "
        "'금주_주요_요약', '차주_주요_요약'을 각각 불릿 2~4개 이내로 한국어로 압축하세요. "
        "원문에 없는 내용은 만들지 마세요. "
        "응답은 반드시 JSON 배열만 출력하세요. 키: 프로젝트명, 금주_주요_요약, 차주_주요_요약.\n\n"
        + json.dumps(payload, ensure_ascii=False)
    )
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
    j = None
    for attempt in range(5):
        try:
            r = requests.post(
                url,
                params={"key": key},
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0.2, "maxOutputTokens": 8192},
                },
                timeout=120,
            )
            if r.status_code == 429:
                if attempt < 4:
                    time.sleep(min(45, 3 * (2**attempt)))
                    continue
                he = requests.HTTPError()
                he.response = r
                return None, _gemini_user_facing_error(he)
            r.raise_for_status()
            j = r.json()
            break
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 429 and attempt < 4:
                time.sleep(min(45, 3 * (2**attempt)))
                continue
            return None, _gemini_user_facing_error(e)
        except Exception as e:
            return None, _gemini_user_facing_error(e)
    if j is None:
        return None, "Gemini 응답을 받지 못했습니다."
    try:
        text = j["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError) as e:
        return None, _gemini_user_facing_error(e)
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        if "```" in text:
            text = text.rsplit("```", 1)[0]
        text = text.strip()
    try:
        arr = json.loads(text)
    except json.JSONDecodeError:
        return None, "Gemini 응답을 JSON으로 파싱하지 못했습니다. 다시 시도해 주세요."
    sum_df = pd.DataFrame(arr)
    if sum_df.empty or "프로젝트명" not in sum_df.columns:
        return None, "요약 결과 형식이 올바르지 않습니다."
    out = df_report.merge(
        sum_df[["프로젝트명", "금주_주요_요약", "차주_주요_요약"]],
        on="프로젝트명",
        how="left",
    )
    return out, None


# 1. 통합 대시보드
def view_dashboard(sh, pjt_list):
    if "dashboard_report_font_size" not in st.session_state:
        st.session_state.dashboard_report_font_size = 12
    col_title, col_right = st.columns([7, 2])
    with col_title:
        st.title("📊 통합 대시보드 (현황 브리핑)")
    with col_right:
        render_print_button()
        report_font = st.slider("📝 보고 글자 크기", min_value=10, max_value=20, value=int(st.session_state.dashboard_report_font_size), step=1, key="dashboard_font_slider")
        st.session_state.dashboard_report_font_size = float(report_font)
    
    dashboard_data = []
    
    with st.spinner("프로젝트 데이터를 분석 중입니다..."):
        for p_name in pjt_list:
            try:
                # ★ 성능 개선: 전체가 아니라 상단 일부만 + 캐시 사용
                data = cached_get_head('pms_db', p_name, max_rows=200)
                
                pm_name = "미지정"
                this_w = "금주 실적 미입력"
                next_w = "차주 계획 미입력"
                
                if len(data) > 0:
                    header = data[0][:7]
                    df = pd.DataFrame(
                        [r[:7] for r in data[1:]],
                        columns=header
                    ) if len(data) > 1 else pd.DataFrame(columns=header)
                    
                    if len(data) > 1 and len(data[1]) > 7 and str(data[1][7]).strip(): pm_name = str(data[1][7]).strip()
                    if len(data) > 1 and len(data[1]) > 8 and str(data[1][8]).strip(): this_w = str(data[1][8]).strip()
                    if len(data) > 1 and len(data[1]) > 9 and str(data[1][9]).strip(): next_w = str(data[1][9]).strip()
                else:
                    df = pd.DataFrame()

                if not df.empty and '진행률' in df.columns:
                    avg_act = calc_weighted_actual_progress(df)
                    avg_plan = calc_weighted_planned_progress(df)
                else:
                    avg_act = 0.0; avg_plan = 0.0
                
                status_key = "정상"
                status_ui = "🟢 정상"
                b_style = "status-normal"
                if (avg_plan - avg_act) >= 10:
                    status_key = "지연"
                    status_ui = "🔴 지연"
                    b_style = "status-delay"
                elif avg_act >= 100:
                    status_key = "완료"
                    status_ui = "🔵 완료"
                    b_style = "status-done"
                
                dashboard_data.append({
                    "p_name": p_name,
                    "pm_name": pm_name,
                    "this_w": this_w,
                    "next_w": next_w,
                    "avg_act": avg_act,
                    "avg_plan": avg_plan,
                    "status_key": status_key,
                    "status_ui": status_ui,
                    "b_style": b_style
                })
            except Exception:
                # 개별 프로젝트 오류는 무시하고 계속
                pass

    all_pms = sorted(list(set([d["pm_name"] for d in dashboard_data])))
    
    _STATUS_FILTER_OPTS = ["🟢 정상", "🔴 지연", "🔵 완료"]
    _STATUS_KEY_MAP = {"🟢 정상": "정상", "🔴 지연": "지연", "🔵 완료": "완료"}

    f_col1, f_col2, f_col3 = st.columns([1, 1.2, 2.8])
    with f_col1:
        selected_pm = st.selectbox("👤 담당자 조회", ["전체"] + all_pms, key="dashboard_pm_filter")
    with f_col2:
        selected_status_labels = st.multiselect(
            "📌 상태 필터",
            _STATUS_FILTER_OPTS,
            default=["🟢 정상", "🔴 지연"],
            help="기본값은 진행 중(정상·지연)만 표시합니다. 완료 프로젝트는 '🔵 완료'를 선택하세요.",
            key="dashboard_status_filter",
        )
        selected_status_keys = {_STATUS_KEY_MAP[l] for l in selected_status_labels}

    if selected_pm != "전체":
        pm_filtered = [d for d in dashboard_data if d["pm_name"] == selected_pm]
    else:
        pm_filtered = dashboard_data

    if selected_status_keys:
        filtered_data = [d for d in pm_filtered if d["status_key"] in selected_status_keys]
    else:
        filtered_data = []

    pool_cnt = len(pm_filtered)
    display_cnt = len(filtered_data)
    normal_cnt = len([d for d in pm_filtered if d["status_key"] == "정상"])
    delay_cnt = len([d for d in pm_filtered if d["status_key"] == "지연"])
    done_cnt = len([d for d in pm_filtered if d["status_key"] == "완료"])
    pool_hint = (
        f" <span style='opacity:0.75;font-size:12px;'>(전체 {pool_cnt}건)</span>"
        if pool_cnt != display_cnt
        else ""
    )

    with f_col3:
        st.markdown(f"""
            <div class="metric-container" style="display: flex; gap: 10px; align-items: center; height: 100%; padding-top: 28px; flex-wrap: wrap;">
                <div style="background: rgba(128,128,128,0.1); padding: 7px 12px; border-radius: 6px; font-weight: bold; font-size: 13px;">
                    📊 표시: <span style="color: #2196f3; font-size: 15px;">{display_cnt}</span>건{pool_hint}
                </div>
                <div style="background: rgba(33,150,243,0.1); padding: 7px 12px; border-radius: 6px; font-weight: bold; font-size: 13px; color: #1976d2;">
                    🟢 정상: {normal_cnt}건
                </div>
                <div style="background: rgba(244,67,54,0.1); padding: 7px 12px; border-radius: 6px; font-weight: bold; font-size: 13px; color: #d32f2f;">
                    🔴 지연: {delay_cnt}건
                </div>
                <div style="background: rgba(76,175,80,0.1); padding: 7px 12px; border-radius: 6px; font-weight: bold; font-size: 13px; color: #388e3c;">
                    🔵 완료: {done_cnt}건
                </div>
            </div>
        """, unsafe_allow_html=True)
        
    st.divider()

    if not selected_status_keys:
        st.info("상태 필터에서 하나 이상을 선택해 주세요. (기본: 정상·지연)")
    elif display_cnt == 0:
        st.info("선택한 담당자·상태 조건에 맞는 프로젝트가 없습니다. 완료 건은 상태 필터에 '🔵 완료'를 추가하세요.")
    else:
        daily_df = load_daily_report_df(sh)
        for d in filtered_data:
            with st.container(border=True):
                h_col1, h_col2 = st.columns([7.5, 2.5], gap="small")

                with h_col1:
                    st.markdown(f"""
                        <div style="display: flex; align-items: center; flex-wrap: wrap; gap: 6px; margin-top: 2px;">
                            <h4 style="font-weight:700; margin:0; font-size:clamp(13.5px, 3.5vw, 16px); word-break:keep-all; line-height:1.2;">
                                🏗️ {d['p_name']}
                            </h4>
                            <span class="pm-tag" style="margin:0;">PM: {d['pm_name']}</span>
                            <span class="status-badge {d['b_style']}" style="margin:0;">{d['status_ui']}</span>
                        </div>
                    """, unsafe_allow_html=True)

                with h_col2:
                    st.button("🔍 상세", key=f"btn_go_{d['p_name']}", on_click=navigate_to_project, args=(d['p_name'],), use_container_width=True)

                weekly_col, daily_col = st.columns([1, 1.05], gap="medium")
                fs = st.session_state.get("dashboard_report_font_size", 12)
                this_w_html = html_module.escape(str(d['this_w'])).replace('\n', '<br>')
                next_w_html = html_module.escape(str(d['next_w'])).replace('\n', '<br>')

                with weekly_col:
                    st.markdown('<p class="dashboard-report-split-title">📋 주간보고</p>', unsafe_allow_html=True)
                    st.markdown(f'''
                        <div style="margin-bottom:4px;">
                            <p style="font-size:{fs}px; opacity: 0.7; margin-top:0; margin-bottom:4px;">계획: {d['avg_plan']}% | 실적: {d['avg_act']}%</p>
                            <div class="weekly-box" style="margin-top:0; font-size:{fs}px;">
                                <div style="margin-bottom: 8px;"><b>[금주]</b><br>{this_w_html}</div>
                                <div><b>[차주]</b><br>{next_w_html}</div>
                            </div>
                        </div>
                    ''', unsafe_allow_html=True)
                    st.progress(min(1.0, max(0.0, d['avg_act']/100)))

                with daily_col:
                    st.markdown('<p class="dashboard-report-split-title">📋 일일보고</p>', unsafe_allow_html=True)
                    dr_date, dr_rows = _get_latest_daily_report_for_project(daily_df, d['p_name'])
                    if dr_rows:
                        st.caption(f"최근 일자: {_daily_report_date_korean(dr_date)}")
                        _render_daily_report_section_table(
                            dr_rows,
                            dr_date,
                            project_name=None,
                            compact=True,
                        )
                    else:
                        st.markdown(
                            '<div class="weekly-box" style="font-size:12px; opacity:0.85;">'
                            "저장된 일일보고가 없습니다.<br>"
                            "<span style='font-size:11px;'>일일보고 메뉴에서 작성·업로드하세요.</span>"
                            "</div>",
                            unsafe_allow_html=True,
                        )


def view_weekly_final_report(sh, pjt_list):
    """프로젝트별 진행 현황 표 + 엑셀 다운로드 (선택: Gemini 요약)"""
    col_title, col_btn = st.columns([7, 2])
    with col_title:
        st.title("📋 프로젝트별 주간 최종 보고 (표)")
    with col_btn:
        render_print_button()
    st.caption(
        "데이터는 구글 시트 `pms_db`의 각 프로젝트 시트와 동일합니다. "
        "**실적·계획%**는 공정별 진행률을 **일정 기간(종료일−시작일)으로 가중**한 평균입니다."
    )

    with st.spinner("프로젝트별 데이터를 불러오는 중…"):
        report_df = build_project_status_report_df(pjt_list)

    if report_df.empty:
        st.info("표시할 프로젝트가 없습니다.")
        return

    all_pms = sorted(report_df["담당자"].dropna().unique().tolist())
    f1, f2 = st.columns([1, 3])
    with f1:
        pm_sel = st.selectbox("담당자 필터", ["전체"] + all_pms, key="report_pm_filter")
    base_df = st.session_state.get("gemini_summary_df")
    display_df = base_df if base_df is not None else report_df
    filt = display_df if pm_sel == "전체" else display_df[display_df["담당자"] == pm_sel]

    st.metric("조회 건수", f"{len(filt)}건")
    show_df = filt.copy()
    show_df = show_df.reset_index(drop=True)
    show_df.insert(0, "순번", range(1, len(show_df) + 1))

    # 표 표시용 컬럼명/순서 정리
    rename_map = {
        "용량(MW)": "용량",
        "계획진행률%": "계획",
        "진행률_실적%": "실적",
        "금주_주요": "금주",
        "차주_주요": "차주",
    }
    show_df = show_df.rename(columns=rename_map)

    base_cols = [
        "순번",
        "프로젝트명",
        "용량",
        "담당자",
        "계획",
        "실적",
        "상태",
        "금주",
        "차주",
    ]
    extra_cols = [c for c in ["금주_주요_요약", "차주_주요_요약"] if c in show_df.columns]
    ordered_cols = [c for c in base_cols if c in show_df.columns] + extra_cols
    show_df = show_df[ordered_cols]

    st.dataframe(show_df, use_container_width=True, height=min(520, 120 + len(show_df) * 36))

    c1, c2, c3 = st.columns(3)
    with c1:
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            show_df.to_excel(writer, index=False, sheet_name="주간최종보고")
        st.download_button(
            label="📥 엑셀(xlsx) 다운로드",
            data=buf.getvalue(),
            file_name=f"프로젝트별_주간최종보고_{datetime.date.today()}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
    with c2:
        if st.button("🔄 원본 표로 초기화", use_container_width=True):
            st.session_state["gemini_summary_df"] = None
            st.rerun()
    with c3:
        pass

    with st.expander("✨ Gemini로 금주·차주 요약 열 추가", expanded=False):
        st.markdown(
            "로컬은 `.streamlit/secrets.toml`, **Streamlit Cloud**는 해당 앱 **⋮ → Settings → Secrets**에 "
            "아래 **한 줄**을 **최상위**(다른 `[표제]` 블록 밖이어도 됨)로 넣으세요.\n\n"
            "```toml\nGEMINI_API_KEY = \"여기에_키\"\n```\n\n"
            "- **`chatbot`과 `pjt`는 Secrets가 각각 따로입니다.** 지금 보는 앱과 동일한 앱에 넣었는지 확인하세요.\n"
            "- 저장 후 메뉴의 **Reboot**로 한 번 재시작하면 반영이 확실합니다.\n"
            "- 이름은 대문자 `GEMINI_API_KEY` 권장 (`Gemini_api_key` 등은 인식 안 될 수 있음).\n\n"
            "[Google AI Studio](https://aistudio.google.com/apikey)에서 키 발급. "
            "(외부 전송 전 회사 보안 정책을 확인하세요.)"
        )
        with st.expander("🔧 키 인식 진단 (값은 표시하지 않음)", expanded=False):
            st.markdown(_gemini_key_debug_hint())
        if st.button("Gemini로 요약 표 생성", type="primary", use_container_width=True):
            with st.spinner("Gemini 요약 중…"):
                summ, err = call_gemini_summarize_table(report_df.copy())
            if err:
                st.error(err)
            else:
                st.session_state["gemini_summary_df"] = summ
                st.success("요약 열이 추가되었습니다. 위 표와 엑셀 다운로드에 반영됩니다.")
                st.rerun()


# 2. 프로젝트 상세 관리
def view_project_detail(sh, pjt_list):
    col_title, col_btn = st.columns([8, 2])
    with col_title:
        st.title("🏗️ 프로젝트 상세 관리")
    with col_btn:
        st.write("")
        render_print_button()
    
    selected_pjt = st.selectbox("현장 선택", ["선택"] + pjt_list, key="selected_pjt")
    
    if selected_pjt != "선택":
        data = cached_get_all_values('pms_db', selected_pjt)
        
        current_pm = ""
        this_val = ""
        next_val = ""
        
        if len(data) > 0:
            header = data[0][:7]
            df = pd.DataFrame([r[:7] for r in data[1:]], columns=header) if len(data) > 1 else pd.DataFrame(columns=header)
            
            if len(data) > 1 and len(data[1]) > 7: current_pm = str(data[1][7]).strip()
            if len(data) > 1 and len(data[1]) > 8: this_val = str(data[1][8]).strip()
            if len(data) > 1 and len(data[1]) > 9: next_val = str(data[1][9]).strip()
        else:
            df = pd.DataFrame(columns=["시작일", "종료일", "대분류", "구분", "진행상태", "비고", "진행률"])

        if '시작일' in df.columns:
            df['시작일'] = df['시작일'].astype(str).str.split().str[0].replace('nan', '')
        if '종료일' in df.columns:
            df['종료일'] = df['종료일'].astype(str).str.split().str[0].replace('nan', '')

        if '진행률' in df.columns:
            df['진행률'] = pd.to_numeric(df['진행률'], errors='coerce').fillna(0)

        # 편집용 복사본: 시작일/종료일 정규화 후 date 타입으로 변환 (잘못된 입력도 YYYY-MM-DD로 표시)
        df_edit = df.copy()

        def _normalize_date_string(val):
            """구글 시트 숫자(20260313.0), '2026.03.13', '20260313' 등 → '2026-03-13' 형태로 정규화."""
            if val is None:
                return ""
            if isinstance(val, (int, float)):
                if pd.isna(val):
                    return ""
                # 시트에서 숫자로 들어온 경우 (예: 20260313.0, 20260313)
                i = int(val)
                if 19000101 <= i <= 21001231:
                    sc = str(i)
                    if len(sc) == 8:
                        return f"{sc[:4]}-{sc[4:6]}-{sc[6:8]}"
                return ""
            s = str(val).strip()
            if not s or s.lower() in ("nan", "none", "."):
                return ""
            # 앞에 붙은 마이너스(오타) 제거
            if s.startswith("-"):
                s = s[1:].strip()
            # 이미 YYYY-MM-DD 형태면 그대로
            if len(s) >= 10 and s[4] == "-" and s[7] == "-":
                return s[:10]
            # 숫자만 추출 (20260313.0 → 20260313)
            s_clean = "".join(c for c in s if c.isdigit())
            if len(s_clean) >= 8:
                s_clean = s_clean[:8]
                return f"{s_clean[:4]}-{s_clean[4:6]}-{s_clean[6:8]}"
            # 점/슬래시를 dash로 통일 후 처리
            s = s.replace(".", "-").replace("/", "-")
            parts = s.split("-")
            if len(parts) == 2 and len(parts[0]) == 4 and len(parts[1]) == 4:
                return f"{parts[0]}-{parts[1][:2]}-{parts[1][2:]}"
            return s

        def _to_date_or_none(ser):
            def one(val):
                norm = _normalize_date_string(val)
                if not norm:
                    return None
                try:
                    parsed = pd.to_datetime(norm, errors="coerce")
                    return parsed.date() if pd.notna(parsed) else None
                except Exception:
                    return None
            return ser.apply(one)

        df_edit['시작일'] = _to_date_or_none(df_edit['시작일'])
        df_edit['종료일'] = _to_date_or_none(df_edit['종료일'])

        # 텍스트 컬럼에서 'None', 'nan' 표기 제거 → 빈 칸으로 표시
        for col in ['대분류', '구분', '진행상태', '비고']:
            if col in df_edit.columns:
                df_edit[col] = df_edit[col].astype(str).replace({"None": "", "nan": "", "NaN": ""})

        # 편집 내용 유지: 프로젝트별 세션 보관 (단, 시트 데이터가 바뀌면 자동 재로드)
        data_sig = _sheet_data_signature(data)
        sig_key = f"process_edit_sig_{selected_pjt}"
        invalidated = set(st.session_state.get("process_edit_invalidated_pjts") or ())
        sheet_changed = st.session_state.get(sig_key) != data_sig
        need_reload = (
            "process_edit_df" not in st.session_state
            or st.session_state.get("process_edit_pjt") != selected_pjt
            or selected_pjt in invalidated
            or sheet_changed
        )
        if need_reload:
            st.session_state.process_edit_df = df_edit.copy()
            st.session_state.process_edit_pjt = selected_pjt
            st.session_state[sig_key] = data_sig
            if selected_pjt in invalidated:
                invalidated.discard(selected_pjt)
                st.session_state.process_edit_invalidated_pjts = invalidated
        process_df = st.session_state.process_edit_df

        ws = safe_api_call(sh.worksheet, selected_pjt)

        col_pm1, col_pm2 = st.columns([3, 1])
        with col_pm1:
            new_pm = st.text_input("프로젝트 담당 PM (H2 셀)", value=current_pm)
        with col_pm2:
            st.write("")
            if st.button("PM 성함 저장"):
                safe_api_call(ws.update, 'H2', [[new_pm]])
                cached_get_all_values.clear()
                cached_get_head.clear()
                clear_file_cache(selected_pjt)
                st.success("PM이 업데이트되었습니다!")
        
        st.divider()

        tab1, tab2, tab3 = st.tabs(["📊 간트 차트", "📈 S-Curve 분석", "📝 주간 업무 보고"])
        
        with tab1:
            try:
                cdf = df.copy()
                original_len = len(cdf)
                
                cdf['시작일'] = pd.to_datetime(cdf['시작일'], errors='coerce')
                cdf['종료일'] = pd.to_datetime(cdf['종료일'], errors='coerce')
                cdf = cdf.dropna(subset=['시작일', '종료일'])
                
                dropped_len = original_len - len(cdf)
                if dropped_len > 0:
                    st.warning(f"⚠️ 날짜 형식 오류(예: 2월 30일 등 존재하지 않는 날짜)로 인해 {dropped_len}개의 항목이 차트에서 제외되었습니다.")
                
                if not cdf.empty:
                    cdf = cdf.reset_index(drop=True)
                    
                    if '대분류' in cdf.columns:
                        cdf['대분류'] = cdf['대분류'].astype(str).replace({'nan': '미지정', '': '미지정'})
                    if '구분' not in cdf.columns:
                        cdf['구분'] = '내용 없음'
                        
                    cdf['진행률'] = pd.to_numeric(cdf['진행률'], errors='coerce').fillna(0).astype(float)
                    
                    # 표시용 라벨: 긴 글자 말줄임으로 좌측 영역 축소 (모바일에서 차트가 크게 보이도록)
                    max_label_len = 14
                    def truncate_label(row):
                        raw = f"{row.name + 1}. {str(row['구분']).strip()}"
                        if len(raw) <= max_label_len:
                            return raw
                        return raw[:max_label_len] + "…"
                    cdf['구분_표시'] = cdf.apply(truncate_label, axis=1)
                    
                    cdf['duration'] = (cdf['종료일'] - cdf['시작일']).dt.total_seconds() * 1000
                    cdf['duration'] = cdf['duration'].apply(lambda d: 86400000.0 if d <= 0 else d)
                    
                    cdf['시작일_str'] = cdf['시작일'].dt.strftime('%Y-%m-%d')
                    cdf['종료일_str'] = cdf['종료일'].dt.strftime('%Y-%m-%d')
                    
                    # 프로젝트 기간 년.월 (26.1 ~ 27.3 형식)
                    min_d = cdf['시작일'].min()
                    max_d = cdf['종료일'].max()
                    period_start = f"{min_d.year % 100}.{min_d.month}"
                    period_end = f"{max_d.year % 100}.{max_d.month}"
                    
                    # 상단 고정: 프로젝트 기간 + 월 눈금(스크롤해도 유지)
                    st.markdown(
                        f'<div class="gantt-sticky-header">📅 프로젝트 기간: <strong>{period_start}</strong> ~ <strong>{period_end}</strong></div>',
                        unsafe_allow_html=True
                    )
                    _render_gantt_month_ruler(min_d, max_d)
                    st.caption("↕ 공정이 많으면 아래 차트 영역만 스크롤됩니다. 상단 기간·월 눈금은 고정됩니다.")
                    
                    # 진행률별 색상 대비 강화 (0=빨강, 30=주황, 60=노랑·연두, 100=초록)
                    progress_colorscale = [
                        [0.0, 'rgb(200, 60, 60)'],
                        [0.2, 'rgb(230, 100, 80)'],
                        [0.4, 'rgb(255, 180, 60)'],
                        [0.6, 'rgb(180, 210, 90)'],
                        [0.8, 'rgb(100, 180, 100)'],
                        [1.0, 'rgb(50, 140, 70)'],
                    ]
                    
                    fig = go.Figure()
                    fig.add_trace(go.Bar(
                        base=cdf['시작일'],
                        x=cdf['duration'],
                        y=[cdf['대분류'].tolist(), cdf['구분_표시'].tolist()],
                        orientation='h',
                        marker=dict(
                            color=cdf['진행률'],
                            colorscale=progress_colorscale,
                            cmin=0,
                            cmax=100,
                            showscale=True,
                            colorbar=dict(
                                title=dict(text="진행률(%)", font=dict(size=12)),
                                thickness=18,
                                len=0.7,
                                tickfont=dict(size=11),
                                outlinewidth=1,
                            ),
                            line=dict(width=1.2, color='rgba(60,60,60,0.5)'),
                        ),
                        customdata=cdf[['시작일_str', '종료일_str', '대분류', '구분', '진행률']].values,
                        hovertemplate="<b>[%{customdata[2]}] %{customdata[3]}</b><br>시작: %{customdata[0]} ~ 종료: %{customdata[1]}<br>진행률: %{customdata[4]:.0f}%<extra></extra>"
                    ))
                    
                    today_ms = pd.Timestamp.now().normalize().timestamp() * 1000
                    fig.add_vline(
                        x=today_ms,
                        line_width=2.5,
                        line_dash="dash",
                        line_color="rgb(120, 60, 180)",
                        annotation_text=" 오늘 ",
                        annotation_position="bottom",
                        annotation_font=dict(color="rgb(120, 60, 180)", size=12, weight="bold"),
                        annotation_bgcolor="rgba(240,230,255,0.9)",
                        annotation_borderpad=4,
                    )
                    
                    fig.update_xaxes(
                        type="date",
                        side="top",
                        dtick="M1",
                        tickformat="%y.%-m",
                        tickangle=0,
                        tickfont=dict(size=11),
                        showticklabels=False,
                        showgrid=True,
                        gridwidth=1,
                        gridcolor='rgba(200, 200, 200, 0.7)',
                        showline=True,
                        linewidth=1,
                        linecolor='rgba(180, 180, 180, 0.8)',
                        mirror=True,
                        title_text="",
                    )
                    
                    fig.update_yaxes(
                        autorange="reversed",
                        type="multicategory",
                        categoryorder="trace",
                        tickfont=dict(size=10),
                        showgrid=True,
                        gridwidth=1,
                        gridcolor='rgba(200, 200, 200, 0.7)',
                        showline=True,
                        linewidth=1,
                        linecolor='rgba(180, 180, 180, 0.8)',
                        mirror=True,
                        dividercolor='rgba(120, 120, 120, 0.6)',
                        dividerwidth=1.2,
                        title_text="",
                    )
                    
                    # 좌측 여백 축소 → 차트 영역 확대 (모바일에서 그래프가 크게 보이도록)
                    chart_h = max(500, len(cdf) * 40)
                    fig.update_layout(
                        height=chart_h,
                        bargap=0.25,
                        bargroupgap=0.08,
                        plot_bgcolor='rgb(252,252,252)',
                        paper_bgcolor='white',
                        margin=dict(l=78, r=88, t=28, b=28),
                        font=dict(family="Pretendard, sans-serif", size=10),
                        showlegend=False,
                    )
                    
                    gantt_panel_h = min(720, max(380, min(chart_h, len(cdf) * 36 + 90)))
                    with st.container(height=gantt_panel_h, border=True):
                        st.plotly_chart(
                            fig,
                            use_container_width=True,
                            key=f"gantt_chart_{selected_pjt}_{data_sig[:10]}",
                        )
                else:
                    st.info("차트를 그릴 수 있는 유효한 날짜 데이터가 부족합니다. 편집기에서 날짜를 확인해 주세요.")
            except Exception as e:
                st.error(f"차트를 그리는 중 세부 오류가 발생했습니다: {e}")

        with tab2:
            try:
                sdf = df.copy()
                sdf['시작일'] = pd.to_datetime(sdf['시작일'], errors='coerce').dt.date
                sdf['종료일'] = pd.to_datetime(sdf['종료일'], errors='coerce').dt.date
                sdf = sdf.dropna(subset=['시작일', '종료일'])
                if not sdf.empty:
                    min_d, max_d = sdf['시작일'].min(), sdf['종료일'].max()
                    d_range = pd.date_range(min_d, max_d, freq='W-MON').date.tolist()
                    p_trend = [
                        calc_weighted_progress_mean(
                            sdf,
                            sdf.apply(
                                lambda r: calc_planned_progress(r['시작일'], r['종료일'], d),
                                axis=1,
                            ),
                        )
                        for d in d_range
                    ]
                    a_prog = calc_weighted_actual_progress(sdf)
                    fig_s = go.Figure()
                    fig_s.add_trace(go.Scatter(x=[d.strftime("%Y-%m-%d") for d in d_range], y=p_trend, mode='lines+markers', name='계획'))
                    fig_s.add_trace(go.Scatter(x=[datetime.date.today().strftime("%Y-%m-%d")], y=[a_prog], mode='markers', name='현재 실적', marker=dict(size=12, color='red', symbol='star')))
                    fig_s.update_layout(title="진척률 추이 (S-Curve)", yaxis_title="진척률(%)")
                    st.plotly_chart(fig_s, use_container_width=True)
            except:
                pass

        with tab3:
            st.subheader("📋 최근 주간 업무 이력")
            try:
                h_data = cached_get_all_records('pms_db', 'weekly_history')
                h_df = pd.DataFrame(h_data)
                if not h_df.empty:
                    h_df['프로젝트명'] = h_df['프로젝트명'].astype(str).str.strip()
                    p_match = h_df[h_df['프로젝트명'] == selected_pjt.strip()]
                    if not p_match.empty:
                        latest = p_match.iloc[-1]
                        
                        hist_this_w = str(latest.get('금주업무', latest.get('주요현황', '-'))).replace('\n', '<br>')
                        hist_next_w = str(latest.get('차주업무', '-')).replace('\n', '<br>')
                        
                        st.markdown(f"""
                        <div class="history-box">
                            <p style="font-size:14px; opacity: 0.7; margin-bottom:10px;">📅 <b>최종 보고일:</b> {latest.get('날짜', '-')}</p>
                            <div style="margin-bottom:12px;"><b>✔️ 금주 주요 업무:</b><br>{hist_this_w}</div>
                            <div><b>🔜 차주 주요 업무:</b><br>{hist_next_w}</div>
                        </div>
                        """, unsafe_allow_html=True)
                    else: 
                        st.info("아직 등록된 주간 업무 기록이 없습니다.")
                else:
                    st.info("아직 등록된 주간 업무 기록이 없습니다.")
            except: 
                st.warning("이력 데이터를 불러오는 중 오류가 발생했습니다.")

            # ---------- [추가] 전체 주간 보고 히스토리 (history 시트 전체 내역) ----------
            st.subheader("📜 전체 주간 보고 히스토리")
            try:
                h_data_full = cached_get_all_records('pms_db', 'weekly_history')
                h_df_full = pd.DataFrame(h_data_full)
                if not h_df_full.empty:
                    h_df_full['프로젝트명'] = h_df_full['프로젝트명'].astype(str).str.strip()
                    hist_for_pjt = h_df_full[h_df_full['프로젝트명'] == selected_pjt.strip()].copy()
                    if not hist_for_pjt.empty:
                        # 날짜 컬럼이 있으면 최신순 정렬
                        if '날짜' in hist_for_pjt.columns:
                            hist_for_pjt['_sort_date'] = pd.to_datetime(hist_for_pjt['날짜'], errors='coerce')
                            hist_for_pjt = hist_for_pjt.sort_values('_sort_date', ascending=False).drop(columns=['_sort_date'], errors='ignore')
                        # 표시용: 프로젝트명 컬럼은 제거 (이미 선택된 프로젝트이므로)
                        display_cols = [c for c in hist_for_pjt.columns if c != '프로젝트명']
                        hist_display = hist_for_pjt[display_cols] if display_cols else hist_for_pjt
                        st.caption(f"총 {len(hist_for_pjt)}건의 주간 보고 이력 (최신순)")
                        st.dataframe(hist_display, use_container_width=True, height=min(400, 80 + len(hist_display) * 38))
                    else:
                        st.info("이 프로젝트에 대한 주간 보고 이력이 없습니다.")
                else:
                    st.info("히스토리 시트에 데이터가 없습니다.")
            except Exception as e:
                st.warning(f"전체 히스토리를 불러오는 중 오류가 발생했습니다: {e}")

            st.divider()

            st.subheader("📝 주간 업무 작성 및 동기화 (I2, J2 셀 & 히스토리)")
            
            st.info("💡 우측 하단 모서리를 마우스로 드래그하면 입력 창의 크기를 자유롭게 늘리거나 줄일 수 있습니다.")
            with st.form("weekly_sync_form"):
                in_this = st.text_area("✔️ 금주 주요 업무 (I2)", value=this_val, height=250)
                in_next = st.text_area("🔜 차주 주요 업무 (J2)", value=next_val, height=250)
                if st.form_submit_button("시트 데이터 업데이트 및 이력 저장"):
                    safe_api_call(ws.update, 'I2', [[in_this]])
                    safe_api_call(ws.update, 'J2', [[in_next]])
                    try:
                        h_ws = safe_api_call(sh.worksheet, 'weekly_history')
                        safe_api_call(h_ws.append_row, [datetime.date.today().strftime("%Y-%m-%d"), selected_pjt, in_this, in_next, st.session_state.user_id])
                        cached_get_all_records.clear()
                    except: 
                        pass
                    cached_get_all_values.clear()
                    cached_get_head.clear()
                    clear_file_cache(selected_pjt)
                    st.success("성공적으로 업데이트 및 저장되었습니다!"); time.sleep(1); st.rerun()

        st.write("---")
        h_edit1, h_edit2 = st.columns([5, 1])
        with h_edit1:
            st.subheader("📝 상세 공정표 편집 (A~G열 전용)")
        with h_edit2:
            st.write("")
            if st.button("🔄 시트에서 새로고침", use_container_width=True, key=f"reload_sheet_{selected_pjt}"):
                refresh_sheet_data_cache([selected_pjt])
                st.session_state.pop(sig_key, None)
                st.rerun()
        st.info("✏️ **날짜·내용을 모두 입력한 뒤**, 맨 아래 **💾 변경사항 전체 저장** 버튼 **한 번만** 누르면 시트에 반영됩니다. (마스터 설정 엑셀 업로드 후에는 자동 반영되며, 안 보이면 **시트에서 새로고침**을 누르세요.)")

        # ---------- 달력: 폼으로 묶어서 '이 행에 적용' 클릭 시에만 전송 → 리프레시 최소화 ----------
        with st.expander("📅 달력으로 날짜 선택 (행 선택 후 시작일/종료일 설정)", expanded=False):
            n_rows = len(process_df)
            if n_rows == 0:
                st.caption("아래 표에서 행을 추가한 뒤 여기서 날짜를 설정할 수 있습니다.")
            else:
                with st.form("calendar_apply_form"):
                    row_options = list(range(n_rows))
                    def _row_label(i):
                        g = str(process_df.iloc[i].get("구분", ""))[:18]
                        return f"{i+1}행 - {g}" if g else f"{i+1}행"
                    sel_row = st.selectbox("행 선택", row_options, format_func=_row_label, key="calendar_row_sel")
                    cur_start = process_df.iloc[sel_row].get("시작일")
                    cur_end = process_df.iloc[sel_row].get("종료일")
                    default_start = cur_start if isinstance(cur_start, datetime.date) else datetime.date.today()
                    default_end = cur_end if isinstance(cur_end, datetime.date) else datetime.date.today()
                    cal_start = st.date_input("시작일", value=default_start, min_value=datetime.date(2020, 1, 1), max_value=datetime.date(2035, 12, 31), key="cal_start")
                    cal_end = st.date_input("종료일", value=default_end, min_value=datetime.date(2020, 1, 1), max_value=datetime.date(2035, 12, 31), key="cal_end")
                    calendar_submitted = st.form_submit_button("✅ 이 행에 적용")
                if calendar_submitted:
                    _proc = st.session_state.process_edit_df.copy()
                    _proc.at[_proc.index[sel_row], "시작일"] = cal_start
                    _proc.at[_proc.index[sel_row], "종료일"] = cal_end
                    st.session_state.process_edit_df = _proc
                    st.success(f"{sel_row+1}행 날짜가 반영되었습니다. 아래 표에서 다른 항목도 수정한 뒤 **변경사항 전체 저장**을 누르세요.")
                    st.rerun()

        st.caption("표에서 날짜·대분류·구분·진행상태·비고·진행률을 입력/수정한 뒤, **한 번만** 맨 아래 **💾 변경사항 전체 저장**을 누르세요.")
        # 시작일/종료일 컬럼을 달력(DateColumn)으로 설정
        column_config = {
            "시작일": st.column_config.DateColumn(
                "시작일",
                format="YYYY-MM-DD",
                min_value=datetime.date(2020, 1, 1),
                max_value=datetime.date(2035, 12, 31),
                step=1,
                help="셀 클릭 또는 위 달력에서 선택",
            ),
            "종료일": st.column_config.DateColumn(
                "종료일",
                format="YYYY-MM-DD",
                min_value=datetime.date(2020, 1, 1),
                max_value=datetime.date(2035, 12, 31),
                step=1,
                help="셀 클릭 또는 위 달력에서 선택",
            ),
        }
        edited = st.data_editor(
            process_df,
            column_config=column_config,
            use_container_width=True,
            num_rows="dynamic",
            key=f"process_schedule_editor_{selected_pjt}_{data_sig[:12]}",
        )
        st.session_state.process_edit_df = edited
        
        def _date_cell_to_str(val):
            """날짜/datetime 셀을 YYYY-MM-DD 문자열로 변환"""
            if val is None or (isinstance(val, float) and pd.isna(val)):
                return ""
            if hasattr(val, "strftime"):
                return val.strftime("%Y-%m-%d")
            s = str(val).strip()
            if not s or s.lower() == "nan":
                return ""
            # 이미 "2025-01-15" 형태면 그대로, "2025-01-15 00:00:00" 형태면 앞 10자만
            return s[:10] if len(s) >= 10 else s

        if st.button("💾 변경사항 전체 저장"):
            full_data = []
            header_7 = list(edited.columns.values)[:7]
            while len(header_7) < 7:
                header_7.append("")
            full_data.append(header_7 + ["PM", "금주", "차주"])

            if len(edited) > 0:
                for i in range(len(edited)):
                    row = edited.iloc[i]
                    r_7 = []
                    for c in edited.columns[:7]:
                        val = row[c]
                        if c in ("시작일", "종료일"):
                            r_7.append(_date_cell_to_str(val))
                        else:
                            r_7.append("" if (val is None or (isinstance(val, float) and pd.isna(val))) else str(val))
                    while len(r_7) < 7:
                        r_7.append("")
                    if i == 0:
                        r_7.extend([new_pm, in_this, in_next])
                    else:
                        r_7.extend([new_pm, "", ""])
                    full_data.append(r_7)
            else:
                full_data.append([""] * 7 + [new_pm, in_this, in_next])
                
            safe_api_call(ws.clear)
            safe_api_call(ws.update, 'A1', full_data)
            cached_get_all_values.clear()
            cached_get_head.clear()
            clear_file_cache(selected_pjt)
            invalidate_process_edit_cache([selected_pjt])
            st.session_state.pop(f"process_edit_sig_{selected_pjt}", None)
            st.success("데이터가 완벽하게 저장되었습니다!"); time.sleep(1); st.rerun()

# 3. 일 발전량 및 일조 분석
def view_solar(sh):
    col_title, col_btn = st.columns([8, 2])
    with col_title:
        st.title("☀️ 일 발전량 및 일조 분석")
    with col_btn:
        st.write("")
        render_print_button()
        
    try:
        raw = cached_get_all_records('pms_db', 'Solar_DB')
        if not raw:
            st.info("데이터가 없습니다.")
            return
        
        df_db = pd.DataFrame(raw)
        df_db['날짜'] = pd.to_datetime(df_db['날짜'], errors='coerce')
        df_db['발전시간'] = pd.to_numeric(df_db['발전시간'], errors='coerce').fillna(0)
        df_db['일사량합계'] = pd.to_numeric(df_db['일사량합계'], errors='coerce').fillna(0)
        df_db = df_db.dropna(subset=['날짜'])

        with st.expander("🔍 발전량 상세 검색 필터", expanded=True):
            f1, f2 = st.columns(2)
            with f1:
                db_locs = sorted(df_db['지점'].dropna().astype(str).unique().tolist())
                extra_locs = sorted(set(GEO_FALLBACK_COORDS.keys()) - set(db_locs))
                locs = db_locs + [f"{x} (미등록)" for x in extra_locs]
                sel_raw = st.selectbox("조회 지역 선택", locs)
                sel_loc = sel_raw.replace(" (미등록)", "").strip()
                if sel_raw.endswith("(미등록)"):
                    st.caption(f"💡 `{sel_loc}`은 Solar_DB에 없습니다. 아래 **신규 지역 데이터 생성**에서 먼저 만들 수 있습니다.")
            with f2:
                default_start = datetime.date(2024, 1, 1)
                default_end = datetime.date(2025, 12, 31)
                dr = st.date_input("조회 기간", [default_start, default_end])
        
        mask = (df_db['지점'] == sel_loc)
        if len(dr) == 2:
            mask = mask & (df_db['날짜'].dt.date >= dr[0]) & (df_db['날짜'].dt.date <= dr[1])
        
        f_df = df_db[mask].sort_values('날짜')

        # -------------------------
        # [신규] 10년 평균 대비 연평균 일사량 분석 (2024·2025)
        # -------------------------
        with st.expander("📈 연평균 일사량 vs 과거 10년 평균 (2024·2025)", expanded=True):
            render_solar_climatology_analysis(sel_loc, f_df, df_db)

        with st.expander("🏗️ 신규 지역 데이터 생성 (여주 등)", expanded=False):
            render_yeoju_data_builder(sh, df_db)

        st.divider()

        # -------------------------
        # [신규] 내일 예측 섹션
        # -------------------------
        st.subheader("🔮 내일 태양광 예측 (날씨 예보 연동)")
        with st.container(border=True):
            tom = datetime.date.today() + datetime.timedelta(days=1)
            geo = None
            try:
                geo = geocode_location_open_meteo(sel_loc)
            except Exception:
                geo = None

            lat = None
            lon = None
            if geo and geo.get("latitude") is not None and geo.get("longitude") is not None:
                lat = float(geo["latitude"])
                lon = float(geo["longitude"])
                place = " / ".join([str(x) for x in [geo.get("name"), geo.get("admin1"), geo.get("country")] if x])
                st.caption(f"예보 좌표: {place} (lat={lat:.4f}, lon={lon:.4f})")
            else:
                st.warning("지점명을 좌표로 변환하지 못했습니다. 아래에서 위/경도를 직접 입력하면 예측이 가능합니다. (자주 쓰는 지점은 개발자에게 요청해 app.py의 GEO_FALLBACK_COORDS에 등록하면 자동 변환됩니다.)")
                c1, c2 = st.columns(2)
                lat = c1.number_input("위도(lat)", value=36.3504, format="%.6f")
                lon = c2.number_input("경도(lon)", value=127.3845, format="%.6f")

            try:
                fc = fetch_open_meteo_daily_forecast(lat, lon, timezone="Asia/Seoul")
                rad = _pick_daily_value(fc, tom, "shortwave_radiation_sum")  # MJ/m²
                cloud = _pick_daily_value(fc, tom, "cloud_cover_mean")
                tmax = _pick_daily_value(fc, tom, "temperature_2m_max")
                precip = _pick_daily_value(fc, tom, "precipitation_sum")

                if rad is None:
                    st.warning("내일 일사량 예보 값을 가져오지 못했습니다. (API 응답에 날짜가 없을 수 있어요)")
                else:
                    pred_h, method, r2 = fit_predict_generation_hours(f_df, float(rad))

                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("내일 예보 일사량", f"{float(rad):.2f} MJ/m²")
                    m2.metric("내일 예측 발전시간", f"{pred_h:.2f} h")
                    if cloud is not None:
                        m3.metric("평균 운량(예보)", f"{float(cloud):.0f}%")
                    else:
                        m3.metric("평균 운량(예보)", "-")
                    if tmax is not None:
                        m4.metric("최고기온(예보)", f"{float(tmax):.1f}℃")
                    else:
                        m4.metric("최고기온(예보)", "-")

                    cap = f"예측모델: {method}"
                    if r2 is not None:
                        cap += f" | 적합도(R²): {r2:.2f}"
                    if precip is not None:
                        cap += f" | 강수량(합계): {float(precip):.1f} mm"
                    st.caption(cap)

                    # 선택: 예측값 저장 (Solar_Forecast 시트)
                    with st.expander("📌 예측값 저장 (선택)"):
                        st.write("버튼을 누르면 `pms_db`에 `Solar_Forecast` 시트가 없으면 생성하고, 예측 결과를 1행 추가합니다.")
                        if st.button("💾 내일 예측값 시트에 저장", use_container_width=True):
                            try:
                                f_ws_title = "Solar_Forecast"
                                try:
                                    f_ws = safe_api_call(sh.worksheet, f_ws_title)
                                except WorksheetNotFound:
                                    f_ws = safe_api_call(sh.add_worksheet, title=f_ws_title, rows="2000", cols="20")
                                    safe_api_call(f_ws.append_row, ["날짜", "지점", "위도", "경도", "예보_일사량(MJ/m²)", "예측_발전시간(h)", "예측모델", "R2", "운량(%)", "최고기온(℃)", "강수량(mm)", "저장시각", "저장자"])
                                now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                safe_api_call(
                                    f_ws.append_row,
                                    [
                                        tom.strftime("%Y-%m-%d"),
                                        str(sel_loc),
                                        float(lat),
                                        float(lon),
                                        float(rad),
                                        float(pred_h),
                                        str(method),
                                        "" if r2 is None else float(r2),
                                        "" if cloud is None else float(cloud),
                                        "" if tmax is None else float(tmax),
                                        "" if precip is None else float(precip),
                                        now_str,
                                        st.session_state.get("user_id", "")
                                    ]
                                )
                                st.success("저장 완료!")
                            except Exception as e:
                                st.error(f"저장 중 오류: {e}")

            except Exception as e:
                st.warning(f"예보 데이터를 불러오지 못했습니다: {e}")

        st.divider()

        if not f_df.empty:
            m1, m2, m3 = st.columns(3)
            m1.metric("평균 발전 시간", f"{f_df['발전시간'].mean():.2f} h")
            m2.metric("평균 일사량", f"{f_df['일사량합계'].mean():.2f} MJ/m²")
            m3.metric("검색 데이터 수", f"{len(f_df)} 건")

            # --- [핵심] 일사량(막대), 발전시간(선), 예측추세(빨간선) 혼합 차트 ---
            fig_solar = go.Figure()
            
            # 1. 일사량합계 (주황색 막대) - 1차 Y축
            fig_solar.add_trace(go.Bar(
                x=f_df['날짜'], 
                y=f_df['일사량합계'], 
                name='일사량 (기상청)', 
                marker_color='rgba(255, 165, 0, 0.6)', 
                yaxis='y1'
            ))
            
            # 2. 실제 발전시간 (파란색 선) - 2차 Y축
            fig_solar.add_trace(go.Scatter(
                x=f_df['날짜'], 
                y=f_df['발전시간'], 
                name='실제 발전시간', 
                mode='lines+markers', 
                line=dict(color='rgba(33, 150, 243, 1)', width=2), 
                marker=dict(size=4),
                yaxis='y2'
            ))
            
            # 3. 예측 발전시간 추세 (빨간색 두꺼운 선) - 2차 Y축 (기존 로직 유지)
            f_df = f_df.copy()
            f_df['예측_발전시간'] = (f_df['일사량합계'] / 3.6) * 0.8
            f_df['예측_추세선'] = f_df['예측_발전시간'].rolling(window=14, min_periods=1, center=True).mean()
            
            fig_solar.add_trace(go.Scatter(
                x=f_df['날짜'], 
                y=f_df['예측_추세선'], 
                name='예측 발전량 (Trend)', 
                mode='lines', 
                line=dict(color='red', width=4), 
                yaxis='y2'
            ))

            # 내일 예측 점(가능할 때만)
            try:
                tom = datetime.date.today() + datetime.timedelta(days=1)
                geo = geocode_location_open_meteo(sel_loc)
                if geo and geo.get("latitude") and geo.get("longitude"):
                    fc = fetch_open_meteo_daily_forecast(float(geo["latitude"]), float(geo["longitude"]), timezone="Asia/Seoul")
                    rad = _pick_daily_value(fc, tom, "shortwave_radiation_sum")
                    if rad is not None:
                        pred_h, _, _ = fit_predict_generation_hours(f_df, float(rad))
                        fig_solar.add_trace(go.Scatter(
                            x=[datetime.datetime.combine(tom, datetime.time(0, 0))],
                            y=[pred_h],
                            name="내일 예측(점)",
                            mode="markers",
                            marker=dict(size=12, color="purple", symbol="diamond"),
                            yaxis='y2'
                        ))
            except Exception:
                pass

            fig_solar.update_layout(
                title=f"[{sel_loc}] 일사량 및 실제/예측 발전시간 추이 비교",
                xaxis=dict(title="날짜"),
                yaxis=dict(
                    title=dict(text="일사량 (MJ/m²)", font=dict(color="orange")), 
                    tickfont=dict(color="orange")
                ),
                yaxis2=dict(
                    title=dict(text="발전시간 (h)", font=dict(color="blue")), 
                    tickfont=dict(color="blue"), 
                    anchor="free", 
                    overlaying="y", 
                    side="right"
                ),
                hovermode="x unified",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            
            st.plotly_chart(fig_solar, use_container_width=True)

            st.subheader("📊 검색 결과 상세 내역")
            
            output_solar = io.BytesIO()
            with pd.ExcelWriter(output_solar, engine='openpyxl') as writer:
                export_df = f_df.copy()
                export_df['날짜'] = export_df['날짜'].dt.strftime('%Y-%m-%d')
                export_df.to_excel(writer, index=False, sheet_name='발전량_검색결과')
            
            col_down1, col_down2 = st.columns([8, 2])
            with col_down2:
                st.download_button(
                    label="📥 데이터 엑셀 다운로드",
                    data=output_solar.getvalue(),
                    file_name=f"일일발전량_조회결과_{datetime.date.today()}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
            
            st.dataframe(f_df, use_container_width=True)
        else:
            st.warning("조건에 맞는 데이터가 없습니다.")

    except Exception as e:
        st.error(f"분석 데이터를 불러올 수 없습니다: {e}")

def _parse_korean_report_date(text: str) -> Optional[str]:
    m = re.match(r"(\d{4})년(\d{2})월(\d{2})일", str(text or "").strip())
    if not m:
        return None
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"


def _guess_project_from_filename(filename: str, pjt_list: list) -> str:
    base = pathlib.Path(str(filename or "")).stem
    for p in pjt_list:
        if p in base:
            return p
    m = re.search(r"\d{6}\s*(.+?)\s*일일보고", base)
    if m:
        guess = m.group(1).strip()
        for p in pjt_list:
            if guess in p or p in guess:
                return p
        return guess
    return ""


def parse_daily_report_xlsx(uploaded_file) -> list:
    """
    합천댐 일일보고 엑셀 형식 파싱.
    반환: [{"date": "2026-06-02", "rows": [{구분, 대분류, 세부항목, 업무내용, 공정율, 비고}, ...]}, ...]
    """
    df = pd.read_excel(uploaded_file, sheet_name=0, header=None)
    reports = []
    report_date = None
    rows = []
    major_cat = ""

    def _cell(row, idx):
        if idx >= len(row) or pd.isna(row.iloc[idx]):
            return ""
        return str(row.iloc[idx]).strip()

    def _flush():
        nonlocal rows
        if report_date and rows:
            reports.append({"date": report_date, "rows": rows.copy()})

    for idx in range(len(df)):
        row = df.iloc[idx]
        c0, c1, c2, c3, c9, c11 = (
            _cell(row, 0),
            _cell(row, 1),
            _cell(row, 2),
            _cell(row, 3),
            _cell(row, 9),
            _cell(row, 11),
        )
        parsed_date = _parse_korean_report_date(c0)
        if parsed_date:
            _flush()
            rows = []
            report_date = parsed_date
            major_cat = ""
            continue
        if c0 == "구 분" or not report_date:
            continue
        if c1 and re.match(r"^\d+\.", c1):
            major_cat = c1
        if re.match(r"^\d+-\d+$", c0):
            rows.append(
                {
                    "구분": c0,
                    "대분류": major_cat,
                    "세부항목": c2,
                    "업무내용": c3,
                    "공정율": "" if c9 in ("", "-") else c9,
                    "비고": "" if c11 in ("", "-") else c11,
                }
            )
        elif rows and (c3 or (c9 and c9 != "-") or (c11 and c11 != "-")):
            last = rows[-1]
            if c3:
                last["업무내용"] = f"{last['업무내용']}\n{c3}".strip() if last["업무내용"] else c3
            if c9 and c9 != "-":
                last["공정율"] = c9
            if c11 and c11 != "-":
                last["비고"] = f"{last['비고']}\n{c11}".strip() if last["비고"] else c11
    _flush()
    return reports


def _get_daily_report_worksheet(sh):
    try:
        return safe_api_call(sh.worksheet, DAILY_REPORT_SHEET)
    except WorksheetNotFound:
        ws = safe_api_call(sh.add_worksheet, title=DAILY_REPORT_SHEET, rows="5000", cols=str(len(DAILY_REPORT_COLUMNS)))
        safe_api_call(ws.append_row, DAILY_REPORT_COLUMNS)
        return ws


def load_daily_report_df(sh) -> pd.DataFrame:
    try:
        raw = cached_get_all_records("pms_db", DAILY_REPORT_SHEET)
        if not raw:
            return pd.DataFrame(columns=DAILY_REPORT_COLUMNS)
        df = pd.DataFrame(raw)
        for col in DAILY_REPORT_COLUMNS:
            if col not in df.columns:
                df[col] = ""
        return df[DAILY_REPORT_COLUMNS]
    except Exception:
        return pd.DataFrame(columns=DAILY_REPORT_COLUMNS)


def save_daily_reports_to_sheet(sh, project_name: str, sections: list, user_id: str, overwrite_dates: bool = True) -> int:
    """파싱된 일일보고 섹션을 pms_db 일일보고 시트에 저장. 반환: 저장 행 수"""
    if not sections:
        return 0
    ws = _get_daily_report_worksheet(sh)
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    upload_dates = {s["date"] for s in sections}

    if overwrite_dates:
        existing = safe_api_call(ws.get_all_values)
        if existing:
            header = existing[0]
            kept = [header]
            for row in existing[1:]:
                if len(row) < 2:
                    kept.append(row)
                    continue
                row_date = str(row[0]).strip()[:10]
                row_pjt = str(row[1]).strip()
                if row_pjt == project_name and row_date in upload_dates:
                    continue
                kept.append(row)
            safe_api_call(ws.clear)
            if kept:
                safe_api_call(ws.update, "A1", kept)

    new_rows = []
    for section in sections:
        for item in section.get("rows", []):
            new_rows.append(
                [
                    section["date"],
                    project_name,
                    item.get("구분", ""),
                    item.get("대분류", ""),
                    item.get("세부항목", ""),
                    item.get("업무내용", ""),
                    item.get("공정율", ""),
                    item.get("비고", ""),
                    now_str,
                    user_id or "",
                ]
            )
    for row in new_rows:
        safe_api_call(ws.append_row, row, value_input_option="USER_ENTERED")
    cached_get_all_records.clear()
    return len(new_rows)


DEFAULT_DAILY_REPORT_LEGEND = [
    ("RFQ", "Request For Quotation"),
    ("TBE", "Technical Bid Evaluation"),
    ("IFA", "Issue For Approved"),
    ("IFC", "Issue For Construction"),
]


def _daily_report_date_korean(date_iso: str) -> str:
    try:
        d = pd.to_datetime(str(date_iso)[:10])
        return f"{d.year}년 {d.month:02d}월 {d.day:02d}일"
    except Exception:
        return str(date_iso)


def _daily_report_escape(text) -> str:
    if text is None or (isinstance(text, float) and pd.isna(text)):
        return ""
    return html_module.escape(str(text).strip()).replace("\n", "<br>")


def _daily_report_sort_key(row: dict):
    g = str(row.get("구분", ""))
    m = re.match(r"(\d+)-(\d+)", g)
    if m:
        return (int(m.group(1)), int(m.group(2)))
    return (99, 99)


def _normalize_daily_report_rows(section_rows: list) -> list:
    """저장 시트·파싱 결과를 동일 키로 정규화"""
    out = []
    for row in section_rows or []:
        if not isinstance(row, dict):
            continue
        out.append(
            {
                "구분": str(row.get("구분", "")).strip(),
                "대분류": str(row.get("대분류", "")).strip(),
                "세부항목": str(row.get("세부항목", "")).strip(),
                "업무내용": str(row.get("업무내용", "")).strip(),
                "공정율": str(row.get("공정율", row.get("공정율(%)", ""))).strip(),
                "비고": str(row.get("비고", "")).strip(),
            }
        )
    return sorted(out, key=_daily_report_sort_key)


def _daily_report_major_rowspans(rows: list) -> dict:
    """대분류 열 rowspan: {시작행인덱스: (rowspan, 텍스트)}"""
    info = {}
    i = 0
    while i < len(rows):
        cat = rows[i].get("대분류", "")
        j = i + 1
        while j < len(rows) and rows[j].get("대분류", "") == cat:
            j += 1
        info[i] = (j - i, cat)
        i = j
    return info


def _get_latest_daily_report_for_project(daily_df: pd.DataFrame, project_name: str):
    """프로젝트별 가장 최근 일일보고 (일자, 행 목록)"""
    if daily_df is None or daily_df.empty or not project_name:
        return None, []
    sub = daily_df[daily_df["프로젝트명"].astype(str) == str(project_name)]
    if sub.empty:
        return None, []
    dates = sorted(sub["날짜"].astype(str).str[:10].unique().tolist(), reverse=True)
    latest = dates[0]
    rows = []
    day_mask = sub["날짜"].astype(str).str.startswith(latest)
    for _, r in sub.loc[day_mask].iterrows():
        rows.append(
            {
                "구분": r.get("구분", ""),
                "대분류": r.get("대분류", ""),
                "세부항목": r.get("세부항목", ""),
                "업무내용": r.get("업무내용", ""),
                "공정율": r.get("공정율(%)", ""),
                "비고": r.get("비고", ""),
            }
        )
    return latest, _normalize_daily_report_rows(rows)


def _build_daily_report_html(
    date_iso: str,
    section_rows: list,
    project_name: str = None,
    legend_note: str = "(6월24일마감)",
    *,
    show_legend: bool = True,
    show_project_tag: bool = True,
) -> str:
    rows = _normalize_daily_report_rows(section_rows)
    if not rows:
        return "<p>표시할 항목이 없습니다.</p>"

    major_spans = _daily_report_major_rowspans(rows)
    legend_cells = ""
    for abbr, desc in DEFAULT_DAILY_REPORT_LEGEND:
        legend_cells += (
            f'<div class="daily-report-legend-cell"><b>{html_module.escape(abbr)}</b> '
            f"{html_module.escape(desc)}</div>"
        )

    body_rows = ""
    for i, row in enumerate(rows):
        body_rows += "<tr>"
        body_rows += f'<td class="dr-col-id">{_daily_report_escape(row.get("구분", ""))}</td>'
        if i in major_spans:
            span, cat = major_spans[i]
            body_rows += (
                f'<td class="dr-col-major" rowspan="{span}">{_daily_report_escape(cat)}</td>'
            )
        body_rows += f'<td class="dr-col-sub">{_daily_report_escape(row.get("세부항목", ""))}</td>'
        body_rows += f'<td class="dr-col-work">{_daily_report_escape(row.get("업무내용", ""))}</td>'
        pct = row.get("공정율", "")
        body_rows += f'<td class="dr-col-pct">{_daily_report_escape(pct if pct not in ("-", "") else "")}</td>'
        body_rows += f'<td class="dr-col-note">{_daily_report_escape(row.get("비고", ""))}</td>'
        body_rows += "</tr>"

    project_bar = ""
    if project_name and show_project_tag:
        project_bar = (
            f'<div class="daily-report-project-tag">🏗️ {html_module.escape(project_name)}</div>'
        )

    if show_legend:
        top_block = f"""
        <div class="daily-report-top">
            <div class="daily-report-date-box">{_daily_report_date_korean(date_iso)}</div>
            <div style="flex:1;display:flex;flex-direction:column;">
                <div class="daily-report-legend-note">{html_module.escape(legend_note)}</div>
                <div class="daily-report-legend">{legend_cells}</div>
            </div>
        </div>"""
    else:
        top_block = f"""
        <div class="daily-report-top daily-report-top--compact">
            <div class="daily-report-date-box">{_daily_report_date_korean(date_iso)}</div>
        </div>"""

    return f"""
    <div class="daily-report-sheet">
        {project_bar}
        {top_block}
        <table class="daily-report-table">
            <thead>
                <tr>
                    <th class="dr-col-id">구분</th>
                    <th class="dr-col-major">대분류</th>
                    <th class="dr-col-sub">세부</th>
                    <th class="dr-col-work">업무 내용</th>
                    <th class="dr-col-pct">공정율<br>(%)</th>
                    <th class="dr-col-note">비고</th>
                </tr>
            </thead>
            <tbody>{body_rows}</tbody>
        </table>
    </div>
    """


# st.markdown은 <table> 등 블록 HTML을 렌더하지 못함 → st.html / components.html 사용
_DAILY_REPORT_EMBED_CSS = """
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
body { margin: 0; padding: 0; font-family: 'Pretendard', 'Malgun Gothic', sans-serif; background: #fff; }
.daily-report-viewport {
    overflow-x: auto;
    margin: 8px 0 16px 0;
    border: 1px solid #b4b4b4;
    border-radius: 4px;
    background: #fff;
}
.daily-report-sheet {
    min-width: 920px;
    font-size: 12px;
    color: #111;
}
.daily-report-top {
    display: flex;
    align-items: stretch;
    border-bottom: 1px solid #b4b4b4;
}
.daily-report-date-box {
    flex: 0 0 200px;
    background: #4f81bd;
    color: #fff;
    font-size: 22px;
    font-weight: 700;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 18px 12px;
    border-right: 1px solid #b4b4b4;
    text-align: center;
    line-height: 1.35;
}
.daily-report-legend {
    flex: 1 1 auto;
    display: grid;
    grid-template-columns: 1fr 1fr;
}
.daily-report-legend-cell {
    border: 1px solid #b4b4b4;
    border-top: none;
    padding: 5px 8px;
    font-size: 11px;
    background: #fff;
}
.daily-report-legend-cell b { font-size: 12px; }
.daily-report-legend-note {
    grid-column: 1 / -1;
    text-align: right;
    font-size: 10px;
    color: #444;
    padding: 2px 8px 4px;
    background: #fafafa;
    border-bottom: 1px solid #b4b4b4;
}
.daily-report-table {
    width: 100%;
    border-collapse: collapse;
    table-layout: fixed;
}
.daily-report-table th {
    background: #d9d9d9;
    border: 1px solid #808080;
    padding: 6px 4px;
    font-weight: 700;
    text-align: center;
    font-size: 12px;
}
.daily-report-table td {
    border: 1px solid #808080;
    padding: 5px 6px;
    vertical-align: middle;
    line-height: 1.45;
    word-break: keep-all;
    overflow-wrap: break-word;
}
.daily-report-table .dr-col-id { width: 52px; text-align: center; }
.daily-report-table .dr-col-major { width: 88px; text-align: center; font-weight: 600; background: #fafafa; }
.daily-report-table .dr-col-sub { width: 108px; text-align: center; }
.daily-report-table .dr-col-work { text-align: left; }
.daily-report-table .dr-col-pct { width: 72px; text-align: center; }
.daily-report-table .dr-col-note { width: 140px; text-align: left; font-size: 11px; }
.daily-report-project-tag {
    padding: 4px 10px;
    background: #eef4fb;
    border-bottom: 1px solid #c5d3e3;
    font-size: 12px;
    font-weight: 600;
    color: #1565c0;
}
.daily-report-viewport--dashboard {
    max-height: 420px;
    overflow: auto;
    margin: 4px 0 0 0;
}
.daily-report-viewport--dashboard .daily-report-sheet {
    min-width: 520px;
    font-size: 11px;
}
.daily-report-viewport--dashboard .daily-report-date-box {
    flex: 0 0 130px;
    font-size: 15px;
    padding: 10px 8px;
}
.daily-report-top--compact { border-bottom: 1px solid #b4b4b4; }
"""


def _estimate_daily_report_embed_height(row_count: int, compact: bool) -> int:
    n = max(row_count, 1)
    if compact:
        return min(450, max(180, 72 + n * 28))
    return min(1200, max(300, 140 + n * 32))


def _render_daily_report_html_viewport(viewport_cls: str, sheet_html: str, *, row_count: int = 0, compact: bool = False):
    """일일보고 HTML을 실제 표로 렌더 (markdown은 table 미지원)"""
    payload = f'<div class="{viewport_cls}">{sheet_html}</div>'
    if hasattr(st, "html"):
        st.html(payload)
        return
    height = _estimate_daily_report_embed_height(row_count, compact)
    doc = (
        f"<!DOCTYPE html><html><head><meta charset='utf-8'>"
        f"<style>{_DAILY_REPORT_EMBED_CSS}</style></head>"
        f"<body>{payload}</body></html>"
    )
    components.html(doc, height=height, scrolling=True)


def _render_daily_report_section_table(
    section_rows: list,
    date_iso: str,
    project_name: str = None,
    *,
    compact: bool = False,
):
    if not section_rows:
        st.info("표시할 항목이 없습니다.")
        return
    sheet_html = _build_daily_report_html(
        date_iso,
        section_rows,
        project_name=project_name,
        show_legend=not compact,
        show_project_tag=not compact,
    )
    viewport_cls = "daily-report-viewport daily-report-viewport--dashboard" if compact else "daily-report-viewport"
    _render_daily_report_html_viewport(
        viewport_cls,
        sheet_html,
        row_count=len(section_rows),
        compact=compact,
    )


def load_daily_report_rows(sh, project_name: str, date_iso: str) -> list:
    """구글 시트에서 특정 프로젝트·일자 일일보고 행 목록"""
    df = load_daily_report_df(sh)
    if df.empty or not project_name:
        return []
    d = str(date_iso)[:10]
    mask = (df["프로젝트명"].astype(str) == str(project_name)) & (
        df["날짜"].astype(str).str.startswith(d)
    )
    rows = []
    for _, r in df.loc[mask].iterrows():
        rows.append(
            {
                "구분": r.get("구분", ""),
                "대분류": r.get("대분류", ""),
                "세부항목": r.get("세부항목", ""),
                "업무내용": r.get("업무내용", ""),
                "공정율": r.get("공정율(%)", ""),
                "비고": r.get("비고", ""),
            }
        )
    return _normalize_daily_report_rows(rows)


def _copy_daily_report_rows(rows: list) -> list:
    return copy.deepcopy(_normalize_daily_report_rows(rows))


def _editor_df_from_rows(rows: list) -> pd.DataFrame:
    cols = ["구분", "대분류", "세부항목", "업무내용", "공정율", "비고"]
    norm = _normalize_daily_report_rows(rows)
    if not norm:
        return pd.DataFrame(columns=cols)
    df = pd.DataFrame(norm)
    for c in cols:
        if c not in df.columns:
            df[c] = ""
    return df[cols]


def _rows_from_editor_df(df: pd.DataFrame) -> list:
    if df is None or df.empty:
        return []
    rows = []
    for _, r in df.iterrows():
        item = {
            "구분": "" if pd.isna(r.get("구분")) else str(r.get("구분", "")).strip(),
            "대분류": "" if pd.isna(r.get("대분류")) else str(r.get("대분류", "")).strip(),
            "세부항목": "" if pd.isna(r.get("세부항목")) else str(r.get("세부항목", "")).strip(),
            "업무내용": "" if pd.isna(r.get("업무내용")) else str(r.get("업무내용", "")).strip(),
            "공정율": "" if pd.isna(r.get("공정율")) else str(r.get("공정율", "")).strip(),
            "비고": "" if pd.isna(r.get("비고")) else str(r.get("비고", "")).strip(),
        }
        if not any(item[c] for c in ("구분", "세부항목", "업무내용", "대분류")):
            continue
        rows.append(item)
    return _normalize_daily_report_rows(rows)


def _daily_report_source_dates(sh, project_name: str, exclude_date: str = None) -> list:
    df = load_daily_report_df(sh)
    if df.empty or not project_name:
        return []
    mask = df["프로젝트명"].astype(str) == str(project_name)
    dates = sorted(df.loc[mask, "날짜"].astype(str).str[:10].unique().tolist(), reverse=True)
    if exclude_date:
        dates = [d for d in dates if d != str(exclude_date)[:10]]
    return dates


def _render_daily_report_edit_and_save(
    sh,
    project_name: str,
    date_iso: str,
    initial_rows: list,
    key_prefix: str,
    show_html_preview: bool = True,
):
    """일일보고 편집기 + 미리보기 + 구글 시트 저장 + 일자 복사"""
    if not project_name:
        st.warning("프로젝트를 선택하세요.")
        return

    date_iso = str(date_iso)[:10]
    draft_key = f"dr_draft_{key_prefix}_{project_name}_{date_iso}"
    src_dates = _daily_report_source_dates(sh, project_name, exclude_date=date_iso)

    st.markdown("##### 📋 일자 복사 (다음날 작성용)")
    cp1, cp2, cp3, cp4 = st.columns([1.3, 1, 1, 1.2])
    with cp1:
        copy_from = st.selectbox(
            "복사 원본 일자",
            ["선택"] + src_dates,
            key=f"dr_copy_from_{key_prefix}_{project_name}_{date_iso}",
        )
    with cp2:
        if st.button("📋 원본 복사", key=f"dr_copy_btn_{key_prefix}", use_container_width=True):
            if copy_from == "선택":
                st.warning("복사할 원본 일자를 선택하세요.")
            else:
                st.session_state[draft_key] = _copy_daily_report_rows(
                    load_daily_report_rows(sh, project_name, copy_from)
                )
                st.success(f"{copy_from} 내용을 불러왔습니다. 수정 후 저장하세요.")
                st.rerun()
    with cp3:
        if st.button("📋 최근 보고 복사", key=f"dr_copy_latest_{key_prefix}", use_container_width=True):
            all_dates = _daily_report_source_dates(sh, project_name)
            if not all_dates:
                st.warning("복사할 저장된 일일보고가 없습니다.")
            else:
                src = all_dates[0]
                if src == date_iso and len(all_dates) > 1:
                    src = all_dates[1]
                elif src == date_iso:
                    st.warning("다른 일자의 저장 데이터가 없습니다.")
                    src = None
                if src:
                    st.session_state[draft_key] = _copy_daily_report_rows(
                        load_daily_report_rows(sh, project_name, src)
                    )
                    st.success(f"{src} 보고를 복사했습니다.")
                    st.rerun()
    with cp4:
        try:
            default_new = pd.to_datetime(date_iso).date() + datetime.timedelta(days=1)
        except Exception:
            default_new = datetime.date.today() + datetime.timedelta(days=1)
        new_date = st.date_input(
            "새 일자",
            value=default_new,
            key=f"dr_new_date_{key_prefix}_{project_name}_{date_iso}",
        )

    cp5, cp6 = st.columns([1, 3])
    with cp5:
        if st.button("📅 새 일자로 복사 작성", key=f"dr_newday_{key_prefix}", use_container_width=True):
            src = copy_from if copy_from != "선택" else (
                _daily_report_source_dates(sh, project_name)[0]
                if _daily_report_source_dates(sh, project_name)
                else None
            )
            if not src:
                st.warning("복사 원본 일자를 선택하거나, 저장된 보고가 있어야 합니다.")
            else:
                new_iso = new_date.strftime("%Y-%m-%d")
                new_draft_key = f"dr_draft_{key_prefix}_{project_name}_{new_iso}"
                st.session_state[new_draft_key] = _copy_daily_report_rows(
                    load_daily_report_rows(sh, project_name, src)
                )
                st.session_state["dr_jump_project"] = project_name
                st.session_state["dr_jump_date"] = new_iso
                st.success(f"{src} → {new_iso} 복사 완료. 작성·수정 탭에서 이어서 편집하세요.")
                st.rerun()
    with cp6:
        st.caption(
            "다음날 보고는 **원본 일자 선택 → 새 일자 지정 → 새 일자로 복사 작성** 순서로 사용하세요. "
            "복사 후 업무 내용만 수정해 저장하면 됩니다."
        )

    if draft_key not in st.session_state:
        st.session_state[draft_key] = _copy_daily_report_rows(initial_rows)

    st.markdown(f"##### ✏️ 편집 — {_daily_report_date_korean(date_iso)} · {project_name}")
    edit_df = _editor_df_from_rows(st.session_state[draft_key])
    edited = st.data_editor(
        edit_df,
        num_rows="dynamic",
        use_container_width=True,
        height=min(520, 120 + max(len(edit_df), 8) * 36),
        key=f"dr_editor_{key_prefix}_{project_name}_{date_iso}",
        column_config={
            "구분": st.column_config.TextColumn("구분", width="small"),
            "대분류": st.column_config.TextColumn("대분류", width="small"),
            "세부항목": st.column_config.TextColumn("세부", width="small"),
            "업무내용": st.column_config.TextColumn("업무 내용", width="large"),
            "공정율": st.column_config.TextColumn("공정율(%)", width="small"),
            "비고": st.column_config.TextColumn("비고", width="medium"),
        },
    )
    st.session_state[draft_key] = _rows_from_editor_df(edited)

    btn1, btn2, btn3 = st.columns([1, 1, 2])
    with btn1:
        if st.button("💾 구글 시트에 저장", type="primary", key=f"dr_save_{key_prefix}", use_container_width=True):
            rows = st.session_state.get(draft_key, [])
            if not rows:
                st.error("저장할 항목이 없습니다.")
            else:
                with st.spinner("저장 중…"):
                    cnt = save_daily_reports_to_sheet(
                        sh,
                        project_name,
                        [{"date": date_iso, "rows": rows}],
                        st.session_state.get("user_id", ""),
                        overwrite_dates=True,
                    )
                st.session_state.pop(draft_key, None)
                st.success(f"`{DAILY_REPORT_SHEET}`에 {cnt}건 저장되었습니다.")
                st.rerun()
    with btn2:
        if st.button("↩️ 편집 초기화", key=f"dr_reset_{key_prefix}", use_container_width=True):
            st.session_state[draft_key] = _copy_daily_report_rows(initial_rows)
            st.rerun()

    if show_html_preview:
        st.markdown("##### 👁️ 양식 미리보기")
        _render_daily_report_section_table(
            st.session_state[draft_key],
            date_iso,
            project_name,
        )


def view_daily_report(sh, pjt_list):
    col_title, col_btn = st.columns([8, 2])
    with col_title:
        st.title("📋 일일보고")
    with col_btn:
        render_print_button()

    st.caption(
        "일일보고를 화면에서 **편집·저장**하거나, 엑셀을 업로드할 수 있습니다. "
        f"데이터는 구글 시트 `{DAILY_REPORT_SHEET}` 탭에 저장됩니다."
    )

    tab_edit, tab_upload, tab_saved = st.tabs(["✏️ 작성·수정", "📤 엑셀 업로드", "📂 저장된 일일보고"])

    with tab_edit:
        jump_pjt = st.session_state.pop("dr_jump_project", None)
        jump_date = st.session_state.pop("dr_jump_date", None)
        if jump_pjt and jump_pjt in pjt_list:
            st.session_state["dr_edit_pjt"] = jump_pjt
        if jump_date:
            try:
                st.session_state["dr_edit_date"] = pd.to_datetime(str(jump_date)[:10]).date()
            except Exception:
                pass
        e1, e2 = st.columns(2)
        with e1:
            edit_pjt = st.selectbox(
                "프로젝트",
                ["선택"] + pjt_list,
                key="dr_edit_pjt",
            )
        with e2:
            if "dr_edit_date" not in st.session_state:
                st.session_state["dr_edit_date"] = datetime.date.today()
            edit_date = st.date_input("보고 일자", key="dr_edit_date")

        if edit_pjt == "선택":
            st.info("프로젝트를 선택하면 일일보고를 작성·수정할 수 있습니다.")
        else:
            edit_iso = edit_date.strftime("%Y-%m-%d")
            existing_rows = load_daily_report_rows(sh, edit_pjt, edit_iso)
            if existing_rows:
                st.caption(f"저장된 데이터 **{len(existing_rows)}건** 불러옴 — 수정 후 저장하면 덮어씁니다.")
            else:
                st.info("이 일자는 아직 저장된 보고가 없습니다. 아래 **복사**로 양식을 가져온 뒤 작성하세요.")
            _render_daily_report_edit_and_save(
                sh,
                edit_pjt,
                edit_iso,
                existing_rows,
                "edit",
                show_html_preview=True,
            )

    with tab_upload:
        up_col1, up_col2 = st.columns([1, 1])
        with up_col1:
            pjt_sel = st.selectbox(
                "프로젝트",
                ["선택"] + pjt_list,
                key="daily_report_pjt",
            )
        with up_col2:
            overwrite = st.checkbox(
                "같은 날짜·프로젝트 기존 데이터 덮어쓰기",
                value=True,
                help="체크 시 업로드 파일에 포함된 날짜의 기존 기록을 삭제 후 새로 저장합니다.",
            )

        uploaded = st.file_uploader(
            "일일보고 엑셀 파일 (.xlsx)",
            type=["xlsx"],
            key="daily_report_uploader",
        )
        if uploaded:
            guess_default = _guess_project_from_filename(uploaded.name, pjt_list)
            if guess_default and pjt_sel == "선택":
                st.info(f"파일명 기준 추천 프로젝트: **{guess_default}** (목록에 있으면 저장 시 자동 사용)")
            try:
                sections = parse_daily_report_xlsx(uploaded)
            except Exception as e:
                st.error(f"엑셀 파싱 오류: {e}")
                sections = []

            if not sections:
                st.warning("일일보고 형식의 데이터를 찾지 못했습니다. 날짜 행(예: 2026년06월02일)이 있는지 확인하세요.")
            else:
                dates = [s["date"] for s in sections]
                st.success(f"**{len(sections)}개** 일자, 총 **{sum(len(s['rows']) for s in sections)}건** 항목을 읽었습니다.")
                preview_date = st.selectbox("미리보기 일자", dates, key="daily_report_preview_date")
                preview_section = next(s for s in sections if s["date"] == preview_date)
                preview_pjt = pjt_sel if pjt_sel != "선택" else guess_default
                upload_draft_key = f"dr_upload_sections_{uploaded.name}"
                if upload_draft_key not in st.session_state:
                    st.session_state[upload_draft_key] = sections

                st.markdown("##### 👁️ 업로드 미리보기")
                _render_daily_report_section_table(
                    preview_section["rows"],
                    preview_date,
                    project_name=preview_pjt or None,
                )

                save_pjt = pjt_sel if pjt_sel != "선택" else guess_default
                if save_pjt:
                    st.markdown("##### ✏️ 업로드 내용 편집·저장")
                    sec_for_edit = next(
                        s for s in st.session_state[upload_draft_key] if s["date"] == preview_date
                    )
                    _render_daily_report_edit_and_save(
                        sh,
                        save_pjt,
                        preview_date,
                        sec_for_edit["rows"],
                        "upload",
                        show_html_preview=False,
                    )

                    if st.button("💾 파일 전체 일자 한번에 저장", key="daily_report_save_all_btn"):
                        all_sections = []
                        for s in st.session_state[upload_draft_key]:
                            draft_k = f"dr_draft_upload_{save_pjt}_{s['date']}"
                            rows = st.session_state.get(draft_k, s["rows"])
                            all_sections.append({"date": s["date"], "rows": rows})
                        with st.spinner("전체 일자 저장 중…"):
                            cnt = save_daily_reports_to_sheet(
                                sh,
                                save_pjt,
                                all_sections,
                                st.session_state.get("user_id", ""),
                                overwrite_dates=overwrite,
                            )
                        st.success(f"총 {cnt}건 저장되었습니다.")
                        st.rerun()
                else:
                    st.warning("저장·편집하려면 프로젝트를 선택하세요.")

                buf = io.BytesIO()
                export_rows = []
                for section in sections:
                    for item in section["rows"]:
                        export_rows.append({"날짜": section["date"], **item})
                pd.DataFrame(export_rows).to_excel(buf, index=False, sheet_name="일일보고")
                st.download_button(
                    "📥 파싱 결과 엑셀 다운로드",
                    data=buf.getvalue(),
                    file_name=f"일일보고_파싱_{datetime.date.today()}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )

    with tab_saved:
        saved_df = load_daily_report_df(sh)
        if saved_df.empty:
            st.info(f"아직 `{DAILY_REPORT_SHEET}` 시트에 저장된 일일보고가 없습니다. 업로드 탭에서 엑셀을 저장하세요.")
            return

        f1, f2, f3 = st.columns([1, 1, 1])
        with f1:
            pjt_opts = ["전체"] + sorted(saved_df["프로젝트명"].dropna().astype(str).unique().tolist())
            filt_pjt = st.selectbox("프로젝트 필터", pjt_opts, key="daily_saved_pjt")
        with f2:
            dates_avail = sorted(saved_df["날짜"].dropna().astype(str).unique().tolist(), reverse=True)
            filt_date = st.selectbox("일자 필터", ["전체"] + dates_avail, key="daily_saved_date")
        view_df = saved_df.copy()
        if filt_pjt != "전체":
            view_df = view_df[view_df["프로젝트명"].astype(str) == filt_pjt]
        if filt_date != "전체":
            view_df = view_df[view_df["날짜"].astype(str).str.startswith(filt_date[:10])]

        st.metric("조회 건수", f"{len(view_df)}건")
        if view_df.empty:
            st.warning("선택한 조건에 맞는 데이터가 없습니다.")
            return

        display_cols = ["날짜", "프로젝트명", "구분", "대분류", "세부항목", "업무내용", "공정율(%)", "비고"]
        show_saved = view_df[display_cols].reset_index(drop=True)

        sheet_dates = sorted(show_saved["날짜"].astype(str).str[:10].unique().tolist(), reverse=True)
        if filt_date == "전체" and len(sheet_dates) > 1:
            view_date = st.selectbox("양식 미리보기 일자", sheet_dates, key="daily_saved_sheet_date")
        elif filt_date != "전체":
            view_date = filt_date[:10]
        else:
            view_date = sheet_dates[0]

        day_df = show_saved[show_saved["날짜"].astype(str).str.startswith(view_date)]
        sheet_pjt = ""
        if filt_pjt != "전체":
            sheet_pjt = filt_pjt
        elif not day_df.empty:
            sheet_pjt = str(day_df.iloc[0]["프로젝트명"])

        sheet_rows = load_daily_report_rows(sh, sheet_pjt, view_date) if sheet_pjt else []
        _render_daily_report_section_table(sheet_rows, view_date, project_name=sheet_pjt or None)

        if sheet_pjt:
            with st.expander("✏️ 이 일자 수정·저장", expanded=False):
                _render_daily_report_edit_and_save(
                    sh,
                    sheet_pjt,
                    view_date,
                    sheet_rows,
                    "saved",
                    show_html_preview=False,
                )

        with st.expander("📊 표 형태로 보기 / 엑셀 다운로드"):
            st.dataframe(
                show_saved,
                use_container_width=True,
                height=min(400, 100 + len(show_saved) * 36),
            )

        out = io.BytesIO()
        show_saved.to_excel(out, index=False, sheet_name="일일보고")
        st.download_button(
            "📥 조회 결과 엑셀 다운로드",
            data=out.getvalue(),
            file_name=f"일일보고_조회_{datetime.date.today()}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )


# 4. 경영지표 KPI
def view_kpi(sh):
    col_title, col_btn = st.columns([8, 2])
    with col_title:
        st.title("📉 경영 실적 및 KPI")
    with col_btn:
        st.write("")
        render_print_button()
        
    try:
        df = pd.DataFrame(cached_get_all_records('pms_db', 'KPI'))
        st.table(df)
        if not df.empty and '실적' in df.columns:
            st.plotly_chart(px.pie(df, values='실적', names=df.columns[0], title="항목별 실적 비중"))
    except: 
        st.warning("KPI 시트를 찾을 수 없습니다.")

def view_admin_menu_visibility(sh):
    """admin 전용: 일반 사용자 PMO 메뉴 표시/숨김 설정"""
    st.subheader("👁️ PMO 메뉴 표시 설정")
    st.caption("체크한 메뉴는 **일반 사용자** 화면(사이드바·상단 메뉴)에서 숨겨집니다.")
    st.info(
        f"**{ADMIN_MENU}**은 `{ADMIN_USER_ID}` 계정 전용이며, 일반 사용자에게는 항상 표시되지 않습니다. "
        f"설정은 구글 시트 `{MENU_CONFIG_SHEET}`에도 저장되어 배포 환경에서도 유지됩니다."
    )

    configurable = [m for m in ALL_PMO_MENUS if m != ADMIN_MENU]
    current_hidden = set(load_user_hidden_menus(sh))

    with st.form("menu_visibility_form"):
        hide_states = {
            m: st.checkbox(f"{m} — 일반 사용자에게 숨김", value=m in current_hidden)
            for m in configurable
        }
        if st.form_submit_button("💾 메뉴 표시 설정 저장", use_container_width=True):
            hidden = [m for m, hide in hide_states.items() if hide]
            save_user_hidden_menus(sh, hidden)
            st.success("메뉴 표시 설정이 저장되었습니다. (로컬 + 구글 시트)")
            st.rerun()


# 5. 마스터 관리
def view_project_admin(sh, pjt_list):
    if not is_admin_user():
        st.error("마스터 설정은 admin 계정만 이용할 수 있습니다.")
        return

    col_title, col_btn = st.columns([8, 2])
    with col_title:
        st.title("⚙️ 마스터 관리")
    with col_btn:
        st.write("")
        render_print_button()

    tab_labels = ["➕ 등록", "✏️ 수정", "🗑️ 삭제", "🔄 업로드", "📥 다운로드", "👁️ 메뉴 표시"]
    t1, t2, t3, t4, t5, t6 = st.tabs(tab_labels)
    
    with t1:
        new_n = st.text_input("신규 프로젝트명")
        if st.button("생성") and new_n:
            new_ws = safe_api_call(sh.add_worksheet, title=new_n, rows="100", cols="20")
            safe_api_call(new_ws.append_row, ["시작일", "종료일", "대분류", "구분", "진행상태", "비고", "진행률", "PM", "금주", "차주"])
            cached_get_all_values.clear()
            cached_get_head.clear()
            clear_file_cache()  # 워크시트 목록 포함 전체 갱신
            st.success("생성 완료!"); st.rerun()
            
    with t2:
        target = st.selectbox("수정 대상", ["선택"] + pjt_list, key="ren")
        new_name = st.text_input("변경할 이름")
        if st.button("이름 변경") and target != "선택" and new_name:
            ws = safe_api_call(sh.worksheet, target)
            safe_api_call(ws.update_title, new_name)
            cached_get_all_values.clear()
            cached_get_head.clear()
            clear_file_cache()  # 워크시트 목록 포함 전체 갱신
            st.success("수정 완료!"); st.rerun()

    with t3:
        target_del = st.selectbox("삭제 대상", ["선택"] + pjt_list, key="del")
        conf = st.checkbox("영구 삭제에 동의합니다.")
        if st.button("삭제 수행") and target_del != "선택" and conf:
            ws = safe_api_call(sh.worksheet, target_del)
            safe_api_call(sh.del_worksheet, ws)
            cached_get_all_values.clear()
            cached_get_head.clear()
            clear_file_cache()
            st.success("삭제 완료!"); st.rerun()

    with t4:
        st.info("💡 엑셀 파일 내의 '시트 이름'이 구글 시트의 '프로젝트명'과 일치하면 한 번에 모두 업데이트됩니다.")
        file = st.file_uploader("통합 엑셀 파일 업로드", type=['xlsx'])
        
        if file and st.button("🔄 일괄 동기화 (자동 매칭)"):
            try:
                all_sheets = pd.read_excel(file, sheet_name=None, engine='openpyxl')
                
                updated_count = 0
                skipped_sheets = []
                
                updated_projects = []
                with st.spinner("데이터를 매칭하여 일괄 업데이트 중입니다..."):
                    for sheet_name, df_up in all_sheets.items():
                        s_name = sheet_name.strip()
                        
                        if s_name in pjt_list:
                            ws = safe_api_call(sh.worksheet, s_name)
                            sync_worksheet_from_excel_df(ws, df_up)
                            updated_count += 1
                            updated_projects.append(s_name)
                        else:
                            skipped_sheets.append(s_name)
                
                cached_get_all_values.clear()
                cached_get_head.clear()
                clear_file_cache()  # 일괄 업로드 후 전체 갱신
                invalidate_process_edit_cache(updated_projects)

                if updated_count > 0:
                    st.success(f"🎉 총 {updated_count}개의 프로젝트가 성공적으로 일괄 업데이트되었습니다!")
                    st.rerun()
                else:
                    st.warning("⚠️ 일치하는 시트 이름이 없어 업데이트된 항목이 없습니다.")
                    
                if skipped_sheets:
                    st.caption(f"건너뛴 시트 (이름 불일치 또는 시스템 시트): {', '.join(skipped_sheets)}")
                    
            except Exception as e:
                st.error(f"파일 처리 중 오류가 발생했습니다: {e}")

    with t5:
        if st.button("📚 통합 백업 엑셀 생성"):
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                for p in pjt_list:
                    try:
                        data = cached_get_all_values('pms_db', p)
                        if not data:
                            continue
                        pd.DataFrame(data[1:], columns=data[0]).to_excel(writer, index=False, sheet_name=p[:31])
                    except: 
                        pass
            st.download_button("📥 통합 파일 받기", output.getvalue(), f"Backup_{datetime.date.today()}.xlsx")

    with t6:
        view_admin_menu_visibility(sh)

# ---------------------------------------------------------
# [SECTION 3] 메인 컨트롤러
# ---------------------------------------------------------

if check_login():
    client = get_client()
    if client:
        try:
            sh = safe_api_call(client.open, 'pms_db')
            sys_names = [
                'weekly_history', 'Solar_DB', 'KPI', 'Sheet1', 'Control_Center',
                'Dashboard_Control', '통합 대시보드', 'Solar_Forecast', DAILY_REPORT_SHEET,
            ]
            pjt_list = _load_file_cache(WORKSHEET_LIST_CACHE, FILE_CACHE_TTL)
            if pjt_list is None:
                pjt_list = [ws.title for ws in sh.worksheets() if ws.title not in sys_names]
                _save_file_cache(WORKSHEET_LIST_CACHE, pjt_list)
            
            visible_menus = get_pmo_menus_for_current_user(sh)
            if "selected_menu" not in st.session_state:
                st.session_state.selected_menu = visible_menus[0]
            elif st.session_state.selected_menu not in visible_menus:
                st.session_state.selected_menu = visible_menus[0]
            if "selected_pjt" not in st.session_state:
                st.session_state.selected_pjt = "선택"
            
            st.sidebar.title("📁 PMO 메뉴")
            if not is_admin_user():
                st.sidebar.caption("일부 메뉴는 관리자 설정에 따라 숨겨져 있을 수 있습니다.")
            menu = st.sidebar.radio(
                "메뉴 선택",
                visible_menus,
                key="selected_menu",
            )
            
            # 상단 가로 메뉴 (사이드바와 동기화, 테두리 없음)
            top_cols = st.columns(max(1, len(visible_menus)))
            for idx, opt in enumerate(visible_menus):
                with top_cols[idx]:
                    if opt == menu:
                        st.button(f"● {opt}", key=f"topmenu_{idx}", disabled=True, use_container_width=True, type="primary")
                    else:
                        st.button(opt, key=f"topmenu_{idx}", on_click=set_top_menu, args=(opt,), use_container_width=True)
            
            if menu == "통합 대시보드": 
                view_dashboard(sh, pjt_list)
            elif menu == "주간 최종 보고(표)":
                view_weekly_final_report(sh, pjt_list)
            elif menu == "일일보고":
                view_daily_report(sh, pjt_list)
            elif menu == "프로젝트 상세": 
                view_project_detail(sh, pjt_list)
            elif menu == "일 발전량 분석": 
                view_solar(sh)
            elif menu == "경영지표(KPI)": 
                view_kpi(sh)
            elif menu == "마스터 설정": 
                view_project_admin(sh, pjt_list)
            
            render_sidebar_cache_controls()

            if st.sidebar.button("로그아웃"):
                st.session_state.logged_in = False
                _clear_login_url_token()
                st.rerun()
        except Exception:
            st.error("서버 접속이 지연되고 있습니다. 잠시 후 새로고침 해주세요.")
