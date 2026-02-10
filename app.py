import streamlit as st
import pandas as pd
import datetime
import gspread
from google.oauth2.service_account import Credentials
import requests
import plotly.express as px

# 1. 페이지 설정
st.set_page_config(page_title="PM 통합 공정 관리 v2.2.0", page_icon="🏗️", layout="wide")

# --- [UI] 공통 스타일 ---
st.markdown("""
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    html, body, [class*="css"] { font-family: 'Pretendard', sans-serif; }
    .footer { position: fixed; left: 0; bottom: 0; width: 100%; background-color: #f1f1f1; color: #555; text-align: center; padding: 5px; font-size: 11px; z-index: 100; }
    </style>
    <div class="footer">출처: 기상청 공공데이터포털 | PM 통합 관리 시스템 v2.2.0 (Gantt 차트 복구 버전)</div>
    """, unsafe_allow_html=True)

# ---------------------------------------------------------
# [SECTION 1] 백엔드 및 차트 엔진
# ---------------------------------------------------------

@st.cache_resource
def get_client():
    key_dict = dict(st.secrets["gcp_service_account"])
    if "private_key" in key_dict: key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")
    creds = Credentials.from_service_account_info(key_dict, scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
    return gspread.authorize(creds)

def draw_gantt_chart(df):
    """표 데이터를 기반으로 Gantt 차트를 생성합니다."""
    try:
        # 컬럼명 유연성 확보 (대분류, 구분, 작업명 등 대응)
        task_col = '구분' if '구분' in df.columns else (df.columns[0] if not df.empty else None)
        
        if task_col and '시작일' in df.columns and '종료일' in df.columns:
            chart_df = df.copy()
            # 날짜 형식 강제 변환
            chart_df['시작일'] = pd.to_datetime(chart_df['시작일'], errors='coerce')
            chart_df['종료일'] = pd.to_datetime(chart_df['종료일'], errors='coerce')
            chart_df = chart_df.dropna(subset=['시작일', '종료일']) # 유효하지 않은 날짜 제거
            
            if not chart_df.empty:
                # 진행률 수치화
                chart_df['진행률'] = pd.to_numeric(chart_df['진행률'], errors='coerce').fillna(0)
                
                fig = px.timeline(
                    chart_df, 
                    x_start="시작일", 
                    x_end="종료일", 
                    y=task_col, 
                    color="진행률",
                    color_continuous_scale='RdYlGn', # 빨강(0) -> 초록(100)
                    range_color=[0, 100],
                    title="프로젝트 공정 Gantt 차트"
                )
                fig.update_yaxes(autorange="reversed") # 상단부터 시작
                fig.update_layout(height=400, margin=dict(t=30, b=10, l=10, r=10))
                st.plotly_chart(fig, use_container_width=True)
                return True
        return False
    except: return False

# ---------------------------------------------------------
# [SECTION 2] 개별 현장 관리 페이지 (차트 복구 로직 포함)
# ---------------------------------------------------------

def show_pjt_detail(sh, pjt_name):
    st.title(f"🔍 {pjt_name} 상세 관리 및 공정 차트")
    
    try:
        ws = sh.worksheet(pjt_name)
        data = ws.get_all_records()
        df = pd.DataFrame(data)
        
        if df.empty:
            st.warning("데이터가 없습니다. 아래 표에 내용을 입력해 주세요.")
            # 빈 데이터프레임 생성
            df = pd.DataFrame(columns=["시작일", "종료일", "대분류", "구분", "진행상태", "비고", "진행률", "담당자"])
        
        # 1. 차트 영역
        chart_success = draw_gantt_chart(df)
        if not chart_success:
            st.info("💡 시작일, 종료일, 구분 컬럼에 올바른 데이터를 입력하면 차트가 생성됩니다.")

        st.markdown("---")
        
        # 2. 편집 영역
        st.subheader("📝 상세 공정표 편집")
        edited_df = st.data_editor(df, use_container_width=True, num_rows="dynamic")
        
        if st.button(f"💾 {pjt_name} 변경사항 저장", use_container_width=True):
            ws.clear()
            # 데이터 저장 전 정렬 및 정리
            save_data = [edited_df.columns.values.tolist()] + edited_df.values.tolist()
            ws.update(save_data)
            st.success("시트에 성공적으로 저장되었습니다!"); st.rerun()
            
    except Exception as e:
        st.error(f"데이터 로드 중 오류 발생: {e}")

# ---------------------------------------------------------
# [SECTION 3] 메인 라우팅 및 사이드바 (v2.1.0 기반 통합)
# ---------------------------------------------------------

# (로그인 체크 및 사이드바 구성 로직 v2.1.0과 동일)
# ... [이전 버전의 sidebar 및 routing 로직 포함] ...
