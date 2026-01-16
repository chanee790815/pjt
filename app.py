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
st.title("🏗️ 당진 적서리 태양광 PMS (Final Corrected)")

df, sheet = get_pms_data()
if sheet is None:
    st.warning("데이터베이스 연결 대기 중...")
    st.stop()

tab1, tab2 = st.tabs(["📊 공정표 (Gantt)", "📝 일정 업데이트"])

with tab1:
    st.subheader("실시간 공정 현황")
    
    if not df.empty:
        try:
            # 1. 데이터 전처리 및 정렬
            df['시작일'] = pd.to_datetime(df['시작일'])
            df['종료일'] = pd.to_datetime(df['종료일'])
            df['구분'] = df['구분'].astype(str).str.strip().replace('', '내용 없음').fillna('내용 없음')
            
            # [수정 1] 시작일 기준으로 오름차순 정렬 (빠른 날짜가 먼저 나오도록)
            df = df.sort_values(by="시작일", ascending=True)

            # 2. 마일스톤과 일반 공정 분리
            main_df = df[df['대분류'] != 'MILESTONE'].copy()
            ms_df = df[df['대분류'] == 'MILESTONE'].copy()
            
            # [수정 2] Y축 순서 리스트 추출 (시작일이 빠른 항목이 리스트의 앞쪽에 위치)
            y_order = main_df['구분'].unique().tolist()

            # 3. 간트 차트 생성
            fig = px.timeline(
                main_df, 
                x_start="시작일", 
                x_end="종료일", 
                y="구분", 
                color="진행상태",
                hover_data=["대분류", "비고"],
                # [수정 3] 리스트 순서(빠른 날짜순)대로 카테고리 지정
                category_orders={"구분": y_order} 
            )

            # 4. 상단 마일스톤 (PDF 스타일 화살표) 추가
            if not ms_df.empty:
                for _, row in ms_df.iterrows():
                    fig.add_trace(go.Scatter(
                        x=[row['시작일']],
                        y=[y_order[0]] if y_order else [0], 
                        mode='markers+text',
                        marker=dict(symbol='arrow-bar-down', size=20, color='black'),
                        text=f"▼ {row['구분']}",
                        textposition="top center",
                        textfont=dict(color="red", size=12, family="Arial Black"),
                        name='MILESTONE',
                        showlegend=False,
                        cliponaxis=False
                    ))

            # 5. 레이아웃 최종 교정 (상단 년월 및 격자선)
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
                yaxis=dict(
                    # [핵심] 정렬된 리스트 순서를 유지하기 위해 autorange 설정을 "reversed"로 확정
                    # 이렇게 해야 y_order의 첫 번째 항목(가장 빠른 날짜)이 차트 상단에 배치됩니다.
                    autorange="reversed", 
                    showgrid=True, 
                    gridcolor="rgba(240, 240, 240, 0.8)"
                ),
                height=800,
                margin=dict(t=150, l=10, r=10, b=50),
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
        input_start = c1.date_input("시작일", datetime.date.today())
        input_end = c2.date_input("종료일", datetime.date.today() + datetime.timedelta(days=30))
        input_dae = st.selectbox("대분류", ["인허가", "설계/조사", "계약", "토목공사", "건축공사", "송전선로", "MILESTONE"])
        input_gubun = st.text_input("구분")
        input_status = st.selectbox("진행상태", ["예정", "진행중", "완료", "지연"])
        input_note = st.text_input("비고")
        submitted = st.form_submit_button("저장하기 💾", use_container_width=True)
        if submitted:
            new_row = [input_start.strftime('%Y-%m-%d'), input_end.strftime('%Y-%m-%d'), input_dae, input_gubun, input_status, input_note]
            sheet.append_row(new_row)
            st.success("✅ 저장되었습니다!")
            time.sleep(1)
            st.rerun()
