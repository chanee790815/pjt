import streamlit as st
import pandas as pd
import datetime
import gspread
from google.oauth2.service_account import Credentials
import time
import json
import plotly.express as px
import plotly.graph_objects as go

# 1. 페이지 설정
st.set_page_config(page_title="현장 공정 관리", page_icon="🏗️", layout="wide")

# --- 구글 시트 연결 함수 ---
@st.cache_resource
def get_connection():
    try:
        if "gcp_service_account" not in st.secrets:
            st.error("🚨 Secrets 설정이 비어있습니다!")
            return None
        key_dict = dict(st.secrets["gcp_service_account"])
        if "private_key" in key_dict:
            key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(key_dict, scopes=scopes)
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        st.error(f"🚨 인증 연결 실패: {e}")
        return None

def get_pms_data():
    client = get_connection()
    if client:
        try:
            sh = client.open('pms_db') 
            worksheet = sh.sheet1
            data = worksheet.get_all_records()
            return pd.DataFrame(data), worksheet
        except Exception as e:
             st.error(f"🚨 데이터 읽기 오류: {e}")
             return pd.DataFrame(), None
    return pd.DataFrame(), None

# --- 메인 화면 ---
st.title("🏗️ 당진 적서리 태양광 PMS (Milestone Ver.)")

df, sheet = get_pms_data()
if sheet is None:
    st.warning("데이터베이스 연결 대기 중...")
    st.stop()

tab1, tab2 = st.tabs(["📊 공정표 (Gantt)", "📝 일정 업데이트"])

with tab1:
    st.subheader("실시간 공정 현황")
    
    if not df.empty:
        try:
            # 데이터 전처리
            df['시작일'] = pd.to_datetime(df['시작일'])
            df['종료일'] = pd.to_datetime(df['종료일'])
            df['구분'] = df['구분'].astype(str).replace('', '인허가 보완/진행').fillna('인허가 보완/진행')
            
            # 마일스톤과 일반 공정 분리
            main_df = df[df['대분류'] != 'MILESTONE'].copy().sort_values(by="시작일")
            ms_df = df[df['대분류'] == 'MILESTONE'].copy()

            # 1. 기본 간트 차트 (일반 공정)
            fig = px.timeline(
                main_df, 
                x_start="시작일", 
                x_end="종료일", 
                y="구분", 
                color="진행상태",
                hover_data=["대분류", "비고"],
                category_orders={"구분": main_df["구분"].tolist()}
            )

            # 2. 상단 마일스톤 (화살표 및 텍스트) 추가
            if not ms_df.empty:
                fig.add_trace(
                    go.Scatter(
                        x=ms_df['시작일'],
                        # Y축의 가장 상단(첫 번째 공정 위)에 위치하도록 설정
                        y=[main_df['구분'].iloc[0]] * len(ms_df) if not main_df.empty else [0] * len(ms_df),
                        mode='markers+text',
                        marker=dict(
                            symbol='arrow-bar-down', # 아래 방향 화살표 형태
                            size=20,
                            color='black',
                        ),
                        text=ms_df['구분'],
                        textposition="top center", # 텍스트를 화살표 위에 표시
                        textfont=dict(color="red", size=12), # PDF 예시처럼 강조
                        name='주요 마일스톤',
                        cliponaxis=False
                    )
                )

            # 레이아웃 개선 (상단 년월 및 격자선)
            fig.update_layout(
                plot_bgcolor="white",
                xaxis=dict(
                    side="top",
                    showgrid=True,
                    gridcolor="rgba(220, 220, 220, 0.8)",
                    dtick="M1",
                    tickformat="%Y-%m",
                    ticks="outside"
                ),
                yaxis=dict(autorange="reversed", showgrid=True, gridcolor="LightGray"),
                height=700,
                margin=dict(t=150, l=10, r=10, b=10), # 상단 마일스톤 텍스트를 위한 여백 확대
                showlegend=True
            )
            
            fig.update_traces(marker_line_color="rgb(8,48,107)", marker_line_width=1, opacity=0.8)
            st.plotly_chart(fig, use_container_width=True)
            
        except Exception as e:
            st.warning(f"차트 생성 중 오류: {e}")

        st.divider()
        st.write("📋 상세 데이터 목록")
        st.dataframe(df, use_container_width=True, hide_index=True)

with tab2:
    st.subheader("일정 및 마일스톤 등록")
    with st.form("input_form"):
        c1, c2 = st.columns(2)
        input_start = c1.date_input("날짜 (마일스톤일 경우 당일 기준)", datetime.date.today())
        input_end = c2.date_input("종료일", datetime.date.today() + datetime.timedelta(days=30))
        
        c3, c4 = st.columns(2)
        input_dae = c3.selectbox("대분류", ["인허가", "설계/조사", "계약", "토목공사", "송전선로", "MILESTONE"])
        input_gubun = c4.text_input("구분", placeholder="예: MTR, GIS 선발주, 착공, 종합준공 등")
        
        input_status = st.selectbox("진행상태", ["예정", "진행중", "완료", "지연"])
        input_note = st.text_input("비고")
        
        submitted = st.form_submit_button("저장하기 💾", use_container_width=True)
        if submitted:
            new_row = [input_start.strftime('%Y-%m-%d'), input_end.strftime('%Y-%m-%d'), input_dae, input_gubun, input_status, input_note]
            sheet.append_row(new_row)
            st.success("✅ 저장되었습니다!")
            time.sleep(1)
            st.rerun()
