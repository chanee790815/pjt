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
from streamlit_folium import st_folium
import folium

# ---------------------------------
# 지점별 고정 위경도 매핑 (원하는 만큼 추가)
# ---------------------------------
LOCATION_COORDS = {
    "서산태양광": {"lat": 36.7840, "lon": 126.4500},
    "부산": {"lat": 35.1796, "lon": 129.0756},
    "당진": {"lat": 36.8910, "lon": 126.6290},
    # TODO: 실제 사용하는 지점명을 키로, 위도/경도를 계속 추가하세요.
}

# 1. 페이지 설정
st.set_page_config(page_title="PM 통합 공정 관리 v4.5.22", page_icon="🏗️", layout="wide")

# --- [UI] 스타일 ---
st.markdown("""
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    html, body, [class*="css"] { font-family: 'Pretendard', sans-serif; }
    
    h1 {
        font-size: clamp(1.5rem, 6vw, 2.5rem) !important; 
        word-break: keep-all !important; 
        line-height: 1.3 !important;
    }
    
    .footer { position: fixed; left: 0; bottom: 0; width: 100%; background-color: rgba(128, 128, 128, 0.15); backdrop-filter: blur(5px); text-align: center; padding: 5px; font-size: 11px; z-index: 100; }
    
    .weekly-box { background-color: rgba(128, 128, 128, 0.1); padding: 10px 12px; border-radius: 6px; margin-top: 4px; font-size: 12.5px; line-height: 1.6; border: 1px solid rgba(128, 128, 128, 0.2); white-space: normal; word-break: keep-all; word-wrap: break-word; }
    .history-box { background-color: rgba(128, 128, 128, 0.1); padding: 15px; border-radius: 8px; border-left: 5px solid #2196f3; margin-bottom: 20px; white-space: normal; word-break: keep-all; word-wrap: break-word; }
    .stMetric { background-color: rgba(128, 128, 128, 0.05); padding: 15px; border-radius: 10px; border: 1px solid rgba(128, 128, 128, 0.2); }
    
    .pm-tag { background-color: rgba(25, 113, 194, 0.15); color: #339af0; padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: 600; border: 1px solid rgba(25, 113, 194, 0.3); display: inline-block; }
    .status-badge { padding: 3px 8px; border-radius: 12px; font-size: 11px; font-weight: 700; display: inline-block; white-space: nowrap; }
    .status-normal { background-color: rgba(33, 150, 243, 0.15); color: #42a5f5; border: 1px solid rgba(33, 150, 243, 0.3); }
    .status-delay { background-color: rgba(244, 67, 54, 0.15); color: #ef5350; border: 1px solid rgba(244, 67, 54, 0.3); }
    .status-done { background-color: rgba(76, 175, 80, 0.15); color: #66bb6a; border: 1px solid rgba(76, 175, 80, 0.3); }
    
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
    
    div[data-testid="stProgressBar"] { margin-bottom: 0px !important; margin-top: 5px !important; }
    
    @media (max-width: 768px) {
        div[data-testid="stContainer"] div[data-testid="stHorizontalBlock"] {
            flex-direction: row !important;
            flex-wrap: nowrap !important;
            align-items: flex-start !important;
            gap: 5px !important;
        }
        div[data-testid="stContainer"] div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:first-child {
            width: calc(100% - 80px) !important;
            flex: 1 1 auto !important;
            min-width: 0 !important;
        }
        div[data-testid="stContainer"] div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:last-child {
            width: 75px !important;
            flex: 0 0 75px !important;
            min-width: 75px !important;
        }
        .metric-container { flex-wrap: wrap; }
    }

    @media print {
        header[data-testid="stHeader"] { display: none !important; }
        section[data-testid="stSidebar"] { display: none !important; }
        .footer { display: none !important; }
        iframe { display: none !important; }
        button { display: none !important; }
        
        .block-container { max-width: 100% !important; padding: 10px !important; margin: 0 !important; }
        * { -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }
        
        div[data-testid="stContainer"] { page-break-inside: avoid; }
    }
    </style>
    <div class="footer">시스템 상태: 정상 (v4.5.22) | PDF/보고서 인쇄 기능 추가</div>
    """, unsafe_allow_html=True)

