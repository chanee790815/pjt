## [PMS Revision History]
## 버전: Rev. 0.5.1
## 업데이트 요약:
## 1. 차트 시간축 최적화: 차트 상단에 '년-월' 단위 표시 (dtick 설정)
## 2. 공정 정렬 로직 적용: 시작일이 빠른 공정부터 상단에 표시되도록 정렬
## 3. 로그인 및 프로젝트 관리 기능 유지

import streamlit as st
import pandas as pd
import datetime
import gspread
from google.oauth2.service_account import Credentials
import time
import plotly.express as px

# 1. 페이지 설정
st.set_page_config(page_title="PM 통합 공정 관리 v0.5.1", page_icon="🏗️", layout="wide")

# --- 로그인 체크 함수 ---
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False
    if st.session_state["password_correct"]:
        return True

    st.title("🏗️ PM 통합 공정 관리 시스템")
    with st.form("login_form"):
        password = st.text_input("Password", type="password")
        if st.form_submit_button("Log In"):
            if password == st.secrets["auth"]["password"]:
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("😕 비밀번호가 틀렸습니다.")
    return False

if not check_password():
    st.stop()

# --- 구글 시트 연결 ---
@st.cache_resource
def get_client():
    try:
        key_dict = dict(st.secrets["gcp_service_account"])
        if "private_key" in key_dict:
            key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")
        creds = Credentials.from_service_account_info(key_dict, scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"🚨 인증 오류: {e}"); return None

# --- 메인 실행 ---
client = get_client()
if client:
    sh = client.open('pms_db')
    all_ws = sh.worksheets()
    pjt_names = [s.title for s in all_ws]
    
    st.sidebar.title("📁 PMO 프로젝트 센터")
    if st.sidebar.button("🔓 로그아웃"):
        st.session_state["password_correct"] = False
        st.rerun()
        
    menu = ["🏠 전체 대시보드"] + pjt_names
    selected = st.sidebar.selectbox("🎯 메뉴 선택", menu)

    # (중략: 프로젝트 추가 기능)
    
    if selected == "🏠 전체 대시보드":
        st.title("📊 프로젝트 통합 대시보드")
        # (대시보드 로직 유지)
        
    else:
        target_ws = sh.worksheet(selected)
        df_raw = pd.DataFrame(target_ws.get_all_records())
        st.title(f"🏗️ {selected} 상세 관리")
        t1, t2, t3 = st.tabs(["📊 통합 공정표", "📝 일정 등록", "⚙️ 현황 및 관리"])

        with t1:
            if not df_raw.empty:
                df = df_raw.copy()
                df['시작일'] = pd.to_datetime(df['시작일'], errors='coerce')
                df['종료일'] = pd.to_datetime(df['종료일'], errors='coerce')
                
                # [요청사항 반영] 시작일 기준 정렬 (시작일이 빠른 것이 위로)
                df = df.sort_values(by='시작일', ascending=True)
                
                # 마일스톤 (D-Day)
                ms = df[df['대분류'] == 'MILESTONE'].dropna(subset=['시작일'])
                if not ms.empty:
                    cols = st.columns(len(ms))
                    for i, (_, row) in enumerate(ms.iterrows()):
                        dday = (row['시작일'].date() - datetime.date.today()).days
                        cols[i].metric(row['구분'], f"D{dday:+d}")

                st.divider()

                # Gantt 차트 (날짜축 최적화)
                chart_df = df[df['대분류'] != 'MILESTONE'].dropna(subset=['시작일', '종료일'])
                if not chart_df.empty:
                    fig = px.timeline(chart_df, x_start="시작일", x_end="종료일", y="구분", color="진행상태",
                                     hover_data=["비고", "진행률", "담당자"])
                    
                    # [요청사항 반영] Y축 순서 고정 및 X축 상단 년/월 표시
                    fig.update_yaxes(autorange="reversed") 
                    fig.update_xaxes(
                        side="top", # 날짜를 차트 상단에 표시
                        dtick="M1", # 1개월 단위로 표시
                        tickformat="%Y-%m", # 년-월 형식
                        ticklabelmode="period"
                    )
                    fig.update_layout(height=500, template="plotly_white", margin=dict(t=100))
                    st.plotly_chart(fig, use_container_width=True)
                
                st.dataframe(df, use_container_width=True)
            else:
                st.info("데이터가 없습니다.")
        
        # (중략: t2 일정 등록, t3 현황 관리 로직 유지)
