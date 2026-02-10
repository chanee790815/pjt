import streamlit as st
import pandas as pd
import datetime
import gspread
from google.oauth2.service_account import Credentials
import requests
import time
import plotly.express as px

# 1. 페이지 설정
st.set_page_config(page_title="PM 통합 공정 관리 v1.0.7", page_icon="🏗️", layout="wide")

st.markdown("""
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    html, body, [class*="css"] { font-family: 'Pretendard', sans-serif; }
    .footer { position: fixed; left: 0; bottom: 0; width: 100%; background-color: #f1f1f1; color: #555; text-align: center; padding: 5px; font-size: 11px; z-index: 100; }
    .metric-box { background-color: #ffffff; padding: 20px; border-radius: 10px; border: 1px solid #e0e0e0; text-align: center; margin-bottom: 20px; }
    </style>
    <div class="footer">출처: 기상청 공공데이터포털 (ASOS 종관기상관측 일자료) | 본 데이터는 기상청에서 제공하는 공공데이터를 활용하였습니다.</div>
    """, unsafe_allow_html=True)

# ---------------------------------------------------------
# [SECTION 1] 백엔드 및 안정화된 동기화 로직
# ---------------------------------------------------------

@st.cache_resource
def get_client():
    key_dict = dict(st.secrets["gcp_service_account"])
    if "private_key" in key_dict: key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")
    creds = Credentials.from_service_account_info(key_dict, scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
    return gspread.authorize(creds)

def sync_solar_data_stable(sh, stn_id, stn_name):
    """연도별로 나누어 안정적으로 2020~2026 데이터를 동기화"""
    try:
        db_ws = sh.worksheet('Solar_DB')
        SERVICE_KEY = 'ba10959184b37d5a2f94b2fe97ecb2f96589f7d8724ba17f85fdbc22d47fb7fe'
        all_new_rows = []
        
        # 2020년부터 현재 연도까지 순회
        current_year = datetime.date.today().year
        for year in range(2020, current_year + 1):
            start_dt = f"{year}0101"
            # 올해인 경우 어제 날짜까지만 조회
            if year == current_year:
                end_dt = (datetime.date.today() - datetime.timedelta(days=1)).strftime("%Y%m%d")
            else:
                end_dt = f"{year}1231"
            
            url = f'http://apis.data.go.kr/1360000/AsosDalyInfoService/getWthrDataList?serviceKey={SERVICE_KEY}&numOfRows=366&pageNo=1&dataType=JSON&dataCd=ASOS&dateCd=DAY&stnIds={stn_id}&startDt={start_dt}&endDt={end_dt}'
            
            try:
                res = requests.get(url, timeout=10).json()
                if 'response' in res and 'body' in res['response'] and 'items' in res['response']['body']:
                    items = res['response']['body']['items']['item']
                    for i in items:
                        icsr = float(i['sumIcsr']) if i.get('sumIcsr') else 0
                        all_new_rows.append([i['tm'], stn_name, round(icsr / 3.6, 2), icsr])
                time.sleep(0.2) # API 서버 보호를 위한 미세 지연
            except:
                continue # 특정 연도 실패 시 다음 연도로 진행

        if all_new_rows:
            db_ws.clear()
            db_ws.append_row(["날짜", "지점", "발전시간", "일사량합계"])
            db_ws.append_rows(all_new_rows)
            return len(all_new_rows)
    except Exception as e:
        st.error(f"상세 오류: {e}")
        return 0

# ---------------------------------------------------------
# [SECTION 2] 분석 화면 (오류 복구 버전)
# ---------------------------------------------------------

def show_daily_solar(sh):
    st.title("📅 일 발전량 연간 통계 분석 (2020-2026)")
    
    with st.expander("📥 과거 데이터 연도별 안정적 동기화"):
        st.info("데이터를 연도별로 나누어 수집하여 오류를 최소화합니다. (2020년~현재)")
        c1, c2 = st.columns([2, 1])
        stn = c1.selectbox("수집 지점 선택", [127, 108, 131, 159], format_func=lambda x: {127:"충주", 108:"서울", 131:"청주", 159:"부산"}[x])
        if c2.button("🚀 안정적 동기화 시작"):
            with st.spinner('연도별 데이터를 순차적으로 수집 중입니다...'):
                count = sync_solar_data_stable(sh, stn, {127:"충주", 108:"서울", 131:"청주", 159:"부산"}[stn])
                if count > 0: st.success(f"✅ {count}일치 데이터 동기화 완료!"); time.sleep(1); st.rerun()

    # 연도 선택 및 그래프 로직 (v1.0.6과 동일)
    year_list = list(range(2026, 2019, -1))
    sel_year = st.selectbox("📊 분석 연도를 선택하세요", year_list)
    
    try:
        df = pd.DataFrame(sh.worksheet('Solar_DB').get_all_records())
        if not df.empty:
            df['날짜'] = pd.to_datetime(df['날짜'])
            y_df = df[df['날짜'].dt.year == sel_year]
            if not y_df.empty:
                avg_val = round(y_df['발전시간'].mean(), 2)
                st.markdown(f'<div class="metric-box"><h2 style="color:#555;">✨ {sel_year}년 전체 평균 발전시간</h2><h1 style="color:#f1c40f; font-size:50px;">{avg_val} h / 일</h1></div>', unsafe_allow_html=True)
                y_df['월'] = y_df['날짜'].dt.month
                m_avg = y_df.groupby('월')['발전시간'].mean().reset_index()
                st.plotly_chart(px.bar(m_avg, x='월', y='발전시간', text_auto='.2f', color='발전시간', color_continuous_scale='YlOrRd'), use_container_width=True)
    except: st.info("동기화가 필요합니다.")

# ---------------------------------------------------------
# [SECTION 3] 메인 컨트롤러
# ---------------------------------------------------------

if "password_correct" not in st.session_state: st.session_state["password_correct"] = False
# (로그인 로직 생략)

if st.session_state.get("password_correct", True):
    client = get_client(); sh = client.open('pms_db')
    
    st.sidebar.title("📁 PMO 센터")
    st.sidebar.markdown("---")
    if st.sidebar.button("🏠 1. 전체 대시보드", use_container_width=True): st.session_state["page"] = "home"
    if st.sidebar.button("⏱️ 시간별 발전량 조회", use_container_width=True): st.session_state["page"] = "solar_hr"
    if st.sidebar.button("📅 일 발전량 조회 (1년)", use_container_width=True): st.session_state["page"] = "solar_day"
    if st.sidebar.button("📉 3. 경영지표 (KPI)", use_container_width=True): st.session_state["page"] = "kpi"
    
    if st.session_state.get("page") == "solar_day": show_daily_solar(sh)
    elif st.session_state.get("page") == "home": st.title("📊 통합 대시보드")
