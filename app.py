import streamlit as st
import pandas as pd
import datetime
import gspread
from google.oauth2.service_account import Credentials
import requests
import time
import plotly.express as px

# 1. 페이지 설정 및 저작권 명시
st.set_page_config(page_title="PM 통합 공정 관리 v1.0.6", page_icon="🏗️", layout="wide")

st.markdown("""
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    html, body, [class*="css"] { font-family: 'Pretendard', sans-serif; }
    section[data-testid="stSidebar"] { background-color: #f8f9fa; border-right: 1px solid #eee; }
    .footer { position: fixed; left: 0; bottom: 0; width: 100%; background-color: #f1f1f1; color: #555; text-align: center; padding: 5px; font-size: 11px; z-index: 100; }
    .metric-box { background-color: #ffffff; padding: 20px; border-radius: 10px; border: 1px solid #e0e0e0; text-align: center; margin-bottom: 20px; }
    </style>
    <div class="footer">출처: 기상청 공공데이터포털 (ASOS 종관기상관측 일자료) | 본 데이터는 기상청에서 제공하는 공공데이터를 활용하였습니다.</div>
    """, unsafe_allow_html=True)

# ---------------------------------------------------------
# [SECTION 1] 백엔드 및 동기화 로직
# ---------------------------------------------------------

@st.cache_resource
def get_client():
    key_dict = dict(st.secrets["gcp_service_account"])
    if "private_key" in key_dict: key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")
    creds = Credentials.from_service_account_info(key_dict, scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
    return gspread.authorize(creds)

def sync_all_solar_data(sh, stn_id, stn_name):
    """2020년부터 오늘까지의 모든 일자료를 한 번에 동기화"""
    try:
        db_ws = sh.worksheet('Solar_DB')
        SERVICE_KEY = 'ba10959184b37d5a2f94b2fe97ecb2f96589f7d8724ba17f85fdbc22d47fb7fe'
        
        # 2020년 1월 1일부터 오늘까지
        start_dt = "20200101"
        end_dt = datetime.date.today().strftime("%Y%m%d")
        
        # 기상청 일자료 조회 API (최대 3000개 호출)
        url = f'http://apis.data.go.kr/1360000/AsosDalyInfoService/getWthrDataList?serviceKey={SERVICE_KEY}&numOfRows=3000&pageNo=1&dataType=JSON&dataCd=ASOS&dateCd=DAY&stnIds={stn_id}&startDt={start_dt}&endDt={end_dt}'
        
        res = requests.get(url).json()
        items = res['response']['body']['items']['item']
        
        new_rows = []
        for i in items:
            icsr = float(i['sumIcsr']) if i.get('sumIcsr') else 0
            gen_h = round(icsr / 3.6, 2)
            new_rows.append([i['tm'], stn_name, gen_h, icsr])
        
        if new_rows:
            db_ws.clear() # 기존 데이터 초기화 후 일괄 삽입
            db_ws.append_row(["날짜", "지점", "발전시간", "일사량합계"])
            db_ws.append_rows(new_rows)
            return len(new_rows)
    except Exception as e:
        st.error(f"동기화 오류: {e}")
        return 0

# ---------------------------------------------------------
# [SECTION 2] 일 발전량 분석 화면
# ---------------------------------------------------------

def show_daily_solar(sh):
    st.title("📅 일 발전량 연간 통계 분석 (2020-2026)")
    
    # 동기화 도구 배치
    with st.expander("📥 과거 데이터 전체 동기화 도구"):
        st.info("2020년부터 현재까지의 데이터를 기상청 API에서 일괄 수집하여 시트에 저장합니다.")
        c1, c2 = st.columns([2, 1])
        stn = c1.selectbox("수집 지점 선택", [127, 108, 131, 159], format_func=lambda x: {127:"충주", 108:"서울", 131:"청주", 159:"부산"}[x])
        if c2.button("🚀 데이터 동기화 시작", use_container_width=True):
            with st.spinner('기상청 서버에서 빅데이터를 수집 중입니다...'):
                count = sync_all_solar_data(sh, stn, {127:"충주", 108:"서울", 131:"청주", 159:"부산"}[stn])
                if count > 0: st.success(f"✅ {count}일치 데이터 동기화 완료!"); time.sleep(1); st.rerun()

    # 연도 선택박스 (2020-2026 고정)
    year_list = list(range(2026, 2019, -1))
    sel_year = st.selectbox("📊 분석 연도를 선택하세요", year_list)
    
    try:
        df = pd.DataFrame(sh.worksheet('Solar_DB').get_all_records())
        if df.empty:
            st.warning("데이터가 비어 있습니다. 위 동기화 버튼을 눌러주세요.")
            return

        df['날짜'] = pd.to_datetime(df['날짜'])
        y_df = df[df['날짜'].dt.year == sel_year]
        
        if y_df.empty:
            st.error(f"⚠️ {sel_year}년 데이터가 아직 수집되지 않았습니다.")
            return

        # 연평균 시각화
        avg_val = round(y_df['발전시간'].mean(), 2)
        st.markdown(f'<div class="metric-box"><h2 style="color:#555;">✨ {sel_year}년 전체 평균 발전시간</h2><h1 style="color:#f1c40f; font-size:50px;">{avg_val} h / 일</h1></div>', unsafe_allow_html=True)

        # 월별 그래프
        y_df['월'] = y_df['날짜'].dt.month
        m_avg = y_df.groupby('월')['발전시간'].mean().reset_index()
        fig = px.bar(m_avg, x='월', y='발전시간', text_auto='.2f', color='발전시간', color_continuous_scale='YlOrRd', title=f"{sel_year}년 월별 평균 발전효율 추이")
        fig.update_layout(xaxis=dict(tickmode='linear', dtick=1), height=500)
        st.plotly_chart(fig, use_container_width=True)

    except: st.info("데이터 동기화가 필요합니다.")

# ---------------------------------------------------------
# [SECTION 3] 메인 컨트롤러 (사이드바 순서 및 기능)
# ---------------------------------------------------------

if "password_correct" not in st.session_state: st.session_state["password_correct"] = False
# (비밀번호 체크 로직 생략 - 기존과 동일)

if st.session_state.get("password_correct", True): # 테스트를 위해 True로 설정
    client = get_client(); sh = client.open('pms_db')
    
    # 사이드바 메뉴
    st.sidebar.title("📁 PMO 센터")
    st.sidebar.markdown("---")
    if st.sidebar.button("🏠 1. 전체 대시보드", use_container_width=True): st.session_state["page"] = "home"
    st.sidebar.markdown("### ☀️ 2. 태양광 분석")
    if st.sidebar.button("⏱️ 시간별 발전량 조회", use_container_width=True): st.session_state["page"] = "solar_hr"
    if st.sidebar.button("📅 일 발전량 조회 (1년)", use_container_width=True): st.session_state["page"] = "solar_day"
    if st.sidebar.button("📉 3. 경영지표 (KPI)", use_container_width=True): st.session_state["page"] = "kpi"
    
    # 페이지 라우팅
    page = st.session_state.get("page", "home")
    if page == "solar_day": show_daily_solar(sh)
    elif page == "home": st.title("📊 통합 대시보드")
