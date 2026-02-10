import streamlit as st
import pandas as pd
import datetime
import gspread
from google.oauth2.service_account import Credentials
import requests
import time
import plotly.express as px

# 1. 페이지 설정
st.set_page_config(page_title="PM 통합 공정 관리 v1.0.1", page_icon="🏗️", layout="wide")

# --- [UI] 디자인 및 저작권 문구 ---
st.markdown("""
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    html, body, [class*="css"] { font-family: 'Pretendard', sans-serif; }
    section[data-testid="stSidebar"] { background-color: #f8f9fa; border-right: 1px solid #eee; }
    .footer { position: fixed; left: 0; bottom: 0; width: 100%; background-color: #f1f1f1; color: #555; text-align: center; padding: 5px; font-size: 11px; z-index: 100; }
    </style>
    <div class="footer">출처: 기상청 공공데이터포털 (ASOS 종관기상관측) | 본 데이터는 기상청에서 제공하는 공공데이터를 활용하였습니다.</div>
    """, unsafe_allow_html=True)

# ---------------------------------------------------------
# [SECTION 1] 백엔드 로직
# ---------------------------------------------------------

def check_password():
    if "password_correct" not in st.session_state: st.session_state["password_correct"] = False
    if st.session_state["password_correct"]: return True
    st.title("🏗️ PM 통합 관리 시스템") 
    with st.form("login_form"):
        u_id = st.text_input("아이디")
        u_pw = st.text_input("비밀번호", type="password")
        if st.form_submit_button("로그인"):
            db = st.secrets["passwords"]
            if u_id in db and u_pw == db[u_id]:
                st.session_state["password_correct"] = True
                st.session_state["user_id"] = u_id
                st.rerun()
            else: st.error("정보 불일치")
    return False

