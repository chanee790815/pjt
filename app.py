import streamlit as st
import pandas as pd
import datetime
import gspread
from google.oauth2.service_account import Credentials
import time
import plotly.express as px

# 1. 페이지 설정
st.set_page_config(page_title="PM 통합 공정 관리 시스템", page_icon="🏗️", layout="wide")

# --- 구글 시트 연결 함수 ---
@st.cache_resource
def get_client():
    try:
        if "gcp_service_account" not in st.secrets:
            st.error("🚨 Streamlit Cloud의 Secrets 설정에 구글 서비스 계정 정보가 없습니다.")
            return None
        key_dict = dict(st.secrets["gcp_service_account"])
        if "private_key" in key_dict:
            key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(key_dict, scopes=scopes)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"🚨 구글 인증 연결 실패: {e}")
        return None

# --- 데이터 로드 함수 (오류 방지 강화) ---
def get_project_data(sh, project_name):
    try:
        worksheet = sh.worksheet(project_name)
        data = worksheet.get_all_records()
        if not data: # 헤더만 있고 데이터가 없는 경우
            return pd.DataFrame(columns=["시작일", "종료일", "대분류", "구분", "진행상태", "비고", "진행률", "담당자"]), worksheet
        return pd.DataFrame(data), worksheet
    except Exception as e:
        return pd.DataFrame(), None

# --- 사이드바 및 프로젝트 관리 ---
st.sidebar.title("📁 PMO 프로젝트 센터")

client = get_client()
if client:
    sh = client.open('pms_db')
    real_project_list = [s.title for s in sh.worksheets()]
else:
    st.stop()

selected_pjt = st.sidebar.selectbox("🎯 관리 프로젝트 선택", real_project_list)

# (중략: 프로젝트 추가/삭제 기능은 이전과 동일하게 유지 가능)

st.title(f"🏗️ {selected_pjt} 공정 관리 시스템")

# 데이터 로드
df_raw, worksheet = get_project_data(sh, selected_pjt)

if worksheet is None:
    st.warning("데이터베이스 연결 대기 중... 시트의 헤더를 확인해주세요.")
    st.stop()

# --- 탭 구성 ---
tab1, tab2, tab3 = st.tabs(["📊 통합 공정표", "📝 일정 등록", "⚙️ 관리 및 수정"])

# [탭 1] 통합 공정표 (보이지 않는 차트 문제 해결 부분)
with tab1:
    if not df_raw.empty and len(df_raw) > 0:
        # 날짜 데이터 정제 (중요!)
        df = df_raw.copy()
        df['시작일'] = pd.to_datetime(df['시작일'], errors='coerce')
        df['종료일'] = pd.to_datetime(df['종료일'], errors='coerce')
        
        # 1. 마일스톤 (D-Day)
        ms_only = df[df['대분류'] == 'MILESTONE'].dropna(subset=['시작일'])
        if not ms_only.empty:
            st.subheader("🚩 핵심 마일스톤")
            cols = st.columns(len(ms_only))
            for i, (_, row) in enumerate(ms_only.iterrows()):
                days_left = (row['시작일'].date() - datetime.date.today()).days
                cols[i].metric(row['구분'], f"D{days_left:+d}", str(row['시작일'].date()))
        
        st.divider()

        # 2. Gantt 차트 (일반 공정만 표시)
        chart_df = df[(df['대분류'] != 'MILESTONE')].dropna(subset=['시작일', '종료일'])
        
        if not chart_df.empty:
            fig = px.timeline(chart_df, x_start="시작일", x_end="종료일", y="구분", color="진행상태")
            fig.update_yaxes(autorange="reversed")
            fig.update_layout(height=500, template="plotly_white")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("💡 일반 공정 데이터가 없습니다. [일정 등록] 탭에서 '토목공사' 등을 추가해 보세요.")

        # 3. 데이터 테이블 (항상 보이게 설정)
        st.subheader("📋 전체 공정 데이터 리스트")
        st.dataframe(df_raw, use_container_width=True)
    else:
        st.info("💡 현재 시트에 저장된 데이터가 없습니다. 먼저 일정을 등록해 주세요.")

# ... (이하 탭 2, 3 로직 유지)
