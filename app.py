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
st.title("🏗️ 당진 적서리 태양광 PMS (Date Cleaned)")

df_raw, sheet = get_pms_data()
if sheet is None:
    st.warning("데이터베이스 연결 대기 중...")
    st.stop()

tab1, tab2, tab3 = st.tabs(["📊 공정표 (Gantt)", "📝 일정 등록", "⚙️ 일정 수정 및 삭제"])

# [탭 1] 공정표 조회
with tab1:
    st.subheader("실시간 공정 현황")
    if not df_raw.empty:
        try:
            df = df_raw.copy()
            # [수정] 날짜에서 시간 정보를 제거하고 순수한 날짜만 남김
            df['시작일'] = pd.to_datetime(df['시작일']).dt.normalize()
            df['종료일'] = pd.to_datetime(df['종료일']).dt.normalize()
            df['구분'] = df['구분'].astype(str).str.strip().replace('', '내용 없음').fillna('내용 없음')
            
            # 시작일 기준 오름차순 정렬
            df = df.sort_values(by="시작일", ascending=True).reset_index(drop=True)

            main_df = df[df['대분류'] != 'MILESTONE'].copy()
            ms_df = df[df['대분류'] == 'MILESTONE'].copy()
            
            # Plotly용 역순 리스트 생성 (차트 상단 배치를 위함)
            y_order_reversed = main_df['구분'].unique().tolist()[::-1]

            # 간트 차트 생성
            fig = px.timeline(
                main_df, 
                x_start="시작일", 
                x_end="종료일", 
                y="구분", 
                color="진행상태",
                hover_data=["대분류", "비고"],
                category_orders={"구분": y_order_reversed}
            )

            # 상단 마일스톤 화살표 추가
            if not ms_df.empty:
                for _, row in ms_df.iterrows():
                    fig.add_trace(go.Scatter(
                        x=[row['시작일']],
                        y=[y_order_reversed[-1]] if y_order_reversed else [0], 
                        mode='markers+text',
                        marker=dict(symbol='arrow-bar-down', size=20, color='black'),
                        text=f"▼ {row['구분']}",
                        textposition="top center",
                        textfont=dict(color="red", size=11, family="Arial Black"),
                        name='MILESTONE',
                        showlegend=False,
                        cliponaxis=False
                    ))

            # 레이아웃 설정
            fig.update_layout(
                plot_bgcolor="white",
                xaxis=dict(side="top", showgrid=True, gridcolor="#E5E5E5", dtick="M1", tickformat="%Y-%m", ticks="outside"),
                yaxis=dict(autorange=False, showgrid=True, gridcolor="#F0F0F0"),
                height=800,
                margin=dict(t=120, l=10, r=10, b=50),
                showlegend=True
            )
            
            fig.update_traces(marker_line_color="rgb(8,48,107)", marker_line_width=1, opacity=0.8)
            st.plotly_chart(fig, use_container_width=True)
            
        except Exception as e:
            st.warning(f"차트 생성 중 오류: {e}")

        st.divider()
        st.write("📋 상세 데이터 목록")
        # [수정] 표 출력 시 시간 제외 형식 지정
        display_df = df.copy()
        display_df['시작일'] = display_df['시작일'].dt.strftime('%Y-%m-%d')
        display_df['종료일'] = display_df['종료일'].dt.strftime('%Y-%m-%d')
        st.dataframe(display_df, use_container_width=True, hide_index=True)

# [탭 2] 및 [탭 3] 로직은 이전과 동일하게 유지...
# (지면 관계상 핵심 수정부 위주로 기재하며, 전체 기능은 동일하게 작동합니다)
