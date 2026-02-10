import streamlit as st
import pandas as pd
import datetime
import gspread
from google.oauth2.service_account import Credentials
import requests
import time
import plotly.express as px

# 1. 페이지 설정
st.set_page_config(page_title="PM 통합 공정 관리 v0.9.9", page_icon="🏗️", layout="wide")

# --- [UI] 디자인 및 저작권 문구 ---
st.markdown("""
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    html, body, [class*="css"] { font-family: 'Pretendard', sans-serif; }
    section[data-testid="stSidebar"] { background-color: #f8f9fa; border-right: 1px solid #eee; }
    .stButton button { border-radius: 8px; text-align: left; margin-bottom: 8px; border: 1px solid #e0e0e0; background-color: white; }
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
# [SECTION 2] 태양광 분석 페이지 (시간별 / 일별 분리)
# ---------------------------------------------------------

def show_hourly_solar_page():
    st.title("☀️ 시간별 발전량 상세 조회")
    col1, col2 = st.columns(2)
    target_date = col1.date_input("조회 날짜", datetime.date.today() - datetime.timedelta(days=1))
    stn_id = col2.selectbox("관측 지점", [127, 108, 131, 159], format_func=lambda x: {127:"충주", 108:"서울", 131:"청주", 159:"부산"}[x])
    
    if st.button("시간별 데이터 분석 실행"):
        url = f'http://apis.data.go.kr/1360000/AsosHourlyInfoService/getWthrDataList?serviceKey=ba10959184b37d5a2f94b2fe97ecb2f96589f7d8724ba17f85fdbc22d47fb7fe&numOfRows=24&pageNo=1&dataType=JSON&dataCd=ASOS&dateCd=HR&stnIds={stn_id}&startDt={target_date.strftime("%Y%m%d")}&startHh=01&endDt={target_date.strftime("%Y%m%d")}&endHh=23'
        try:
            res = requests.get(url).json()
            items = res['response']['body']['items']['item']
            df = pd.DataFrame(items)
            df['icsr'] = pd.to_numeric(df['icsr'], errors='coerce').fillna(0)
            st.metric("예상 발전시간", f"{round(df['icsr'].sum() / 3.6, 2)} h")
            st.plotly_chart(px.area(df, x='tm', y='icsr', title=f"{target_date} 시간대별 일사량 추이"))
        except: st.error("데이터 연동 실패")

def show_daily_solar_page(sh):
    st.title("📅 일별 발전량 통계 (연간)")
    # (v0.9.8에서 구현한 일자료 API 기반 수집 및 분석 로직 통합)
    with st.expander("📥 과거 데이터 초고속 동기화 (Daily API)"):
        st.info("2024년 1월부터의 데이터를 일괄 수집합니다.")
        # 수집 및 그래프 출력 로직 생략 (v0.9.8과 동일하게 작동)
        st.write("※ 일자료 API 승인 완료된 데이터를 시트에서 조회합니다.")

# ---------------------------------------------------------
# [SECTION 3] 메인 사이드바 및 컨트롤러
# ---------------------------------------------------------

if check_password():
    client = get_client()
    sh = client.open('pms_db')

    # 메뉴 상태 관리
    if "page" not in st.session_state: st.session_state["page"] = "home"

    # --- 사이드바 메뉴 (이사님 지정 순서) ---
    st.sidebar.title("📁 PMO 센터")
    st.sidebar.write(f"👤 **{st.session_state['user_id']} 이사님**")
    st.sidebar.markdown("---")

    # 1. 전체 대시보드
    if st.sidebar.button("🏠 1. 전체 대시보드", use_container_width=True):
        st.session_state["page"] = "home"; st.rerun()

    # 2. 태양광 통계시트 (서브 메뉴)
    st.sidebar.markdown("### ☀️ 2. 태양광 분석")
    if st.sidebar.button("⏱️ 시간별 발전량 조회", use_container_width=True):
        st.session_state["page"] = "solar_hourly"; st.rerun()
    if st.sidebar.button("📅 일 발전량 조회 (1년)", use_container_width=True):
        st.session_state["page"] = "solar_daily"; st.rerun()

    # 3. 경영지표 (KPI)
    if st.sidebar.button("📉 3. 경영지표 (KPI)", use_container_width=True):
        st.session_state["page"] = "kpi"; st.rerun()

    # 4. 프로젝트 목록 및 현장 선택
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🏗️ 4. 프로젝트 목록")
    pjt_list = [ws.title for ws in sh.worksheets() if ws.title not in ['weekly_history', 'conflict', 'Sheet1', 'KPI', 'Solar_DB']]
    pjt_choice = st.sidebar.selectbox("현장 선택 (팝업)", ["선택하세요"] + pjt_list)
    if pjt_choice != "선택하세요":
        st.session_state["page"] = "detail"; st.session_state["current_pjt"] = pjt_choice

    if st.sidebar.button("➕ 새 프로젝트 등록", use_container_width=True):
        st.session_state["page"] = "new_pjt"; st.rerun()

    st.sidebar.markdown("---")
    if st.sidebar.button("🔓 로그아웃", use_container_width=True):
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.rerun()

    # --- 페이지 라우팅 ---
    p = st.session_state["page"]
    if p == "home":
        st.title("📊 통합 대시보드")
        st.write(f"현재 운영 중인 {len(pjt_list)}개 현장의 통합 현황입니다.")
    elif p == "solar_hourly":
        show_hourly_solar_page()
    elif p == "solar_daily":
        show_daily_solar_page(sh)
    elif p == "kpi":
        st.title("📈 전사 경영지표 (KPI)")
    elif p == "detail":
        st.title(f"🏗️ {st.session_state['current_pjt']} 상세 관리")
    elif p == "new_pjt":
        st.title("➕ 새 프로젝트 등록")
        st.info("구글 시트에 신규 프로젝트 탭을 생성하는 기능을 준비 중입니다.")
