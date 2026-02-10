import streamlit as st
import pandas as pd
import datetime
import gspread
from google.oauth2.service_account import Credentials
import requests
import time
import plotly.express as px

# 1. 페이지 설정
st.set_page_config(page_title="PM 통합 공정 관리 v0.9.6", page_icon="🏗️", layout="wide")

# --- [UI] 디자인 커스텀 CSS ---
st.markdown("""
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    html, body, [class*="css"] { font-family: 'Pretendard', sans-serif; }
    section[data-testid="stSidebar"] { background-color: #f8f9fa; border-right: 1px solid #eee; }
    
    .stButton button {
        border-radius: 8px;
        text-align: left;
        margin-bottom: 8px;
        border: 1px solid #e0e0e0;
        background-color: white;
        transition: all 0.3s;
    }
    .stButton button:hover { border-color: #ff4b4b; color: #ff4b4b; }
    
    /* 메뉴 버튼 강조 */
    div.stButton > button[key="nav_solar"] { border-left: 5px solid #f1c40f !important; }
    div.stButton > button[key="nav_kpi"] { border-left: 5px solid #3498db !important; }
    div.stButton > button[key="nav_home"] { border-left: 5px solid #2ecc71 !important; }
    </style>
    """, unsafe_allow_html=True)

# ---------------------------------------------------------
# [SECTION 1] 백엔드 로직 (보안 및 DB 연결)
# ---------------------------------------------------------

def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False
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
            else: st.error("정보가 일치하지 않습니다.")
    return False

