import streamlit as st
import pandas as pd
import datetime
import gspread
from google.oauth2.service_account import Credentials
import requests
import time
import plotly.express as px

# 1. 페이지 설정
st.set_page_config(page_title="PM 통합 공정 관리 v1.0.8", page_icon="🏗️", layout="wide")

st.markdown("""
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    html, body, [class*="css"] { font-family: 'Pretendard', sans-serif; }
    .footer { position: fixed; left: 0; bottom: 0; width: 100%; background-color: #f1f1f1; color: #555; text-align: center; padding: 5px; font-size: 11px; z-index: 100; }
    .metric-box { background-color: #ffffff; padding: 20px; border-radius: 10px; border: 1px solid #e0e0e0; text-align: center; margin-bottom: 20px; }
    </style>
    <div class="footer">출처: 기상청 공공데이터포털 | 본 데이터는 기상청에서 제공하는 공공데이터를 활용하였습니다.</div>
    """, unsafe_allow_html=True)

# ---------------------------------------------------------
# [SECTION 1] 백엔드 및 선택적 연도 수집 로직
# ---------------------------------------------------------

@st.cache_resource
def get_client():
    key_dict = dict(st.secrets["gcp_service_account"])
    if "private_key" in key_dict: key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")
    creds = Credentials.from_service_account_info(key_dict, scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
    return gspread.authorize(creds)

def add_yearly_solar_data(sh, stn_id, stn_name, target_year):
    """선택한 연도의 1년치 데이터를 Solar_DB에 추가 (중복 체크)"""
    try:
        db_ws = sh.worksheet('Solar_DB')
        existing_data = db_ws.get_all_values()
        
        # 이미 해당 연도 데이터가 있는지 확인
        if len(existing_data) > 1:
            df_existing = pd.DataFrame(existing_data[1:], columns=existing_data[0])
            df_existing['날짜'] = pd.to_datetime(df_existing['날짜'])
            if target_year in df_existing['날짜'].dt.year.values:
                st.warning(f"⚠️ {target_year}년 데이터가 이미 존재합니다. 추가를 건너뜁니다.")
                return 0

        SERVICE_KEY = 'ba10959184b37d5a2f94b2fe97ecb2f96589f7d8724ba17f85fdbc22d47fb7fe'
        start_dt = f"{target_year}0101"
        
        # 올해인 경우 어제까지, 과거인 경우 12월 31일까지
        current_year = datetime.date.today().year
        if target_year == current_year:
            end_dt = (datetime.date.today() - datetime.timedelta(days=1)).strftime("%Y%m%d")
        else:
            end_dt = f"{target_year}1231"
            
        url = f'http://apis.data.go.kr/1360000/AsosDalyInfoService/getWthrDataList?serviceKey={SERVICE_KEY}&numOfRows=366&pageNo=1&dataType=JSON&dataCd=ASOS&dateCd=DAY&stnIds={stn_id}&startDt={start_dt}&endDt={end_dt}'
        
        res = requests.get(url, timeout=10).json()
        items = res['response']['body']['items']['item']
        
        new_rows = []
        for i in items:
            icsr = float(i['sumIcsr']) if i.get('sumIcsr') else 0
            new_rows.append([i['tm'], stn_name, round(icsr / 3.6, 2), icsr])
        
        if new_rows:
            db_ws.append_rows(new_rows) # 기존 데이터 아래에 추가
            return len(new_rows)
    except Exception as e:
        st.error(f"연도 추가 중 오류: {e}")
        return 0

# ---------------------------------------------------------
# [SECTION 2] 분석 화면 (선택적 수집 UI)
# ---------------------------------------------------------

def show_daily_solar(sh):
    st.title("📅 일 발전량 연간 통계 및 연도별 추가")
    
    with st.expander("📥 특정 연도 데이터 추가하기 (1년 단위)"):
        st.info("시트에 없는 연도를 선택하여 1년치 데이터를 보충하세요.")
        c1, c2, c3 = st.columns([1, 1, 1])
        add_stn = c1.selectbox("지점", [127, 108, 131, 159], format_func=lambda x: {127:"충주", 108:"서울", 131:"청주", 159:"부산"}[x])
        add_year = c2.selectbox("추가할 연도", list(range(2026, 2019, -1)))
        
        if c3.button(f"🚀 {add_year}년 데이터 추가", use_container_width=True):
            with st.spinner(f'{add_year}년 데이터를 가져오는 중...'):
                count = add_yearly_solar_data(sh, add_stn, {127:"충주", 108:"서울", 131:"청주", 159:"부산"}[add_stn], add_year)
                if count > 0: st.success(f"✅ {add_year}년 {count}일치 데이터 추가 완료!"); time.sleep(1); st.rerun()

    # 연도별 조회 로직
    year_list = list(range(2026, 2019, -1))
    sel_year = st.selectbox("📊 분석 연도 선택", year_list)
    
    try:
        df = pd.DataFrame(sh.worksheet('Solar_DB').get_all_records())
        if not df.empty:
            df['날짜'] = pd.to_datetime(df['날짜'])
            y_df = df[df['날짜'].dt.year == sel_year]
            if not y_df.empty:
                avg_val = round(y_df['발전시간'].mean(), 2)
                st.markdown(f'<div class="metric-box"><h3>✨ {sel_year}년 전체 평균 발전시간</h3><h1>{avg_val} h / 일</h1></div>', unsafe_allow_html=True)
                y_df['월'] = y_df['날짜'].dt.month
                m_avg = y_df.groupby('월')['발전시간'].mean().reset_index()
                st.plotly_chart(px.bar(m_avg, x='월', y='발전시간', text_auto='.2f', color='발전시간', color_continuous_scale='YlOrRd'), use_container_width=True)
            else: st.warning(f"{sel_year}년 데이터가 없습니다. 상단에서 추가해 주세요.")
    except: st.info("데이터를 먼저 수집해 주세요.")

# ---------------------------------------------------------
# [SECTION 3] 메인 컨트롤러 (생략 가능 부분은 기존과 동일)
# ---------------------------------------------------------

if "password_correct" not in st.session_state: st.session_state["password_correct"] = False
if st.session_state.get("password_correct", True):
    client = get_client(); sh = client.open('pms_db')
    
    st.sidebar.title("📁 PMO 센터")
    st.sidebar.markdown("---")
    if st.sidebar.button("🏠 1. 전체 대시보드", use_container_width=True): st.session_state["page"] = "home"
    st.sidebar.markdown("### ☀️ 2. 태양광 분석")
    if st.sidebar.button("⏱️ 시간별 발전량 조회", use_container_width=True): st.session_state["page"] = "solar_hr"
    if st.sidebar.button("📅 일 발전량 조회 (1년)", use_container_width=True): st.session_state["page"] = "solar_day"
    if st.sidebar.button("📉 3. 경영지표 (KPI)", use_container_width=True): st.session_state["page"] = "kpi"
    
    if st.session_state.get("page") == "solar_day": show_daily_solar(sh)
    elif st.session_state.get("page") == "home": st.title("📊 통합 대시보드")