# ---------------------------------------------------------
# [SECTION 1] 백엔드 엔진 & 유틸리티
# ---------------------------------------------------------

def safe_api_call(func, *args, **kwargs):
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

def check_login():
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
    client = get_client()
    if client is None:
        return []
    sh = safe_api_call(client.open, spreadsheet_name)
    ws = safe_api_call(sh.worksheet, worksheet_name)
    return safe_api_call(ws.get_all_values)

@st.cache_data(ttl=300, show_spinner=False)
def cached_get_all_records(spreadsheet_name: str, worksheet_name: str):
    client = get_client()
    if client is None:
        return []
    sh = safe_api_call(client.open, spreadsheet_name)
    ws = safe_api_call(sh.worksheet, worksheet_name)
    return safe_api_call(ws.get_all_records)

@st.cache_data(ttl=300, show_spinner=False)
def cached_get_head(spreadsheet_name: str, worksheet_name: str, max_rows: int = 200):
    client = get_client()
    if client is None:
        return []
    sh = safe_api_call(client.open, spreadsheet_name)
    ws = safe_api_call(sh.worksheet, worksheet_name)
    rng = f"A1:J{max_rows}"
    return safe_api_call(ws.get, rng)

# -------------------------------
# [예측] Open-Meteo 기반 내일 일사량/발전시간 예측
# -------------------------------

@st.cache_data(ttl=24 * 3600, show_spinner=False)
def geocode_location_open_meteo(name: str):
    q = str(name).strip()
    if not q:
        return None
    url = "https://geocoding-api.open-meteo.com/v1/search"
    params = {"name": q, "count": 1, "language": "ko", "format": "json"}
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

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_open_meteo_daily_forecast(latitude: float, longitude: float, timezone: str = "Asia/Seoul"):
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

def fit_predict_generation_hours(hist_df: pd.DataFrame, radiation_mj_m2: float):
    try:
        x = pd.to_numeric(hist_df.get("일사량합계"), errors="coerce")
        y = pd.to_numeric(hist_df.get("발전시간"), errors="coerce")
        m = x.notna() & y.notna()
        if m.sum() >= 12:
            a, b = np.polyfit(x[m].to_numpy(), y[m].to_numpy(), 1)
            yhat = a * x[m] + b
            ss_res = float(((y[m] - yhat) ** 2).sum())
            ss_tot = float(((y[m] - y[m].mean()) ** 2).sum())
            r2 = None if ss_tot <= 0 else (1.0 - (ss_res / ss_tot))
            pred = float(a * radiation_mj_m2 + b)
            pred = max(0.0, min(24.0, pred))
            return pred, "linear_regression", r2

        if m.sum() >= 5:
            kwh_m2 = (x[m] / 3.6).replace([np.inf, -np.inf], np.nan)
            ratio = (y[m] / kwh_m2).replace([np.inf, -np.inf], np.nan).dropna()
            if len(ratio) >= 5:
                r = float(ratio.clip(lower=0).median())
                pred = float((radiation_mj_m2 / 3.6) * r)
                pred = max(0.0, min(24.0, pred))
                return pred, "ratio_median", None

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

def navigate_to_project(p_name):
    st.session_state.selected_menu = "프로젝트 상세"
    st.session_state.selected_pjt = p_name

def render_print_button():
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