@st.cache_resource
def get_client():
    key_dict = dict(st.secrets["gcp_service_account"])
    if "private_key" in key_dict:
        key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")
    creds = Credentials.from_service_account_info(key_dict, scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
    return gspread.authorize(creds)

# ---------------------------------------------------------
# [SECTION 2] 데이터 자동 기록 및 분석 (DB 방식)
# ---------------------------------------------------------

def record_daily_solar(sh):
    """[1, 2단계] 매일 어제 데이터를 Solar_DB 시트에 자동 기록"""
    try:
        db_ws = sh.worksheet('Solar_DB')
        # 데이터 로딩 시 '날짜' 컬럼을 기준으로 중복 확인
        db_data = db_ws.get_all_values()
        existing_dates = [row[0] for row in db_data[1:]] if len(db_data) > 1 else []
        
        # 어제 날짜 확인
        yesterday = (datetime.date.today() - datetime.timedelta(days=1))
        target_date_str = yesterday.strftime("%Y-%m-%d")
        api_date_str = yesterday.strftime("%Y%m%d")

        if target_date_str not in existing_dates:
            # 충주(127) 지점 데이터 호출
            SERVICE_KEY = 'ba10959184b37d5a2f94b2fe97ecb2f96589f7d8724ba17f85fdbc22d47fb7fe'
            url = f'http://apis.data.go.kr/1360000/AsosHourlyInfoService/getWthrDataList?serviceKey={SERVICE_KEY}&numOfRows=24&pageNo=1&dataType=JSON&dataCd=ASOS&dateCd=HR&stnIds=127&startDt={api_date_str}&startHh=01&endDt={api_date_str}&endHh=23'
            
            res = requests.get(url).json()
            items = res['response']['body']['items']['item']
            df = pd.DataFrame(items)
            df['icsr'] = pd.to_numeric(df['icsr'], errors='coerce').fillna(0)
            
            gen_h = round(df['icsr'].sum() / 3.6, 2)
            total_mj = round(df['icsr'].sum(), 2)
            
            # 시트 기록: [날짜, 지점, 발전시간, 일사량합계]
            db_ws.append_row([target_date_str, "충주(적서리)", gen_h, total_mj])
            st.toast(f"✅ {target_date_str} 데이터가 DB에 기록되었습니다.")
    except Exception as e:
        pass # 시트 미생성 등으로 인한 에러 방지

def show_solar_stats(sh):
    """[3단계] DB 기반의 부하 제로 분석 페이지"""
    st.title("☀️ 태양광 데이터베이스 통계 분석")
    
    try:
        db_ws = sh.worksheet('Solar_DB')
        df = pd.DataFrame(db_ws.get_all_records())
        
        if df.empty:
            st.warning("'Solar_DB' 시트에 데이터가 없습니다. 제목줄을 확인하세요.")
            return

        df['날짜'] = pd.to_datetime(df['날짜'])
        df['연도'] = df['날짜'].dt.year
        df['월'] = df['날짜'].dt.month
        
        # 연도 선택
        sel_year = st.selectbox("분석 연도 선택", sorted(df['연도'].unique(), reverse=True))
        year_df = df[df['연도'] == sel_year]
        
        # 월별 평균 산출
        monthly_avg = year_df.groupby('월')['발전시간'].mean().reset_index()
        annual_avg = round(year_df['발전시간'].mean(), 2)

        # 요약 지표
        m1, m2, m3 = st.columns(3)
        m1.metric(f"📅 {sel_year}년 연평균 발전", f"{annual_avg} h")
        m2.metric("최고 효율 월", f"{int(monthly_avg.loc[monthly_avg['발전시간'].idxmax(), '월'])}월")
        m3.metric("누적 기록 일수", f"{len(year_df)} 일")

        # 시각화 차트
        fig = px.bar(monthly_avg, x='월', y='발전시간', text_auto='.1f', 
                     title=f"{sel_year}년 월별 평균 발전시간 추이",
                     color_discrete_sequence=['#f1c40f'])
        st.plotly_chart(fig, use_container_width=True)
        
        with st.expander("📊 누적 데이터 로그 확인"):
            st.dataframe(year_df.sort_values('날짜', ascending=False), use_container_width=True)
            
    except:
        st.error("'Solar_DB' 탭이 없거나 구조가 잘못되었습니다. [날짜, 지점, 발전시간, 일사량합계] 순서로 만드세요.")

# ---------------------------------------------------------
# [SECTION 3] 메인 컨트롤러 및 사이드바
# ---------------------------------------------------------

if check_password():
    client = get_client()
    sh = client.open('pms_db')
    
    # 앱 구동 시 자동 데이터 기록 실행
    record_daily_solar(sh)

    # 사이드바 메뉴 (개별 버튼 방식)
    st.sidebar.title("📁 PMO 센터")
    st.sidebar.write(f"👤 **{st.session_state['user_id']} 이사님**")
    st.sidebar.markdown("---")
    
    if st.sidebar.button("🏠 전체 대시보드", key="nav_home", use_container_width=True):
        st.session_state["page"] = "home"
    if st.sidebar.button("☀️ 태양광 DB 통계", key="nav_solar", use_container_width=True):
        st.session_state["page"] = "solar"
    if st.sidebar.button("📉 경영지표 (KPI)", key="nav_kpi", use_container_width=True):
        st.session_state["page"] = "kpi"
    
    st.sidebar.markdown("### 📋 프로젝트 목록")
    pjt_list = [ws.title for ws in sh.worksheets() if ws.title not in ['weekly_history', 'conflict', 'Sheet1', 'KPI', 'Solar_DB']]
    pjt_choice = st.sidebar.selectbox("현장 선택", ["선택하세요"] + pjt_list)
    
    if pjt_choice != "선택하세요":
        st.session_state["page"] = "detail"
        st.session_state["current_pjt"] = pjt_choice

    if st.sidebar.button("🔓 로그아웃", use_container_width=True):
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.rerun()

    # 페이지 라우팅
    page = st.session_state.get("page", "home")
    if page == "home":
        st.title("📊 프로젝트 통합 현황")
        st.info("각 프로젝트의 진척률과 기상 데이터를 연동하여 분석 중입니다.")
    elif page == "solar":
        show_solar_stats(sh)
    elif page == "kpi":
        st.title("📈 전사 경영지표")
    elif page == "detail":
        st.title(f"🏗️ {st.session_state['current_pjt']} 상세 관리")
