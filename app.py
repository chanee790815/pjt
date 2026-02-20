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

# 1. 페이지 설정
st.set_page_config(page_title="PM 통합 공정 관리 v4.5.13", page_icon="🏗️", layout="wide")

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
    
    .footer { position: fixed; left: 0; bottom: 0; width: 100%; background-color: var(--secondary-background-color); color: var(--text-color); text-align: center; padding: 5px; font-size: 11px; z-index: 100; opacity: 0.8; }
    
    /* [핵심] 다크/라이트 모드 자동 대응 박스 디자인 */
    .weekly-box { background-color: var(--secondary-background-color); padding: 8px 10px; border-radius: 6px; margin-top: 4px; font-size: 12px; line-height: 1.4; color: var(--text-color); border: 1px solid var(--border-color); white-space: pre-wrap; }
    .history-box { background-color: var(--secondary-background-color); padding: 15px; border-radius: 8px; border-left: 5px solid #2196f3; margin-bottom: 20px; color: var(--text-color); }
    .stMetric { background-color: var(--secondary-background-color); padding: 15px; border-radius: 10px; border: 1px solid var(--border-color); }
    
    /* 태그 및 뱃지: 다크모드에서도 잘 보이도록 반투명(rgba) 색상 적용 */
    .pm-tag { background-color: rgba(25, 113, 194, 0.15); color: #339af0; padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: 600; border: 1px solid rgba(25, 113, 194, 0.3); display: inline-block; }
    .status-badge { padding: 3px 8px; border-radius: 12px; font-size: 11px; font-weight: 700; display: inline-block; white-space: nowrap; }
    .status-normal { background-color: rgba(33, 150, 243, 0.15); color: #42a5f5; border: 1px solid rgba(33, 150, 243, 0.3); }
    .status-delay { background-color: rgba(244, 67, 54, 0.15); color: #ef5350; border: 1px solid rgba(244, 67, 54, 0.3); }
    .status-done { background-color: rgba(76, 175, 80, 0.15); color: #66bb6a; border: 1px solid rgba(76, 175, 80, 0.3); }
    
    /* 컴팩트 버튼 */
    div[data-testid="stButton"] button {
        min-height: 28px !important;
        height: 28px !important;
        padding: 0px 8px !important;
        font-size: 12px !important;
        border-radius: 6px !important;
        font-weight: 600 !important;
        line-height: 1 !important;
        margin: 0 !important;
    }
    
    /* 진행바 마진 최적화 */
    div[data-testid="stProgressBar"] { margin-bottom: 0px !important; margin-top: 5px !important; }
    </style>
    <div class="footer">시스템 상태: 정상 (v4.5.13) | 다크/라이트 모드 완벽 호환 업데이트 적용</div>
    """, unsafe_allow_html=True)

# ---------------------------------------------------------
# [SECTION 1] 백엔드 엔진 & 유틸리티
# ---------------------------------------------------------

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

def check_login():
    if st.session_state.get("logged_in", False): return True
    st.title("🏗️ PM 통합 관리 시스템")
    with st.form("login"):
        u_id = st.text_input("ID")
        u_pw = st.text_input("Password", type="password")
        if st.form_submit_button("로그인"):
            if u_id in st.secrets["passwords"] and u_pw == st.secrets["passwords"][u_id]:
                st.session_state["logged_in"] = True
                st.session_state["user_id"] = u_id
                st.rerun()
            else: st.error("정보 불일치")
    return False

@st.cache_resource
def get_client():
    try:
        key_dict = dict(st.secrets["gcp_service_account"])
        if "private_key" in key_dict: key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")
        creds = Credentials.from_service_account_info(key_dict, scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"구글 클라우드 연결 실패: {e}")
        return None

def calc_planned_progress(start, end, target_date=None):
    if target_date is None: target_date = datetime.date.today()
    try:
        s = pd.to_datetime(start).date()
        e = pd.to_datetime(end).date()
        if pd.isna(s) or pd.isna(e): return 0.0
        if target_date < s: return 0.0
        if target_date > e: return 100.0
        total_days = (e - s).days
        if total_days <= 0: return 100.0
        passed_days = (target_date - s).days
        return min(100.0, max(0.0, (passed_days / total_days) * 100))
    except: return 0.0

# 콜백 함수: 하이퍼링크처럼 상세페이지로 부드럽게 이동
def navigate_to_project(p_name):
    st.session_state.selected_menu = "프로젝트 상세"
    st.session_state.selected_pjt = p_name

# ---------------------------------------------------------
# [SECTION 2] 뷰(View) 함수
# ---------------------------------------------------------

# 1. 통합 대시보드
def view_dashboard(sh, pjt_list):
    st.title("📊 통합 대시보드 (현황 브리핑)")
    cols = st.columns(2)
    for idx, p_name in enumerate(pjt_list):
        with cols[idx % 2]:
            with st.container(border=True):
                try:
                    ws = safe_api_call(sh.worksheet, p_name)
                    data = safe_api_call(ws.get_all_values)
                    
                    pm_name = "미지정"
                    this_w = "금주 실적 미입력"
                    next_w = "차주 계획 미입력"
                    
                    if len(data) > 0:
                        header = data[0][:8]
                        df = pd.DataFrame([r[:8] for r in data[1:]], columns=header) if len(data) > 1 else pd.DataFrame(columns=header)
                        
                        if len(data[0]) > 8 and str(data[0][8]).strip(): pm_name = str(data[0][8]).strip()
                        if len(data) > 1 and len(data[1]) > 9 and str(data[1][9]).strip(): this_w = str(data[1][9]).strip()
                        if len(data) > 1 and len(data[1]) > 10 and str(data[1][10]).strip(): next_w = str(data[1][10]).strip()
                    else:
                        df = pd.DataFrame()

                    if not df.empty and '진행률' in df.columns:
                        avg_act = round(pd.to_numeric(df['진행률'], errors='coerce').fillna(0).mean(), 1)
                        avg_plan = round(df.apply(lambda r: calc_planned_progress(r.get('시작일'), r.get('종료일')), axis=1).mean(), 1)
                    else:
                        avg_act = 0.0; avg_plan = 0.0
                    
                    status_ui = "🟢 정상"
                    b_style = "status-normal"
                    if (avg_plan - avg_act) >= 10:
                        status_ui = "🔴 지연"
                        b_style = "status-delay"
                    elif avg_act >= 100: 
                        status_ui = "🔵 완료"
                        b_style = "status-done"
                    
                    # 헤더: 2단 구성 유지
                    h_col1, h_col2 = st.columns([7.3, 2.7], gap="small")
                    
                    with h_col1:
                        # [핵심 수정] color 속성을 var(--text-color)로 변경하여 다크모드 대응
                        st.markdown(f"""
                            <div style="display: flex; align-items: center; flex-wrap: wrap; gap: 6px; margin-top: 2px;">
                                <h4 style="color: var(--text-color); font-weight:700; margin:0; font-size:clamp(13.5px, 3.5vw, 16px); word-break:keep-all; line-height:1.2;">
                                    🏗️ {p_name}
                                </h4>
                                <span class="pm-tag" style="margin:0;">PM: {pm_name}</span>
                                <span class="status-badge {b_style}" style="margin:0;">{status_ui}</span>
                            </div>
                        """, unsafe_allow_html=True)
                        
                    with h_col2:
                        st.button(
                            "🔍 상세 보기", 
                            key=f"btn_go_{p_name}", 
                            on_click=navigate_to_project, 
                            args=(p_name,), 
                            use_container_width=True
                        )
                    
                    # 정보 표시 영역
                    st.markdown(f'''
                        <div style="margin-bottom:4px; margin-top:2px;">
                            <p style="font-size:12.5px; color: var(--text-color); opacity: 0.7; margin-top:0; margin-bottom:4px;">계획: {avg_plan}% | 실적: {avg_act}%</p>
                            <div class="weekly-box" style="margin-top:0;"><b>[금주]</b> {this_w}<br><b>[차주]</b> {next_w}</div>
                        </div>
                    ''', unsafe_allow_html=True)
                    
                    # 진행바 표시
                    st.progress(min(1.0, max(0.0, avg_act/100)))
                    
                except Exception as e:
                    st.warning(f"'{p_name}' 데이터를 로드하지 못했습니다.")

# 2. 프로젝트 상세 관리
def view_project_detail(sh, pjt_list):
    st.title("🏗️ 프로젝트 상세
