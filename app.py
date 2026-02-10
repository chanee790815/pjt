import streamlit as st
import pandas as pd
import datetime
import gspread
from google.oauth2.service_account import Credentials
import time
import plotly.express as px
import plotly.graph_objects as go
import requests

# 1. 페이지 설정
st.set_page_config(page_title="PM 통합 공정 관리 v0.9.4", page_icon="🏗️", layout="wide")

# --- [UI] 디자인 커스텀 CSS ---
st.markdown("""
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    html, body, [class*="css"] {
        font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, system-ui, Roboto, sans-serif;
    }
    section[data-testid="stSidebar"] { background-color: #f0f2f6; }
    
    /* 사이드바 메뉴 버튼 스타일 */
    .stButton button {
        border-radius: 8px;
        text-align: left;
        padding: 10px;
        margin-bottom: 5px;
    }
    
    /* 하단 고정 메뉴 강조 스타일 */
    div.stButton > button[key^="nav_"] {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        font-weight: 600;
    }
    
    div.stButton > button[key="nav_solar"] {
        border-left: 5px solid #ff4b4b !important;
    }
    div.stButton > button[key="nav_kpi"] {
        border-left: 5px solid #0068c9 !important;
    }
    </style>
    """, unsafe_allow_html=True)

# ---------------------------------------------------------
# [SECTION 1] 데이터 처리 로직 (생략 없는 핵심 로직)
# ---------------------------------------------------------

def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False
    if st.session_state["password_correct"]: return True
    
    st.title("🏗️ PM 통합 관리 시스템") 
    with st.form("login_form"):
        user_id = st.text_input("아이디 (ID)")
        password = st.text_input("비밀번호 (PW)", type="password")
        if st.form_submit_button("로그인"):
            user_db = st.secrets["passwords"]
            if user_id in user_db and password == user_db[user_id]:
                st.session_state["password_correct"] = True
                st.session_state["user_id"] = user_id
                st.rerun()
            else: st.error("정보가 일치하지 않습니다.")
    return False

