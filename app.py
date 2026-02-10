import streamlit as st
import pandas as pd
import datetime
import gspread
from google.oauth2.service_account import Credentials
import requests
import time
import plotly.express as px

# 1. 페이지 설정
st.set_page_config(page_title="PM 통합 공정 관리 v1.0.2", page_icon="🏗️", layout="wide")

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
# [SECTION 1] 백엔드 및 인증 로직
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
# [SECTION 2] 일 발전량 조회 화면 (이사님 요청 반영)
# ---------------------------------------------------------

def show_daily_solar(sh):
    st.title("📅 일 발전량 통계 분석")
    
    try:
        # DB 로드
        ws = sh.worksheet('Solar_DB')
        df = pd.DataFrame(ws.get_all_records())
        
        if df.empty:
            st.warning("데이터가 없습니다. 상단 동기화 기능을 먼저 이용해주세요.")
            return

        df['날짜'] = pd.to_datetime(df['날짜'])
        df['연도'] = df['날짜'].dt.year
        df['월'] = df['날짜'].dt.month
        
        # 필터 레이아웃
        col1, col2 = st.columns([1, 3])
        sel_year = col1.selectbox("조회 연도", sorted(df['연도'].unique(), reverse=True))
        
        # 데이터 필터링
        y_df = df[df['연도'] == sel_year]
        
        # 1. 1년 전체 평균 수치 표기
        yearly_avg = round(y_df['발전시간'].mean(), 2)
        st.metric(label=f"✨ {sel_year}년 전체 평균 발전시간", value=f"{yearly_avg} h / 일")
        
        # 2. 1월~12월 월간 평균 그래프
        m_avg = y_df.groupby('월')['발전시간'].mean().reset_index()
        # 모든 월(1~12)이 표시되도록 보정
        all_months = pd.DataFrame({'월': range(1, 13)})
        m_avg = pd.merge(all_months, m_avg, on='월', how='left').fillna(0)
        
        fig = px.bar(m_avg, x='월', y='발전시간', 
                     text_auto='.1f',
                     title=f"{sel_year}년 월별 평균 발전시간 추이 (1월~12월)",
                     labels={'발전시간': '평균 발전시간 (h)'},
                     color_discrete_sequence=['#f1c40f'])
        
        fig.update_layout(xaxis=dict(tickmode='linear', tick0=1, dtick=1))
        st.plotly_chart(fig, use_container_width=True)
        
        # 상세 데이터 표
        with st.expander("📝 상세 데이터 보기"):
            st.dataframe(y_df.sort_values('날짜', ascending=False), use_container_width=True)

    except Exception as e:
        st.error(f"데이터 조회 중 오류가 발생했습니다: {e}")

# ---------------------------------------------------------
# [SECTION 3] 메인 컨트롤러 및 메뉴 구성
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
    except: st.write("현장을 선택하여 공정 데이터를 입력해주세요.")

if check_password():
    client = get_client(); sh = client.open('pms_db')
    pjt_list = [ws.title for ws in sh.worksheets() if ws.title not in ['weekly_history', 'conflict', 'Sheet1', 'KPI', 'Solar_DB']]
    
    if "page" not in st.session_state: st.session_state["page"] = "home"
    if "pjt_idx" not in st.session_state: st.session_state["pjt_idx"] = 0

    # 사이드바 구성
    st.sidebar.title("📁 PMO 센터"); st.sidebar.write(f"👤 **{st.session_state['user_id']} 이사님**")
    st.sidebar.markdown("---")
    
    if st.sidebar.button("🏠 1. 전체 대시보드", use_container_width=True):
        st.session_state["page"], st.session_state["pjt_idx"] = "home", 0; st.rerun()

    st.sidebar.markdown("### ☀️ 2. 태양광 분석")
    if st.sidebar.button("⏱️ 시간별 발전량 조회", use_container_width=True):
        st.session_state["page"], st.session_state["pjt_idx"] = "solar_hr", 0; st.rerun()
    if st.sidebar.button("📅 일 발전량 조회 (1년)", use_container_width=True):
        st.session_state["page"], st.session_state["pjt_idx"] = "solar_day", 0; st.rerun()

    if st.sidebar.button("📉 3. 경영지표 (KPI)", use_container_width=True):
        st.session_state["page"], st.session_state["pjt_idx"] = "kpi", 0; st.rerun()

    st.sidebar.markdown("---"); st.sidebar.markdown("### 🏗️ 4. 프로젝트 목록")
    pjt_choice = st.sidebar.selectbox("현장 선택 (팝업)", ["현장을 선택하세요"] + pjt_list, index=st.session_state["pjt_idx"])
    
    if pjt_choice != "현장을 선택하세요":
        st.session_state["page"], st.session_state["current_pjt"] = "detail", pjt_choice
    
    if st.sidebar.button("➕ 새 프로젝트 등록", use_container_width=True):
        st.session_state["page"], st.session_state["pjt_idx"] = "new_pjt", 0; st.rerun()

    st.sidebar.markdown("---")
    if st.sidebar.button("🔓 로그아웃", use_container_width=True):
        for k in list(st.session_state.keys()): del st.session_state[k]
        st.rerun()

    # 페이지 라우팅
    pg = st.session_state["page"]
    if pg == "home": show_home(sh, pjt_list)
    elif pg == "solar_day": show_daily_solar(sh)
    elif pg == "solar_hr":
        st.title("⏱️ 시간별 발전량 조회")
        st.info("준비 중인 기능입니다.")
    elif pg == "kpi":
        st.title("📉 경영지표 (KPI)")
        try: st.dataframe(pd.DataFrame(sh.worksheet('KPI').get_all_records()), use_container_width=True)
        except: st.error("KPI 시트가 없습니다.")
    elif pg == "detail":
        from google.oauth2.service_account import Credentials # 내부 호출 방지용 재선언
        st.title(f"🏗️ {st.session_state['current_pjt']} 상세 관리")
        st.write("공정표 및 현황 보고 기능을 로드 중입니다...")