@st.cache_resource
def get_client():
    key_dict = dict(st.secrets["gcp_service_account"])
    if "private_key" in key_dict: key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")
    creds = Credentials.from_service_account_info(key_dict, scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
    return gspread.authorize(creds)

# ---------------------------------------------------------
# [SECTION 2] 페이지 렌더링 함수
# ---------------------------------------------------------

def show_home(sh, pjt_list):
    st.title("📊 프로젝트 통합 대시보드")
    try:
        hist_df = pd.DataFrame(sh.worksheet('weekly_history').get_all_records())
        for p in pjt_list:
            p_df = pd.DataFrame(sh.worksheet(p).get_all_records())
            prog = round(pd.to_numeric(p_df['진행률'], errors='coerce').mean(), 1) if '진행률' in p_df.columns else 0
            note = hist_df[hist_df['프로젝트명']==p].tail(1).iloc[0]['주요현황'] if not hist_df[hist_df['프로젝트명']==p].empty else "최신 브리핑 없음"
            st.info(f"**{p}** (진척률: {prog}%) \n\n {note}")
    except: st.error("대시보드 데이터를 불러올 수 없습니다.")

def show_hourly_solar():
    st.title("⏱️ 시간별 발전량 상세 조회")
    col1, col2 = st.columns(2)
    target_date = col1.date_input("조회 날짜", datetime.date.today() - datetime.timedelta(days=1))
    stn_id = col2.selectbox("관측 지점", [127, 108, 131, 159], format_func=lambda x: {127:"충주", 108:"서울", 131:"청주", 159:"부산"}[x])
    if st.button("데이터 분석 실행"):
        url = f'http://apis.data.go.kr/1360000/AsosHourlyInfoService/getWthrDataList?serviceKey=ba10959184b37d5a2f94b2fe97ecb2f96589f7d8724ba17f85fdbc22d47fb7fe&numOfRows=24&pageNo=1&dataType=JSON&dataCd=ASOS&dateCd=HR&stnIds={stn_id}&startDt={target_date.strftime("%Y%m%d")}&startHh=01&endDt={target_date.strftime("%Y%m%d")}&endHh=23'
        try:
            res = requests.get(url).json()
            items = res['response']['body']['items']['item']
            df = pd.DataFrame(items)
            df['icsr'] = pd.to_numeric(df['icsr'], errors='coerce').fillna(0)
            st.metric("예상 발전시간", f"{round(df['icsr'].sum() / 3.6, 2)} h")
            st.plotly_chart(px.area(df, x='tm', y='icsr', title=f"{target_date} 시간대별 일사량 추이"))
        except: st.error("API 연동 실패")

def show_daily_solar(sh):
    st.title("📅 일 발전량 조회 (1년/연도별)")
    # (일자료 분석 로직 v1.0.0 동일 유지)
    try:
        df = pd.DataFrame(sh.worksheet('Solar_DB').get_all_records())
        if not df.empty:
            df['날짜'] = pd.to_datetime(df['날짜'])
            df['연도'] = df['날짜'].dt.year
            df['월'] = df['날짜'].dt.month
            sel_year = st.selectbox("조회 연도 선택", sorted(df['연도'].unique(), reverse=True))
            y_df = df[df['연도']==sel_year]
            m_avg = y_df.groupby('월')['발전시간'].mean().reset_index()
            st.plotly_chart(px.bar(m_avg, x='월', y='발전시간', text_auto='.1f', title=f"{sel_year}년 월간 평균 발전시간"))
    except: st.info("Solar_DB 데이터를 수집해 주세요.")

def show_detail(p_name, sh):
    st.title(f"🏗️ {p_name} 상세 관리")
    t1, t2, t3, t4 = st.tabs(["📊 통합 공정표", "📝 일정 등록", "📢 현황 보고", "📜 히스토리"])
    try:
        df = pd.DataFrame(sh.worksheet(p_name).get_all_records())
        with t1:
            if not df.empty:
                df['시작일'] = pd.to_datetime(df['시작일'], errors='coerce')
                df['종료일'] = pd.to_datetime(df['종료일'], errors='coerce')
                st.plotly_chart(px.timeline(df.dropna(subset=['시작일','종료일']), x_start="시작일", x_end="종료일", y="구분", color="진행상태"))
                st.dataframe(df, use_container_width=True)
    except: st.error("시트 구조를 확인하세요.")

# ---------------------------------------------------------
# [SECTION 3] 메인 컨트롤러 (중복 페이지 전환 오류 해결)
# ---------------------------------------------------------

if check_password():
    client = get_client(); sh = client.open('pms_db')
    pjt_list = [ws.title for ws in sh.worksheets() if ws.title not in ['weekly_history', 'conflict', 'Sheet1', 'KPI', 'Solar_DB']]
    
    # 세션 상태 초기화
    if "page" not in st.session_state: st.session_state["page"] = "home"
    if "pjt_idx" not in st.session_state: st.session_state["pjt_idx"] = 0

    st.sidebar.title("📁 PMO 센터"); st.sidebar.write(f"👤 **{st.session_state['user_id']} 이사님**")
    st.sidebar.markdown("---")
    
    # 1. 전체 대시보드
    if st.sidebar.button("🏠 1. 전체 대시보드", use_container_width=True):
        st.session_state["page"] = "home"
        st.session_state["pjt_idx"] = 0 # 프로젝트 선택 초기화
        st.rerun()

    # 2. 태양광 분석
    st.sidebar.markdown("### ☀️ 2. 태양광 분석")
    if st.sidebar.button("⏱️ 시간별 발전량 조회", use_container_width=True):
        st.session_state["page"] = "solar_hr"
        st.session_state["pjt_idx"] = 0
        st.rerun()
    if st.sidebar.button("📅 일 발전량 조회 (1년)", use_container_width=True):
        st.session_state["page"] = "solar_day"
        st.session_state["pjt_idx"] = 0
        st.rerun()

    # 3. 경영지표
    if st.sidebar.button("📉 3. 경영지표 (KPI)", use_container_width=True):
        st.session_state["page"] = "kpi"
        st.session_state["pjt_idx"] = 0
        st.rerun()

    # 4. 프로젝트 목록
    st.sidebar.markdown("---"); st.sidebar.markdown("### 🏗️ 4. 프로젝트 목록")
    pjt_choice = st.sidebar.selectbox(
        "현장 선택 (팝업)", 
        ["현장을 선택하세요"] + pjt_list, 
        index=st.session_state["pjt_idx"]
    )
    
    if pjt_choice != "현장을 선택하세요":
        st.session_state["page"] = "detail"
        st.session_state["current_pjt"] = pjt_choice
    
    if st.sidebar.button("➕ 새 프로젝트 등록", use_container_width=True):
        st.session_state["page"] = "new_pjt"
        st.session_state["pjt_idx"] = 0
        st.rerun()

    st.sidebar.markdown("---")
    if st.sidebar.button("🔓 로그아웃", use_container_width=True):
        for k in list(st.session_state.keys()): del st.session_state[k]
        st.rerun()

    # 라우팅
    pg = st.session_state["page"]
    if pg == "home": show_home(sh, pjt_list)
    elif pg == "solar_hr": show_hourly_solar()
    elif pg == "solar_day": show_daily_solar(sh)
    elif pg == "kpi":
        st.title("📉 경영지표 (KPI)")
        try: st.dataframe(pd.DataFrame(sh.worksheet('KPI').get_all_records()), use_container_width=True)
        except: st.error("KPI 시트가 없습니다.")
    elif pg == "detail": show_detail(st.session_state["current_pjt"], sh)
