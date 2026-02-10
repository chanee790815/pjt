import streamlit as st
import pandas as pd
import datetime
import gspread
from google.oauth2.service_account import Credentials
import requests
import time
import plotly.express as px

# 1. 페이지 설정
st.set_page_config(page_title="PM 통합 공정 관리 v1.1.7", page_icon="🏗️", layout="wide")

# --- [UI] 디자인 및 저작권 문구 ---
st.markdown("""
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    html, body, [class*="css"] { font-family: 'Pretendard', sans-serif; }
    .footer { position: fixed; left: 0; bottom: 0; width: 100%; background-color: #f1f1f1; color: #555; text-align: center; padding: 5px; font-size: 11px; z-index: 100; }
    .metric-box { background-color: #ffffff; padding: 20px; border-radius: 10px; border: 1px solid #e0e0e0; text-align: center; margin-bottom: 20px; }
    </style>
    <div class="footer">출처: 기상청 공공데이터포털 (ASOS 종관기상관측) | 본 데이터는 기상청에서 제공하는 공공데이터를 활용하였습니다.</div>
    """, unsafe_allow_html=True)

# ---------------------------------------------------------
# [SECTION 1] 백엔드 로직
# ---------------------------------------------------------

@st.cache_resource
def get_client():
    key_dict = dict(st.secrets["gcp_service_account"])
    if "private_key" in key_dict: key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")
    creds = Credentials.from_service_account_info(key_dict, scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
    return gspread.authorize(creds)

def sync_yearly_data_v117(sh, stn_id, stn_name, target_year):
    try:
        db_ws = sh.worksheet('Solar_DB')
        SERVICE_KEY = 'ba10959184b37d5a2f94b2fe97ecb2f96589f7d8724ba17f85fdbc22d47fb7fe'
        start_dt = f"{target_year}0101"
        # 종료일 설정: 과거 연도는 1231, 올해(2025/2026)는 어제 날짜
        today = datetime.date.today()
        if int(target_year) < today.year:
            end_dt = f"{target_year}1231"
        else:
            end_dt = (today - datetime.timedelta(days=1)).strftime("%Y%m%d")
            
        url = f'http://apis.data.go.kr/1360000/AsosDalyInfoService/getWthrDataList?serviceKey={SERVICE_KEY}&numOfRows=366&pageNo=1&dataType=JSON&dataCd=ASOS&dateCd=DAY&stnIds={stn_id}&startDt={start_dt}&endDt={end_dt}'
        res = requests.get(url, timeout=15).json()
        items = res.get('response', {}).get('body', {}).get('items', {}).get('item', [])
        
        new_rows = []
        for i in items:
            raw_gsr = i.get('sumGsr', '0')
            gsr = float(raw_gsr) if raw_gsr and str(raw_gsr).strip() != '' else 0.0
            new_rows.append([i['tm'], stn_name, round(gsr / 3.6, 2), gsr])
            
        if new_rows:
            all_data = db_ws.get_all_values()
            df_filtered = pd.DataFrame(all_data[1:], columns=all_data[0]) if len(all_data) > 1 else pd.DataFrame()
            if not df_filtered.empty:
                df_filtered['날짜'] = pd.to_datetime(df_filtered['날짜'], errors='coerce')
                # 해당 지점의 해당 연도 데이터만 삭제 후 업데이트
                df_filtered = df_filtered.loc[~((df_filtered['날짜'].dt.year == int(target_year)) & (df_filtered['지점'] == stn_name))].dropna(subset=['날짜'])
            db_ws.clear()
            db_ws.append_row(["날짜", "지점", "발전시간", "일사량합계"])
            if not df_filtered.empty:
                df_filtered['날짜'] = df_filtered['날짜'].dt.strftime('%Y-%m-%d')
                db_ws.append_rows(df_filtered.values.tolist())
            db_ws.append_rows(new_rows)
            return len(new_rows)
    except: return 0

# ---------------------------------------------------------
# [SECTION 2] 페이지 렌더링 함수
# ---------------------------------------------------------

def show_daily_solar_v117(sh):
    st.title("📅 연도별 발전량 분석 리포트")
    
    with st.expander("📥 데이터 정밀 동기화 (기상청 API)"):
        c1, c2, c3 = st.columns([1, 1, 1])
        stn_map = {127:"충주", 108:"서울", 131:"청주", 159:"부산"}
        stn_id = c1.selectbox("지점", list(stn_map.keys()), format_func=lambda x: stn_map[x])
        year_to_sync = c2.selectbox("수집 연도", list(range(2026, 2019, -1)))
        if c3.button(f"🚀 {year_to_sync}년 {stn_map[stn_id]} 데이터 수집", use_container_width=True):
            with st.spinner('동기화 중...'):
                count = sync_yearly_data_v117(sh, stn_id, stn_map[stn_id], year_to_sync)
                if count > 0: st.success(f"{count}건 수집 완료!"); time.sleep(1); st.rerun()

    # 분석 연도 및 지점 선택
    col_a, col_b = st.columns(2)
    sel_stn = col_a.selectbox("📍 분석 지점 선택", ["서울", "충주", "청주", "부산"], index=1)
    sel_year = col_b.selectbox("📊 분석 연도 선택", list(range(2026, 2019, -1)), index=3) # 기본 2023

    # 그래프 출력 컨테이너
    with st.container():
        try:
            ws = sh.worksheet('Solar_DB')
            df = pd.DataFrame(ws.get_all_records())
            if not df.empty:
                df['날짜'] = pd.to_datetime(df['날짜'], errors='coerce')
                # 지점과 연도 동시 필터링
                target_df = df.loc[(df['날짜'].dt.year == int(sel_year)) & (df['지점'] == sel_stn)].copy()
                
                if not target_df.empty:
                    avg_val = round(pd.to_numeric(target_df['발전시간']).mean(), 2)
                    st.markdown(f'<div class="metric-box"><h3>✨ {sel_year}년 {sel_stn} 일 평균 발전시간</h3><h1>{avg_val} h</h1></div>', unsafe_allow_html=True)
                    
                    target_df['월'] = target_df['날짜'].dt.month
                    m_avg = target_df.groupby('월')['발전시간'].mean().reset_index()
                    fig = px.bar(m_avg, x='월', y='발전시간', text_auto='.2f', color='발전시간', color_continuous_scale='YlOrRd')
                    fig.update_layout(xaxis=dict(tickmode='linear', dtick=1))
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.warning(f"💡 {sel_year}년 {sel_stn} 데이터가 없습니다. 상단 동기화 도구로 수집해 주세요.")
        except: st.info("데이터 로딩 중...")

# ---------------------------------------------------------
# [SECTION 3] 메인 컨트롤러 (생략 로직은 v1.1.6과 동일)
# ---------------------------------------------------------

if "password_correct" not in st.session_state: st.session_state["password_correct"] = False
# (로그인 체크 로직 등... 기존과 동일)

if st.session_state.get("password_correct", True):
    client = get_client(); sh = client.open('pms_db')
    if "page" not in st.session_state: st.session_state["page"] = "home"
    
    # 사이드바 라우팅
    page = st.session_state.get("page")
    if page == "solar_day": show_daily_solar_v117(sh)
    elif page == "home": st.title("🏠 전체 대시보드")