# 1. 통합 대시보드
def view_dashboard(sh, pjt_list):
    col_title, col_btn = st.columns([8, 2])
    with col_title:
        st.title("📊 통합 대시보드 (현황 브리핑)")
    with col_btn:
        st.write("")
        render_print_button()
    
    dashboard_data = []
    
    with st.spinner("프로젝트 데이터를 분석 중입니다..."):
        for p_name in pjt_list:
            try:
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
                    
                    if len(data) > 1 and len(data[1]) > 7 and str(data[1][7]).strip():
                        pm_name = str(data[1][7]).strip()
                    if len(data) > 1 and len(data[1]) > 8 and str(data[1][8]).strip():
                        this_w = str(data[1][8]).strip()
                    if len(data) > 1 and len(data[1]) > 9 and str(data[1][9]).strip():
                        next_w = str(data[1][9]).strip()
                else:
                    df = pd.DataFrame()

                if not df.empty and '진행률' in df.columns:
                    avg_act = round(pd.to_numeric(df['진행률'], errors='coerce').fillna(0).mean(), 1)
                    avg_plan = round(
                        df.apply(
                            lambda r: calc_planned_progress(r.get('시작일'), r.get('종료일')),
                            axis=1
                        ).mean(), 1
                    )
                else:
                    avg_act = 0.0
                    avg_plan = 0.0
                
                status_ui = "🟢 정상"
                b_style = "status-normal"
                if (avg_plan - avg_act) >= 10:
                    status_ui = "🔴 지연"
                    b_style = "status-delay"
                elif avg_act >= 100:
                    status_ui = "🔵 완료"
                    b_style = "status-done"
                
                dashboard_data.append({
                    "p_name": p_name,
                    "pm_name": pm_name,
                    "this_w": this_w,
                    "next_w": next_w,
                    "avg_act": avg_act,
                    "avg_plan": avg_plan,
                    "status_ui": status_ui,
                    "b_style": b_style
                })
            except Exception:
                pass

    all_pms = sorted(list(set([d["pm_name"] for d in dashboard_data])))
    
    f_col1, f_col2 = st.columns([1, 3])
    with f_col1:
        selected_pm = st.selectbox("👤 담당자 조회", ["전체"] + all_pms)
        
    if selected_pm != "전체":
        filtered_data = [d for d in dashboard_data if d["pm_name"] == selected_pm]
    else:
        filtered_data = dashboard_data

    total_cnt = len(filtered_data)
    normal_cnt = len([d for d in filtered_data if d['status_ui'] == "🟢 정상"])
    delay_cnt = len([d for d in filtered_data if d['status_ui'] == "🔴 지연"])
    done_cnt = len([d for d in filtered_data if d['status_ui'] == "🔵 완료"])

    with f_col2:
        st.markdown(f"""
            <div class="metric-container" style="display: flex; gap: 10px; align-items: center; height: 100%; padding-top: 28px;">
                <div style="background: rgba(128,128,128,0.1); padding: 7px 12px; border-radius: 6px; font-weight: bold; font-size: 13px;">
                    📊 조회된 프로젝트: <span style="color: #2196f3; font-size: 15px;">{total_cnt}</span>건
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

    if total_cnt == 0:
        st.info("선택된 담당자의 프로젝트가 없습니다.")
    else:
        cols = st.columns(2)
        for idx, d in enumerate(filtered_data):
            with cols[idx % 2]:
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
                    
                    this_w_html = str(d['this_w']).replace('\n', '<br>')
                    next_w_html = str(d['next_w']).replace('\n', '<br>')

                    st.markdown(f'''
                        <div style="margin-bottom:4px; margin-top:2px;">
                            <p style="font-size:12.5px; opacity: 0.7; margin-top:0; margin-bottom:4px;">계획: {d['avg_plan']}% | 실적: {d['avg_act']}%</p>
                            <div class="weekly-box" style="margin-top:0;">
                                <div style="margin-bottom: 8px;"><b>[금주]</b><br>{this_w_html}</div>
                                <div><b>[차주]</b><br>{next_w_html}</div>
                            </div>
                        </div>
                    ''', unsafe_allow_html=True)
                    
                    st.progress(min(1.0, max(0.0, d['avg_act']/100)))

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
            
            if len(data) > 1 and len(data[1]) > 7:
                current_pm = str(data[1][7]).strip()
            if len(data) > 1 and len(data[1]) > 8:
                this_val = str(data[1][8]).strip()
            if len(data) > 1 and len(data[1]) > 9:
                next_val = str(data[1][9]).strip()
        else:
            df = pd.DataFrame(columns=["시작일", "종료일", "대분류", "구분", "진행상태", "비고", "진행률"])

        if '시작일' in df.columns:
            df['시작일'] = df['시작일'].astype(str).str.split().str[0].replace('nan', '')
        if '종료일' in df.columns:
            df['종료일'] = df['종료일'].astype(str).str.split().str[0].replace('nan', '')

        if '진행률' in df.columns:
            df['진행률'] = pd.to_numeric(df['진행률'], errors='coerce').fillna(0)

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
                    
                    cdf['구분_고유'] = cdf.apply(lambda r: f"{r.name + 1}. {str(r['구분']).strip()}", axis=1)
                    
                    def calc_text_width(text):
                        return sum(2 if ord(c) > 127 else 1 for c in str(text))
                    
                    max_width = cdf['구분_고유'].apply(calc_text_width).max()
                    
                    cdf['구분_고유'] = cdf['구분_고유'].apply(
                        lambda x: str(x) + "&nbsp;" * int((max_width - calc_text_width(x)) * 2.5)
                    )
                    
                    cdf['duration'] = (cdf['종료일'] - cdf['시작일']).dt.total_seconds() * 1000
                    cdf['duration'] = cdf['duration'].apply(lambda d: 86400000.0 if d <= 0 else d)
                    
                    cdf['시작일_str'] = cdf['시작일'].dt.strftime('%Y-%m-%d')
                    cdf['종료일_str'] = cdf['종료일'].dt.strftime('%Y-%m-%d')
                    
                    fig = go.Figure()
                    fig.add_trace(go.Bar(
                        base=cdf['시작일'],
                        x=cdf['duration'],
                        y=[cdf['대분류'].tolist(), cdf['구분_고유'].tolist()],
                        orientation='h',
                        marker=dict(
                            color=cdf['진행률'],
                            colorscale='RdYlGn',
                            cmin=0,
                            cmax=100,
                            showscale=True,
                            colorbar=dict(title="진행률(%)")
                        ),
                        customdata=cdf[['시작일_str', '종료일_str', '대분류', '구분']].values,
                        hovertemplate="<b>[%{customdata[2]}] %{customdata[3]}</b><br>시작일: %{customdata[0]}<br>종료일: %{customdata[1]}<br>진행률: %{marker.color}%<extra></extra>"
                    ))
                    
                    today_ms = pd.Timestamp.now().normalize().timestamp() * 1000
                    fig.add_vline(
                        x=today_ms,
                        line_width=2.5,
                        line_color="purple", 
                        annotation_text="오늘",
                        annotation_position="top",
                        annotation_font=dict(color="purple", size=13, weight="bold")
                    )
                    
                    fig.update_xaxes(
                        type="date",             
                        dtick="M1",              
                        tickformat="%y.%-m",     
                        tickangle=0,             
                        showgrid=True,           
                        gridwidth=1,
                        gridcolor='rgba(200, 200, 200, 0.6)',
                        showline=True, linewidth=1, linecolor='rgba(200, 200, 200, 0.6)', mirror=True,
                        title_text=""
                    )
                    
                    fig.update_yaxes(
                        autorange="reversed",
                        type="multicategory",    
                        categoryorder="trace",   
                        showgrid=True,
                        gridwidth=1,
                        gridcolor='rgba(200, 200, 200, 0.6)',
                        showline=True, linewidth=1, linecolor='rgba(200, 200, 200, 0.6)', mirror=True,
                        dividercolor='rgba(150, 150, 150, 0.8)',
                        dividerwidth=1,
                        title_text=""
                    )
                    
                    fig.update_layout(
                        height=max(400, len(cdf) * 35),
                        plot_bgcolor='white',  
                        paper_bgcolor='white',
                        margin=dict(l=10, r=20, t=40, b=20)
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
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
                        sdf.apply(
                            lambda r: calc_planned_progress(r['시작일'], r['종료일'], d),
                            axis=1
                        ).mean()
                        for d in d_range
                    ]
                    a_prog = pd.to_numeric(sdf['진행률'], errors='coerce').fillna(0).mean()
                    fig_s = go.Figure()
                    fig_s.add_trace(go.Scatter(
                        x=[d.strftime("%Y-%m-%d") for d in d_range],
                        y=p_trend,
                        mode='lines+markers',
                        name='계획'
                    ))
                    fig_s.add_trace(go.Scatter(
                        x=[datetime.date.today().strftime("%Y-%m-%d")],
                        y=[a_prog],
                        mode='markers',
                        name='현재 실적',
                        marker=dict(size=12, color='red', symbol='star')
                    ))
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
            except:
                st.warning("이력 데이터를 불러오는 중 오류가 발생했습니다.")

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
                        safe_api_call(
                            h_ws.append_row,
                            [
                                datetime.date.today().strftime("%Y-%m-%d"),
                                selected_pjt,
                                in_this,
                                in_next,
                                st.session_state.user_id
                            ]
                        )
                        cached_get_all_records.clear()
                    except:
                        pass
                    cached_get_all_values.clear()
                    cached_get_head.clear()
                    st.success("성공적으로 업데이트 및 저장되었습니다!")
                    time.sleep(1)
                    st.rerun()

        st.write("---")
        st.subheader("📝 상세 공정표 편집 (A~G열 전용)")
        edited = st.data_editor(df, use_container_width=True, num_rows="dynamic")
        
        if st.button("💾 변경사항 전체 저장"):
            full_data = []
            header_7 = edited.columns.values.tolist()[:7]
            while len(header_7) < 7:
                header_7.append("")
            
            full_data.append(header_7 + ["PM", "금주", "차주"])
            
            edited_rows = edited.fillna("").astype(str).values.tolist()
            if len(edited_rows) > 0:
                for i, r in enumerate(edited_rows):
                    r_7 = r[:7]
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
            st.success("데이터가 완벽하게 저장되었습니다!")
            time.sleep(1)
            st.rerun()

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
                locs = sorted(df_db['지점'].unique().tolist())
                sel_loc = st.selectbox("조회 지역 선택", locs)
            with f2:
                default_start = datetime.date(2025, 1, 1)
                default_end = datetime.date(2025, 12, 31)
                dr = st.date_input("조회 기간", [default_start, default_end])
        
        mask = (df_db['지점'] == sel_loc)
        if len(dr) == 2:
            mask = mask & (df_db['날짜'].dt.date >= dr[0]) & (df_db['날짜'].dt.date <= dr[1])
        
        f_df = df_db[mask].sort_values('날짜')

        # [신규] 내일 예측 섹션 + 지도 선택
        st.subheader("🔮 내일 태양광 예측 (날씨 예보 연동)")
        with st.container(border=True):
            tom = datetime.date.today() + datetime.timedelta(days=1)

            lat = lon = None
            if sel_loc in LOCATION_COORDS:
                lat = LOCATION_COORDS[sel_loc]["lat"]
                lon = LOCATION_COORDS[sel_loc]["lon"]
                st.caption(f"고정 좌표 사용: {sel_loc} (lat={lat:.4f}, lon={lon:.4f})")
            else:
                geo = None
                try:
                    geo = geocode_location_open_meteo(sel_loc)
                except Exception:
                    geo = None

                if geo and geo.get("latitude") is not None and geo.get("longitude") is not None:
                    lat = float(geo["latitude"])
                    lon = float(geo["longitude"])
                    place = " / ".join([str(x) for x in [geo.get("name"), geo.get("admin1"), geo.get("country")] if x])
                    st.caption(f"예보 좌표(지오코딩): {place} (lat={lat:.4f}, lon={lon:.4f})")

            # 지도에서 직접 선택
            if lat is None or lon is None:
                st.warning("지점명으로 좌표를 찾지 못했습니다. 아래 지도에서 위치를 클릭하거나, 숫자로 직접 입력해 주세요.")
                center_lat, center_lon = 36.5, 127.9
                m = folium.Map(location=[center_lat, center_lon], zoom_start=7)
                m.add_child(folium.LatLngPopup())

                map_data = st_folium(m, width=700, height=400)
                last_clicked = (map_data or {}).get("last_clicked")

                c1, c2 = st.columns(2)
                if last_clicked:
                    lat = c1.number_input("위도(lat)", value=float(last_clicked["lat"]), format="%.6f")
                    lon = c2.number_input("경도(lon)", value=float(last_clicked["lng"]), format="%.6f")
                else:
                    lat = c1.number_input("위도(lat)", value=36.3504, format="%.6f")
                    lon = c2.number_input("경도(lon)", value=127.3845, format="%.6f")

            try:
                fc = fetch_open_meteo_daily_forecast(lat, lon, timezone="Asia/Seoul")
                rad = _pick_daily_value(fc, tom, "shortwave_radiation_sum")
                cloud = _pick_daily_value(fc, tom, "cloud_cover_mean")
                tmax = _pick_daily_value(fc, tom, "temperature_2m_max")
                precip = _pick_daily_value(fc, tom, "precipitation_sum")

                if rad is None:
                    st.warning("내일 일사량 예보 값을 가져오지 못했습니다.")
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

                    with st.expander("📌 예측값 저장 (선택)"):
                        st.write("버튼을 누르면 `Solar_Forecast` 시트에 예측 결과를 1행 추가합니다.")
                        if st.button("💾 내일 예측값 시트에 저장", use_container_width=True):
                            try:
                                f_ws_title = "Solar_Forecast"
                                try:
                                    f_ws = safe_api_call(sh.worksheet, f_ws_title)
                                except WorksheetNotFound:
                                    f_ws = safe_api_call(sh.add_worksheet, title=f_ws_title, rows="2000", cols="20")
                                    safe_api_call(
                                        f_ws.append_row,
                                        ["날짜", "지점", "위도", "경도", "예보_일사량(MJ/m²)", "예측_발전시간(h)",
                                         "예측모델", "R2", "운량(%)", "최고기온(℃)", "강수량(mm)", "저장시각", "저장자"]
                                    )
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

            fig_solar = go.Figure()
            
            fig_solar.add_trace(go.Bar(
                x=f_df['날짜'], 
                y=f_df['일사량합계'], 
                name='일사량 (기상청)', 
                marker_color='rgba(255, 165, 0, 0.6)', 
                yaxis='y1'
            ))
            
            fig_solar.add_trace(go.Scatter(
                x=f_df['날짜'], 
                y=f_df['발전시간'], 
                name='실제 발전시간', 
                mode='lines+markers', 
                line=dict(color='rgba(33, 150, 243, 1)', width=2), 
                marker=dict(size=4),
                yaxis='y2'
            ))
            
            f_df2 = f_df.copy()
            f_df2['예측_발전시간'] = (f_df2['일사량합계'] / 3.6) * 0.8
            f_df2['예측_추세선'] = f_df2['예측_발전시간'].rolling(window=14, min_periods=1, center=True).mean()
            
            fig_solar.add_trace(go.Scatter(
                x=f_df2['날짜'], 
                y=f_df2['예측_추세선'], 
                name='예측 발전량 (Trend)', 
                mode='lines', 
                line=dict(color='red', width=4), 
                yaxis='y2'
            ))

            try:
                tom2 = datetime.date.today() + datetime.timedelta(days=1)
                if sel_loc in LOCATION_COORDS:
                    lat2 = LOCATION_COORDS[sel_loc]["lat"]
                    lon2 = LOCATION_COORDS[sel_loc]["lon"]
                else:
                    geo2 = geocode_location_open_meteo(sel_loc)
                    lat2 = float(geo2["latitude"]) if geo2 and geo2.get("latitude") else None
                    lon2 = float(geo2["longitude"]) if geo2 and geo2.get("longitude") else None
                if lat2 is not None and lon2 is not None:
                    fc2 = fetch_open_meteo_daily_forecast(lat2, lon2, timezone="Asia/Seoul")
                    rad2 = _pick_daily_value(fc2, tom2, "shortwave_radiation_sum")
                    if rad2 is not None:
                        pred_h2, _, _ = fit_predict_generation_hours(f_df, float(rad2))
                        fig_solar.add_trace(go.Scatter(
                            x=[datetime.datetime.combine(tom2, datetime.time(0, 0))],
                            y=[pred_h2],
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

# 5. 마스터 관리
def view_project_admin(sh, pjt_list):
    col_title, col_btn = st.columns([8, 2])
    with col_title:
        st.title("⚙️ 마스터 관리")
    with col_btn:
        st.write("")
        render_print_button()
        
    t1, t2, t3, t4, t5 = st.tabs(["➕ 등록", "✏️ 수정", "🗑️ 삭제", "🔄 업로드", "📥 다운로드"])
    
    with t1:
        new_n = st.text_input("신규 프로젝트명")
        if st.button("생성") and new_n:
            new_ws = safe_api_call(sh.add_worksheet, title=new_n, rows="100", cols="20")
            safe_api_call(new_ws.append_row, ["시작일", "종료일", "대분류", "구분", "진행상태", "비고", "진행률", "PM", "금주", "차주"])
            cached_get_all_values.clear()
            cached_get_head.clear()
            st.success("생성 완료!"); st.rerun()
            
    with t2:
        target = st.selectbox("수정 대상", ["선택"] + pjt_list, key="ren")
        new_name = st.text_input("변경할 이름")
        if st.button("이름 변경") and target != "선택" and new_name:
            ws = safe_api_call(sh.worksheet, target)
            safe_api_call(ws.update_title, new_name)
            cached_get_all_values.clear()
            cached_get_head.clear()
            st.success("수정 완료!"); st.rerun()

    with t3:
        target_del = st.selectbox("삭제 대상", ["선택"] + pjt_list, key="del")
        conf = st.checkbox("영구 삭제에 동의합니다.")
        if st.button("삭제 수행") and target_del != "선택" and conf:
            ws = safe_api_call(sh.worksheet, target_del)
            safe_api_call(sh.del_worksheet, ws)
            cached_get_all_values.clear()
            cached_get_head.clear()
            st.success("삭제 완료!"); st.rerun()

    with t4:
        st.info("💡 엑셀 파일 내의 '시트 이름'이 구글 시트의 '프로젝트명'과 일치하면 한 번에 모두 업데이트됩니다.")
        file = st.file_uploader("통합 엑셀 파일 업로드", type=['xlsx'])
        
        if file and st.button("🔄 일괄 동기화 (자동 매칭)"):
            try:
                all_sheets = pd.read_excel(file, sheet_name=None, engine='openpyxl')
                
                updated_count = 0
                skipped_sheets = []
                
                with st.spinner("데이터를 매칭하여 일괄 업데이트 중입니다..."):
                    for sheet_name, df_up in all_sheets.items():
                        s_name = sheet_name.strip()
                        
                        if s_name in pjt_list:
                            ws = safe_api_call(sh.worksheet, s_name)
                            df_up = df_up.fillna("").astype(str)
                            
                            safe_api_call(ws.clear)
                            safe_api_call(ws.update, [df_up.columns.values.tolist()] + df_up.values.tolist())
                            updated_count += 1
                        else:
                            skipped_sheets.append(s_name)
                
                cached_get_all_values.clear()
                cached_get_head.clear()

                if updated_count > 0:
                    st.success(f"🎉 총 {updated_count}개의 프로젝트가 성공적으로 일괄 업데이트되었습니다!")
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

# ---------------------------------------------------------
# [SECTION 3] 메인 컨트롤러
# ---------------------------------------------------------

if check_login():
    client = get_client()
    if client:
        try:
            sh = safe_api_call(client.open, 'pms_db')
            sys_names = ['weekly_history', 'Solar_DB', 'KPI', 'Sheet1', 'Control_Center', 'Dashboard_Control', '통합 대시보드', 'Solar_Forecast']
            pjt_list = [ws.title for ws in sh.worksheets() if ws.title not in sys_names]
            
            if "selected_menu" not in st.session_state:
                st.session_state.selected_menu = "통합 대시보드"
            if "selected_pjt" not in st.session_state:
                st.session_state.selected_pjt = "선택"
            
            st.sidebar.title("📁 PMO 메뉴")
            menu = st.sidebar.radio("메뉴 선택", ["통합 대시보드", "프로젝트 상세", "일 발전량 분석", "경영지표(KPI)", "마스터 설정"], key="selected_menu")
            
            if menu == "통합 대시보드":
                view_dashboard(sh, pjt_list)
            elif menu == "프로젝트 상세":
                view_project_detail(sh, pjt_list)
            elif menu == "일 발전량 분석":
                view_solar(sh)
            elif menu == "경영지표(KPI)":
                view_kpi(sh)
            elif menu == "마스터 설정":
                view_project_admin(sh, pjt_list)
            
            if st.sidebar.button("로그아웃"):
                st.session_state.logged_in = False
                st.rerun()
        except Exception:
            st.error("서버 접속이 지연되고 있습니다. 잠시 후 새로고침 해주세요.")
