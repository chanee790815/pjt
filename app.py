import streamlit as st
import pandas as pd
import datetime
import gspread
from google.oauth2.service_account import Credentials
import requests
import time
import plotly.express as px

# 1. 페이지 설정
st.set_page_config(page_title="PM 통합 공정 관리 v1.0.4", page_icon="🏗️", layout="wide")

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
# [SECTION 1] 백엔드 및 API 수집 로직
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

def record_solar_batch_2020(sh, stn_id, stn_name):
    """2020년부터 현재까지의 일자료를 수집하여 Solar_DB에 저장"""
    try:
        db_ws = sh.worksheet('Solar_DB')
        SERVICE_KEY = 'ba10959184b37d5a2f94b2fe97ecb2f96589f7d8724ba17f85fdbc22d47fb7fe'
        
        # 2020년 1월 1일부터 어제까지 설정
        start_dt = "20200101"
        end_dt = (datetime.date.today() - datetime.timedelta(days=1)).strftime("%Y%m%d")
        
        # 기상청 일자료 조회 (최대 3000개 행 호출 - 5~6년치 커버)
        url = f'http://apis.data.go.kr/1360000/AsosDalyInfoService/getWthrDataList?serviceKey={SERVICE_KEY}&numOfRows=3000&pageNo=1&dataType=JSON&dataCd=ASOS&dateCd=DAY&stnIds={stn_id}&startDt={start_dt}&endDt={end_dt}'
        
        res = requests.get(url).json()
        items = res['response']['body']['items']['item']
        
        new_rows = []
        for i in items:
            icsr = float(i['sumIcsr']) if i.get('sumIcsr') else 0
            gen_h = round(icsr / 3.6, 2)
            new_rows.append([i['tm'], stn_name, gen_h, icsr])
        
        if new_rows:
            db_ws.clear()
            db_ws.append_row(["날짜", "지점", "발전시간", "일사량합계"])
            db_ws.append_rows(new_rows)
            return len(new_rows)
    except: return 0

# ---------------------------------------------------------
# [SECTION 2] 일 발전량 조회 분석 화면 (2020~ 조회 가능)
# ---------------------------------------------------------

def show_daily_solar(sh):
    st.title("📅 연도별 일 발전량 통계 (2020~)")
    
    with st.expander("📥 과거 데이터 전체 동기화 (2020년~현재)"):
        st.info("2020년부터의 데이터를 기상청 일자료 API로 일괄 수집합니다.")
        stn = st.selectbox("수집 지점", [127, 108, 131, 159], format_func=lambda x: {127:"충주", 108:"서울", 131:"청주", 159:"부산"}[x])
        if st.button("🚀 전체 데이터 동기화 시작"):
            with st.spinner('동기화 중...'):
                count = record_solar_batch_2020(sh, stn, {127:"충주", 108:"서울", 131:"청주", 159:"부산"}[stn])
                if count > 0: st.success(f"✅ {count}일치 데이터 수집 완료!"); st.rerun()

    try:
        df = pd.DataFrame(sh.worksheet('Solar_DB').get_all_records())
        if df.empty:
            st.warning("데이터가 없습니다. 위 동기화 버튼을 눌러주세요.")
            return

        df['날짜'] = pd.to_datetime(df['날짜'])
        df['연도'] = df['날짜'].dt.year
        df['월'] = df['날짜'].dt.month
        
        # 연도 선택 필터 (2020~2026)
        available_years = sorted(df['연도'].unique(), reverse=True)
        sel_year = st.selectbox("📊 분석 연도 선택", available_years)
        
        y_df = df[df['연도'] == sel_year]
        yearly_avg = round(y_df['발전시간'].mean(), 2)
        
        st.metric(label=f"✨ {sel_year}년 일 평균 발전시간", value=f"{yearly_avg} h")
        
        m_avg = y_df.groupby('월')['발전시간'].mean().reset_index()
        all_months = pd.DataFrame({'월': range(1, 13)})
        m_avg = pd.merge(all_months, m_avg, on='월', how='left').fillna(0)
        
        st.plotly_chart(px.bar(m_avg, x='월', y='발전시간', text_auto='.2f', title=f"{sel_year}년 월별 평균 발전시간", color_discrete_sequence=['#f1c40f']))
        with st.expander("📝 상세 데이터 보기"):
            st.dataframe(y_df.sort_values('날짜', ascending=False), use_container_width=True)
    except: st.info("데이터를 동기화해 주세요.")

# ---------------------------------------------------------
# [SECTION 3] 메인 컨트롤러 및 메뉴 구성
# ---------------------------------------------------------

def show_home(sh, pjt_list):
    st.title("📊 통합 대시보드")
    try:
        hist_df = pd.DataFrame(sh.worksheet('weekly_history').get_all_records())
        for p in pjt_list:
            p_df = pd.DataFrame(sh.worksheet(p).get_all_records())
            prog = round(pd.to_numeric(p_df['진행률'], errors='coerce').mean(), 1) if '진행률' in p_df.columns else 0
            note = hist_df[hist_df['프로젝트명']==p].tail(1).iloc[0]['주요현황'] if not hist_df[hist_df['프로젝트명']==p].empty else "최신 기록 없음"
            st.info(f"**{p}** (진척률: {prog}%) \n\n {note}")
    except: st.write("진행 중인 프로젝트를 로드 중입니다.")

if check_password():
    client = get_client(); sh = client.open('pms_db')
    pjt_list = [ws.title for ws in sh.worksheets() if ws.title not in ['weekly_history', 'conflict', 'Sheet1', 'KPI', 'Solar_DB']]
    
    if "page" not in st.session_state: st.session_state["page"] = "home"
    if "pjt_idx" not in st.session_state: st.session_state["pjt_idx"] = 0

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

    pg = st.session_state["page"]
    if pg == "home": show_home(sh, pjt_list)
    elif pg == "solar_day": show_daily_solar(sh)
    elif pg == "solar_hr":
        st.title("⏱️ 시간별 발전량 조회")
        st.info("당일 및 특정일의 정밀 시간대별 분석 화면입니다.")
    elif pg == "kpi":
        st.title("📉 경영지표 (KPI)")
        try: st.dataframe(pd.DataFrame(sh.worksheet('KPI').get_all_records()), use_container_width=True)
        except: st.error("KPI 시트가 없습니다.")
    elif pg == "detail":
        st.title(f"🏗️ {st.session_state['current_pjt']} 상세 관리")
