import streamlit as st
import pandas as pd
import datetime
import gspread
from google.oauth2.service_account import Credentials
import time
import json
import plotly.express as px
import plotly.graph_objects as go
import os

# 1. 페이지 설정
st.set_page_config(page_title="현장 공정 관리 PRO", page_icon="🏗️", layout="wide")

# --- 데이터 로드 함수 (구글 시트 + 로컬 백업) ---
@st.cache_data
def get_pms_data():
    # 1순위: 업로드된 파일 기반으로 생성한 적서리 PJT 데이터
    if os.path.exists('적서리_PJT_공정데이터.csv'):
        df = pd.read_csv('적서리_PJT_공정데이터.csv')
        return df, None # 수정 기능은 구글 시트 필요
    
    # 2순위: 구글 시트 연결 (기존 로직)
    try:
        if "gcp_service_account" in st.secrets:
            key_dict = dict(st.secrets["gcp_service_account"])
            if "private_key" in key_dict:
                key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")
            scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
            creds = Credentials.from_service_account_info(key_dict, scopes=scopes)
            client = gspread.authorize(creds)
            sh = client.open('pms_db') 
            worksheet = sh.sheet1
            data = worksheet.get_all_records()
            return pd.DataFrame(data), worksheet
    except:
        pass
    
    return pd.DataFrame(), None

# --- 메인 화면 상단 ---
st.title("🏗️ 당진 적서리 태양광 PMS (Rev. 2026-01-18.14)")

df_raw, worksheet = get_pms_data()
if df_raw.empty:
    st.warning("데이터를 불러올 수 없습니다. '적서리_PJT_공정데이터.csv' 파일이 있는지 확인해주세요.")
    st.stop()

# --- 사이드바 및 필터링 ---
st.sidebar.header("⚙️ 화면 설정")
is_mobile_mode = st.sidebar.toggle("📱 모바일 공정명 축소 (5글자)", value=False)
st.sidebar.divider()
st.sidebar.header("🔍 공정 필터링")
all_categories = ["전체"] + sorted(df_raw['대분류'].unique().tolist())
selected_cat = st.sidebar.multiselect("조회할 대분류 선택", all_categories, default="전체")

# 데이터 전처리
df = df_raw.copy()
df['시작일'] = pd.to_datetime(df['시작일']).dt.normalize()
df['종료일'] = pd.to_datetime(df['종료일']).dt.normalize()

if "전체" not in selected_cat:
    df = df[df['대분류'].isin(selected_cat)]

# [안전장치] 이동 범위 제한
min_date = df['시작일'].min()
max_date = df['종료일'].max()
limit_min = min_date - datetime.timedelta(days=60)
limit_max = max_date + datetime.timedelta(days=60)

# --- D-Day 카운터 ---
st.subheader("🚩 핵심 마일스톤 현황")
ms_only = df_raw[df_raw['대분류'] == 'MILESTONE'].copy()
if not ms_only.empty:
    cols_per_row = 4
    for i in range(0, len(ms_only), cols_per_row):
        cols = st.columns(min(cols_per_row, len(ms_only)-i))
        for j, (_, row) in enumerate(ms_only.iloc[i:i+cols_per_row].iterrows()):
            target_date = pd.to_datetime(row['시작일']).date()
            days_left = (target_date - datetime.date.today()).days
            cols[j].metric(
                label=row['구분'], 
                value=f"D-{days_left}" if days_left > 0 else f"D+ {abs(days_left)}", 
                delta=str(target_date)
            )

# --- 탭 구성 (통합 공정표 위주) ---
tab1, tab2, tab3 = st.tabs(["📊 통합 공정표", "📝 일정 등록", "⚙️ 관리 및 수정"])

with tab1:
    # (기존 차트 시각화 로직 유지)
    df_sorted = df.sort_values(by="시작일", ascending=False).reset_index(drop=True)
    main_df = df_sorted[df_sorted['대분류'] != 'MILESTONE'].copy()
    y_order = main_df['구분'].unique().tolist()[::-1]
    
    fig = px.timeline(
        main_df, x_start="시작일", x_end="종료일", y="구분", color="대분류",
        text="구분", hover_data=["시작일", "종료일", "비고"],
        category_orders={"구분": y_order}
    )
    
    fig.update_layout(
        xaxis=dict(range=[limit_min, limit_max], side="top", showgrid=True),
        yaxis=dict(fixedrange=False),
        height=800,
        dragmode="pan"
    )
    st.plotly_chart(fig, use_container_width=True)

# ... (이하 탭 2, 3 로직은 기존 소스와 동일)
