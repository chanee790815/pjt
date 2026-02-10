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
    <div class="footer">출처: 기상청 공공데이터포털 (ASOS 종관기상관측 일자료) | 본 데이터는 기상청에서 제공하는 공공데이터를 활용하였습니다.</div>
    """, unsafe_allow_html=True)

# ---------------------------------------------------------
# [SECTION 1] 백엔드 및 1년 단위 동기화 로직
# ---------------------------------------------------------

@st.cache_resource
def get_client():
    key_dict = dict(st.secrets["gcp_service_account"])
    if "private_key" in key_dict: key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")
    creds = Credentials.from_service_account_info(key_dict, scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
    return gspread.authorize(creds)

def sync_solar_by_year(sh, stn_id, stn_name, target_year):
    """지정한 1년치 데이터만 정밀 수집하여 Solar_DB에 누적"""
    try:
        db_ws = sh.worksheet('Solar_DB')
        SERVICE_KEY = 'ba10959184b37d5a2f94b2fe97ecb2f96589f7d8724ba17f85fdbc22d47fb7fe'
        
        start_dt = f"{target_year}0101"
        if target_year == datetime.date.today().year:
            end_dt = (datetime.date.today() - datetime.timedelta(days=1)).strftime("%Y%m%d")
        else:
            end_dt = f"{target_year}1231"
            
        url = f'http://apis.data.go.kr/1360000/AsosDalyInfoService/getWthrDataList?serviceKey={SERVICE_KEY}&numOfRows=366&pageNo=1&dataType=JSON&dataCd=ASOS&dateCd=DAY&stnIds={stn_id}&startDt={start_dt}&endDt={end_dt}'
        
        res = requests.get(url, timeout=10).json()
        if 'response' in res and 'body' in res['response'] and 'items' in res['response']['body']:
            items = res['response']['body']['items']['item']
            
            # 기존 데이터 로드 (중복 체크용)
            existing_data = db_ws.get_all_values()
            existing_dates = [row[0] for row in existing_data] if len(existing_data) > 1 else []
            
            new_rows = []
            for
