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

        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        
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
st.title("🏗️ 당진 적서리 태양광 PMS (Final Optimized)")

# 데이터 로딩
df, sheet = get_pms_data()

if sheet is None:
    st.warning("데이터베이스 연결 대기 중...")
    st.stop()

# 탭 구성
tab1, tab2 = st.tabs(["📊 공정표 (Gantt)", "📝 일정 업데이트"])

# [탭 1] 간트 차트 및 조회
with tab1:
    st.subheader("실시간 공정 현황")
    
    if not df.empty:
        try:
            # 1. 데이터 타입 변환 및 전처리
            df['시작일'] = pd.to_datetime(df['시작일'])
            df['종료일'] = pd.to_datetime(df['종료일'])
            
            # 빈 구분을 '인허가 보완/진행'으로 채움 (차트 오류 방지)
            df['구분'] = df['구분'].astype(str).str.strip().replace('', '인허가 보완/진행').fillna('인허가 보완/진행')
            
            # [교정] 전체 데이터를 시작일 기준으로 오름차순 정렬
            df = df.sort_values(by="시작일", ascending=True)

            # 2. 마일스톤과 일반 공정 분리
            main_df = df[df['대분류'] != 'MILESTONE'].copy()
            ms_df = df[df['대분류'] == 'MILESTONE'].copy()
            
            # [교정] Y축 표시 순서를 시작일 순서대로 강제 리스트화
            y_order = main_df['구분'].unique().tolist()

            # 3. 간트 차트 생성 (일반 공정)
            fig = px.timeline(
                main_df, 
                x_start="시작일", 
                x_end="종료일", 
                y="구분", 
                color="진행상태",
                hover_data=["대분류", "비고"],
                category_orders={"구분": y_order}, # Y축 순서 고정
                title="당진 적서리 태양광 프로젝트 공정 스케줄"
            )

            # 4. 상단 마일스톤 (화살표 및 빨간 텍스트) 추가
            if not ms_df.empty:
                for _, row in ms_df.iterrows():
                    fig.add_trace(
                        go.Scatter(
                            x=[row['시작일']],
                            y=[y_order[0]] if y_order else [0], # 차트 최상단 항목 위치에 배치
                            mode='markers+text',
                            marker=dict(symbol='arrow-bar-down', size=20, color='black'),
                            text=f"▼ {row['구분']}", 
                            textposition="top center",
                            textfont=dict(color="red", size=12, family="Arial Black"),
                            name='주요 마일스톤',
                            showlegend=False,
                            cliponaxis=False
                        )
                    )

            # 5. 차트 레이아웃 및 스타일 최적화 (년월 상단, 격자선 추가)
            fig.update_layout(
                plot_bgcolor="white",          # 배경 흰색
                xaxis=dict(
                    side="top",                # 년월 표시를 상단으로
                    showgrid=True,             # 월별 구분 실선
                    gridcolor="rgba(220, 220, 220, 0.8)",
                    dtick="M1",                # 1개월 단위
                    tickformat="%Y-%m",
                    ticks="outside"
                ),
                yaxis=dict(
                    autorange="reversed",      # 상단부터 시간 순서대로 정렬됨
                    showgrid=True,             # 항목별 구분선
                    gridcolor="rgba(240, 240, 240, 0.8)"
                ),
                height=800,                    # 가독성을 위해 차트 높이 확대
                margin=dict(t=150, l=10, r=10, b=50), # 상단 마일스톤 공간 확보
                showlegend=True
            )
            
            # 막대 스타일 (테두리 추가로 표 느낌 강조)
            fig.update_traces(marker_line_color="rgb(8,48,107)", marker_line_width=1, opacity=0.8)
            
            st.plotly_chart(fig, use_container_width=True)
            
        except Exception as e:
            st.warning(f"차트 생성 중 오류: {e}")

        st.divider()
        st.write("📋 상세 데이터 목록")
        
        # 데이터 목록도 보기 좋게 날짜 형식 변환 후 출력
        display_df = df.copy()
        display_df['시작일'] = display_df['시작일'].dt.strftime('%Y-%m-%d')
        display_df['종료일'] = display_df['종료일'].dt.strftime('%Y-%m-%d')
        st.dataframe(display_df, use_container_width=True, hide_index=True)

# [탭 2] 일정 및 마일스톤 입력
with tab2:
    st.subheader("일정 및 마일스톤 등록")
    with st.form("input_form"):
        c1, c2 = st.columns(2)
        input_start = c1.date_input("시작일(마일스톤일 경우 해당일)", datetime.date.today())
        input_end = c2.date_input("종료일", datetime.date.today() + datetime.timedelta(days=30))
        
        c3, c4 = st.columns(2)
        # 마일스톤으로 등록하면 차트 상단에 화살표로 나타납니다.
        input_dae = c3.selectbox("대분류", ["인허가", "설계/조사", "계약", "토목공사", "건축공사", "송전선로", "MILESTONE"])
        input_gubun = c4.text_input("구분", placeholder="예: 착공, 종합준공, MTR 선발주 등")
        
        c5, c6 = st.columns(2)
        input_status = c5.selectbox("진행상태", ["예정", "진행중", "완료", "지연"])
        input_note = c6.text_input("비고")
        
        submitted = st.form_submit_button("저장하기 💾", use_container_width=True)
        
        if submitted:
            # 빈 구분명 보정
            save_gubun = input_gubun.strip() if input_gubun.strip() != "" else "인허가 보완/진행"
            
            new_row = [
                input_start.strftime('%Y-%m-%d'), 
                input_end.strftime('%Y-%m-%d'), 
                input_dae, 
                save_gubun, 
                input_status, 
                input_note
            ]
            sheet.append_row(new_row)
            st.success("✅ 공정이 성공적으로 저장되었습니다!")
            time.sleep(1)
            st.rerun()
