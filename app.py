import streamlit as st
import pandas as pd
import datetime
import gspread
from google.oauth2.service_account import Credentials
import requests
import time
import plotly.express as px

# 1. 페이지 설정 및 최신 UI 규격 적용
st.set_page_config(page_title="PM 통합 공정 관리 v1.1.2", page_icon="🏗️", layout="wide")

st.markdown("""
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    html, body, [class*="css"] { font-family: 'Pretendard', sans-serif; }
    .footer { position: fixed; left: 0; bottom: 0; width: 100%; background-color: #f1f1f1; color: #555; text-align: center; padding: 5px; font-size: 11px; z-index: 100; }
    </style>
    <div class="footer">출처: 기상청 공공데이터포털 | 본 데이터는 기상청에서 제공하는 공공데이터를 활용하였습니다.</div>
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

def sync_yearly_data_v112(sh, stn_id, stn_name, target_year):
    """표준 항목(sumGsr) 수집 및 문법 오류 해결 버전"""
    try:
        db_ws = sh.worksheet('Solar_DB')
        SERVICE_KEY = 'ba10959184b37d5a2f94b2fe97ecb2f96589f7d8724ba17f85fdbc22d47fb7fe'
        start_dt = f"{target_year}0101"
        end_dt = f"{target_year}1231" if int(target_year) < datetime.date.today().year else datetime.date.today().strftime("%Y%m%d")
        
        url = f'http://apis.data.go.kr/1360000/AsosDalyInfoService/getWthrDataList?serviceKey={SERVICE_KEY}&numOfRows=366&pageNo=1&dataType=JSON&dataCd=ASOS&dateCd=DAY&stnIds={stn_id}&startDt={start_dt}&endDt={end_dt}'
        res = requests.get(url, timeout=15).json()
        
        # 문법 오류 방지를 위한 정밀 파싱
        items = res.get('response', {}).get('body', {}).get('items', {}).get('item', [])
        new_rows = []
        for i in items:
            raw_gsr = i.get('sumGsr', '0')
            gsr = float(raw_gsr) if raw_gsr and str(raw_gsr).strip() != '' else 0.0
            new_rows.append([i['tm'], stn_name, round(gsr / 3.6, 2), gsr])
        
        if new_rows:
            # 기존 데이터 안전 교체
            all_data = db_ws.get_all_values()
            if len(all_data) > 1:
                df_all = pd.DataFrame(all_data[1:], columns=all_data[0])
                df_all['날짜'] = pd.to_datetime(df_all['날짜'], errors='coerce')
                # SettingWithCopyWarning 해결을 위해 .copy() 사용
                df_filtered = df_all.loc[df_all['날짜'].dt.year != int(target_year)].copy()
                db_ws.clear()
                db_ws.append_row(["날짜", "지점", "발전시간", "일사량합계"])
                if not df_filtered.empty:
                    df_filtered['날짜'] = df_filtered['날짜'].dt.strftime('%Y-%m-%d')
                    db_ws.append_rows(df_filtered.values.tolist())
            db_ws.append_rows(new_rows)
            return len(new_rows)
    except: return 0

# ---------------------------------------------------------
# [SECTION 2] 분석 화면 (UI 경고 해결 버전)
# ---------------------------------------------------------

def show_daily_solar(sh):
    st.title("📅 연도별 일 발전량 통계 분석")
    
    # 1. 연도 선택
    year_list = list(range(2026, 2019, -1))
    sel_year = st.selectbox("📊 분석 연도 선택", year_list, index=year_list.index(2023))
    
    try:
        df = pd.DataFrame(sh.worksheet('Solar_DB').get_all_records())
        if not df.empty:
            df['날짜'] = pd.to_datetime(df['날짜'], errors='coerce')
            y_df = df.loc[df['날짜'].dt.year == int(sel_year)].copy()
            
            if not y_df.empty:
                avg_val = round(y_df['발전시간'].mean(), 2)
                st.metric(f"✨ {sel_year}년 일 평균 발전시간", f"{avg_val} h")
                
                # 월별 그래프 (최신 width 규격 적용)
                y_df['월'] = y_df['날짜'].dt.month
                m_avg = y_df.groupby('월')['발전시간'].mean().reset_index()
                fig = px.bar(m_avg, x='월', y='발전시간', text_auto='.2f', color_discrete_sequence=['#f1c40f'])
                st.plotly_chart(fig, width='stretch') # 경고 해결
                
                # 데이터 테이블 (최신 width 규격 적용)
                st.dataframe(y_df.sort_values('날짜', ascending=False), width='stretch')
    except: st.info("데이터 동기화가 필요합니다.")

# (이하 로그인 및 사이드바 로직 v1.1.1과 동일)