@st.cache_resource
def get_client():
    key_dict = dict(st.secrets["gcp_service_account"])
    if "private_key" in key_dict:
        key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")
    creds = Credentials.from_service_account_info(key_dict, scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
    return gspread.authorize(creds)

@st.cache_data(ttl=300)
def fetch_summary(_email):
    client = get_client()
    sh = client.open('pms_db')
    forbidden = ['weekly_history', 'conflict', 'Sheet1', 'KPI']
    all_ws = [ws for ws in sh.worksheets() if ws.title not in forbidden]
    pjt_names = [ws.title for ws in all_ws]
    
    try: hist_data = pd.DataFrame(sh.worksheet('weekly_history').get_all_records())
    except: hist_data = pd.DataFrame(columns=["날짜", "프로젝트명", "주요현황", "작성자"])

    summary = []
    for ws in all_ws:
        try:
            p_df = pd.DataFrame(ws.get_all_records())
            prog = round(pd.to_numeric(p_df['진행률'], errors='coerce').mean(), 1) if '진행률' in p_df.columns else 0
            note = hist_data[hist_data['프로젝트명'] == ws.title].tail(1).iloc[0]['주요현황'] if not hist_data[hist_data['프로젝트명'] == ws.title].empty else "최신 기록 없음"
            summary.append({"명칭": ws.title, "진척": prog if not pd.isna(prog) else 0, "현황": note})
        except: summary.append({"명칭": ws.title, "진척": 0, "현황": "연동 오류"})
    return pjt_names, summary, hist_data

# ---------------------------------------------------------
# [SECTION 2] 페이지 렌더링 (태양광 및 상세 관리)
# ---------------------------------------------------------

def show_solar_page():
    st.title("☀️ 태양광 발전 환경 분석")
    col1, col2 = st.columns(2)
    target_date = col1.date_input("조회 날짜", datetime.date.today() - datetime.timedelta(days=1))
    stn_id = col2.selectbox("관측 지점", [127, 108, 131, 159], format_func=lambda x: {127:"충주 (적서리)", 108:"서울", 131:"청주", 159:"부산"}[x])
    
    if st.button("데이터 분석 실행"):
        url = 'http://apis.data.go.kr/1360000/AsosHourlyInfoService/getWthrDataList'
        params = {'serviceKey': 'ba10959184b37d5a2f94b2fe97ecb2f96589f7d8724ba17f85fdbc22d47fb7fe', 'pageNo': '1', 'numOfRows': '24', 'dataType': 'JSON', 'dataCd': 'ASOS', 'dateCd': 'HR', 'stnIds': str(stn_id), 'startDt': target_date.strftime("%Y%m%d"), 'startHh': '01', 'endDt': target_date.strftime("%Y%m%d"), 'endHh': '23'}
        try:
            res = requests.get(url, params=params).json()
            df = pd.DataFrame(res['response']['body']['items']['item'])
            df['icsr'] = pd.to_numeric(df['icsr'], errors='coerce').fillna(0)
            st.metric("☀️ 예상 발전시간", f"{round(df['icsr'].sum() / 3.6, 2)} h")
            st.plotly_chart(px.area(df, x='tm', y='icsr', title="일사량 변화 추이"))
        except: st.error("API 연동 실패")

def show_pjt_detail(p_name, sh, hist):
    st.title(f"🏗️ {p_name} 관리")
    t1, t2, t3, t4 = st.tabs(["📊 공정표", "📝 일정등록", "📢 현황보고", "📜 히스토리"])
    # (상세 로직 생략 - 이전 v0.9.3과 동일)

# ---------------------------------------------------------
# [SECTION 3] 메인 컨트롤러 (사이드바 메뉴 개편)
# ---------------------------------------------------------

if check_password():
    client = get_client()
    sh = client.open('pms_db')
    pjt_names, summary, hist_df = fetch_summary(st.secrets["gcp_service_account"]["client_email"])

    if "page" not in st.session_state: st.session_state["page"] = "home"

    # --- 사이드바 구성 ---
    st.sidebar.title("📁 PMO 센터")
    st.sidebar.write(f"👤 **{st.session_state['user_id']} 이사님**")
    
    st.sidebar.markdown("### 📋 프로젝트 목록")
    pjt_choice = st.sidebar.selectbox("현장 선택", ["선택하세요"] + pjt_names)
    if pjt_choice != "선택하세요":
        st.session_state["page"] = "detail"
        st.session_state["current_pjt"] = pjt_choice

    st.sidebar.markdown("---")
    st.sidebar.markdown("### 💎 전사 전용 메뉴")
    
    # 팝업 메뉴 대신 별도 버튼(링크)으로 구성
    if st.sidebar.button("🏠 전체 대시보드", key="nav_home", use_container_width=True):
        st.session_state["page"] = "home"
        st.rerun()
        
    if st.sidebar.button("☀️ 태양광 발전 분석", key="nav_solar", use_container_width=True):
        st.session_state["page"] = "solar"
        st.rerun()
        
    if st.sidebar.button("📉 경영지표 (KPI)", key="nav_kpi", use_container_width=True):
        st.session_state["page"] = "kpi"
        st.rerun()

    if st.sidebar.button("🔓 로그아웃", use_container_width=True):
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.rerun()

    # --- 페이지 라우팅 ---
    if st.session_state["page"] == "home":
        st.title("📊 프로젝트 통합 현황")
        for item in summary:
            st.info(f"**{item['명칭']}** (진척: {item['진척']}%) \n\n {item['현황']}")
    elif st.session_state["page"] == "solar":
        show_solar_page()
    elif st.session_state["page"] == "kpi":
        st.title("📈 전사 경영지표")
        st.info("구글 시트 'KPI' 탭 데이터를 분석 중입니다.")
    elif st.session_state["page"] == "detail":
        show_pjt_detail(st.session_state["current_pjt"], sh, hist_df)
