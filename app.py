import streamlit as st
import pandas as pd
import datetime
import gspread
from google.oauth2.service_account import Credentials
import requests
import time
import plotly.express as px

# 1. 페이지 설정
st.set_page_config(page_title="PM 통합 공정 관리 v1.0.5", page_icon="🏗️", layout="wide")

# --- [UI] 디자인 및 저작권 문구 ---
st.markdown("""
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    html, body, [class*="css"] { font-family: 'Pretendard', sans-serif; }
    section[data-testid="stSidebar"] { background-color: #f8f9fa; border-right: 1px solid #eee; }
    .footer { position: fixed; left: 0; bottom: 0; width: 100%; background-color: #f1f1f1; color: #555; text-align: center; padding: 5px; font-size: 11px; z-index: 100; }
    .metric-box { background-color: #ffffff; padding: 20px; border-radius: 10px; border: 1px solid #e0e0e0; text-align: center; }
    </style>
    <div class="footer">출처: 기상청 공공데이터포털 (ASOS 종관기상관측) | 본 데이터는 기상청에서 제공하는 공공데이터를 활용하였습니다.</div>
    """, unsafe_allow_html=True)

# ---------------------------------------------------------
# [SECTION 1] 백엔드 및 인증
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
# [SECTION 2] 일 발전량 조회 분석 (연도 선택 오류 해결 버전)
# ---------------------------------------------------------

def show_daily_solar(sh):
    st.title("📅 일 발전량 연간 통계 분석 (2020-2026)")
    
    # 1. 연도 선택 리스트 강제 생성 (2020년부터 2026년까지)
    year_list = [2026, 2025, 2024, 2023, 2022, 2021, 2020]
    sel_year = st.selectbox("📊 분석 연도를 선택하세요", year_list, index=0)
    
    try:
        ws = sh.worksheet('Solar_DB')
        df = pd.DataFrame(ws.get_all_records())
        
        if df.empty:
            st.warning("데이터가 없습니다. 사이드바 메뉴를 통해 데이터를 먼저 동기화해 주세요.")
            return

        # 날짜 데이터 처리
        df['날짜'] = pd.to_datetime(df['날짜'])
        df['연도'] = df['날짜'].dt.year
        df['월'] = df['날짜'].dt.month
        
        # 선택한 연도 데이터 필터링
        y_df = df[df['연도'] == sel_year]
        
        if y_df.empty:
            st.error(f"⚠️ {sel_year}년 데이터가 Solar_DB에 없습니다. 기상청 API 동기화가 필요합니다.")
            return

        st.markdown("---")

        # 2. 연간 평균 수치 표기
        yearly_avg = round(y_df['발전시간'].mean(), 2)
        st.markdown(f"""
            <div class="metric-box">
                <h3 style='margin:0; color:#555;'>✨ {sel_year}년 전체 평균 발전시간</h3>
                <h1 style='margin:0; color:#f1c40f; font-size:48px;'>{yearly_avg} h / 일</h1>
            </div>
        """, unsafe_allow_html=True)

        # 3. 1월~12월 월별 평균 그래프
        m_avg = y_df.groupby('월')['발전시간'].mean().reset_index()
        all_months = pd.DataFrame({'월': range(1, 13)})
        m_avg = pd.merge(all_months, m_avg, on='월', how='left').fillna(0)
        
        st.subheader(f"📈 {sel_year}년 월별 평균 발전시간 추이")
        fig = px.bar(m_avg, x='월', y='발전시간', 
                     text_auto='.2f',
                     color='발전시간',
                     color_continuous_scale='YlOrRd',
                     labels={'발전시간': '평균 시간(h)', '월': '조회 월'})
        
        fig.update_layout(xaxis=dict(tickmode='linear', dtick=1), height=450)
        st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"데이터 조회 중 오류 발생: {e}")

# ---------------------------------------------------------
# [SECTION 3] 메인 컨트롤러 (메뉴 구성)
# ---------------------------------------------------------

def show_home(sh, pjt_list):
    st.title("📊 통합 대시보드")
    st.write(f"현재 관리 중인 {len(pjt_list)}개 프로젝트의 상태를 요약합니다.")

if check_password():
    client = get_client(); sh = client.open('pms_db')
    pjt_list = [ws.title for ws in sh.worksheets() if ws.title not in ['weekly_history', 'conflict', 'Sheet1', 'KPI', 'Solar_DB']]
    
    if "page" not in st.session_state: st.session_state["page"] = "home"

    st.sidebar.title("📁 PMO 센터"); st.sidebar.write(f"👤 **{st.session_state['user_id']} 이사님**")
    st.sidebar.markdown("---")
    
    if st.sidebar.button("🏠 1. 전체 대시보드", use_container_width=True):
        st.session_state["page"] = "home"; st.rerun()

    st.sidebar.markdown("### ☀️ 2. 태양광 분석")
    if st.sidebar.button("⏱️ 시간별 발전량 조회", use_container_width=True):
        st.session_state["page"] = "solar_hr"; st.rerun()
    if st.sidebar.button("📅 일 발전량 조회 (1년)", use_container_width=True):
        st.session_state["page"] = "solar_day"; st.rerun()

    if st.sidebar.button("📉 3. 경영지표 (KPI)", use_container_width=True):
        st.session_state["page"] = "kpi"; st.rerun()

    st.sidebar.markdown("---"); st.sidebar.markdown("### 🏗️ 4. 프로젝트 목록")
    pjt_choice = st.sidebar.selectbox("현장 선택 (팝업)", ["현장을 선택하세요"] + pjt_list)
    
    if pjt_choice != "현장을 선택하세요":
        st.session_state["page"] = "detail"
        st.session_state["current_pjt"] = pjt_choice
    
    if st.sidebar.button("➕ 새 프로젝트 등록", use_container_width=True):
        st.session_state["page"] = "new_pjt"; st.rerun()

    st.sidebar.markdown("---")
    if st.sidebar.button("🔓 로그아웃", use_container_width=True):
        for k in list(st.session_state.keys()): del st.session_state[k]
        st.rerun()

    pg = st.session_state["page"]
    if pg == "home": show_home(sh, pjt_list)
    elif pg == "solar_day": show_daily_solar(sh)
    elif pg == "kpi":
        st.title("📉 경영지표 (KPI)")
        try: st.dataframe(pd.DataFrame(sh.worksheet('KPI').get_all_records()), use_container_width=True)
        except: st.error("KPI 시트가 없습니다.")
    elif pg == "detail":
        st.title(f"🏗️ {st.session_state['current_pjt']} 상세 관리")
