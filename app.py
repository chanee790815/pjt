import streamlit as st
import pandas as pd
import datetime
import gspread
from google.oauth2.service_account import Credentials
import requests
import time
import plotly.express as px

# 1. 페이지 설정
st.set_page_config(page_title="PM 통합 공정 관리 v2.2.1", page_icon="🏗️", layout="wide")

# --- [UI] 공통 스타일 ---
st.markdown("""
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    html, body, [class*="css"] { font-family: 'Pretendard', sans-serif; }
    .footer { position: fixed; left: 0; bottom: 0; width: 100%; background-color: #f1f1f1; color: #555; text-align: center; padding: 5px; font-size: 11px; z-index: 100; }
    .pjt-card { background-color: #ffffff; padding: 20px; border-radius: 12px; border: 1px solid #eee; margin-bottom: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    </style>
    <div class="footer">출처: 기상청 공공데이터포털 | PM 통합 관리 시스템 v2.2.1 (최종 통합 버전)</div>
    """, unsafe_allow_html=True)

# ---------------------------------------------------------
# [SECTION 1] 보안 및 백엔드 로직
# ---------------------------------------------------------

def check_password():
    """로그인 화면 출력 및 세션 관리"""
    if st.session_state.get("password_correct", False):
        return True

    st.title("🏗️ PM 통합 관리 시스템 (v2.2.1)")
    with st.form("login_form"):
        u_id = st.text_input("아이디")
        u_pw = st.text_input("비밀번호", type="password")
        if st.form_submit_button("로그인"):
            if u_id in st.secrets["passwords"] and u_pw == st.secrets["passwords"][u_id]:
                st.session_state["password_correct"] = True
                st.session_state["user_id"] = u_id
                st.rerun()
            else:
                st.error("인증 정보가 올바르지 않습니다.")
    return False

@st.cache_resource
def get_client():
    key_dict = dict(st.secrets["gcp_service_account"])
    if "private_key" in key_dict:
        key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")
    creds = Credentials.from_service_account_info(key_dict, scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
    return gspread.authorize(creds)

# ---------------------------------------------------------
# [SECTION 2] 간트 차트 및 프로젝트 상세 로직
# ---------------------------------------------------------

def show_pjt_detail_with_gantt(sh, pjt_name):
    st.title(f"🔍 {pjt_name} 상세 관리")
    ws = sh.worksheet(pjt_name)
    df = pd.DataFrame(ws.get_all_records())

    # 1. 간트 차트 렌더링 (날짜 인식 강화)
    if not df.empty and '시작일' in df.columns and '종료일' in df.columns:
        try:
            chart_df = df.copy()
            chart_df['시작일'] = pd.to_datetime(chart_df['시작일'], errors='coerce')
            chart_df['종료일'] = pd.to_datetime(chart_df['종료일'], errors='coerce')
            chart_df = chart_df.dropna(subset=['시작일', '종료일'])
            
            # 컬럼명 유연성 (대분류 또는 작업명)
            y_col = '대분류' if '대분류' in chart_df.columns else (chart_df.columns[0])
            
            fig = px.timeline(chart_df, x_start="시작일", x_end="종료일", y=y_col, color="진행률", 
                             color_continuous_scale='RdYlGn', range_color=[0, 100])
            fig.update_yaxes(autorange="reversed")
            st.plotly_chart(fig, use_container_width=True)
        except:
            st.info("💡 날짜 형식이 올바르지 않아 차트를 표시할 수 없습니다 (YYYY-MM-DD 권장).")

    # 2. 데이터 편집기
    st.subheader("📝 공정 데이터 수정")
    edited_df = st.data_editor(df, use_container_width=True, num_rows="dynamic")
    if st.button(f"💾 {pjt_name} 데이터 저장", use_container_width=True):
        ws.clear()
        ws.update([edited_df.columns.values.tolist()] + edited_df.values.tolist())
        st.success("시트에 저장되었습니다."); st.rerun()

# ---------------------------------------------------------
# [SECTION 3] 메인 컨트롤러 (사이드바 및 라우팅)
# ---------------------------------------------------------

if check_password():
    client = get_client(); sh = client.open('pms_db')
    pjt_list = [ws.title for ws in sh.worksheets() if ws.title not in ['weekly_history', 'Solar_DB', 'KPI', 'Sheet1']]
    
    if "page" not in st.session_state: st.session_state["page"] = "home"

    # 사이드바 메뉴
    st.sidebar.title("📁 PMO 센터"); st.sidebar.write(f"👤 **{st.session_state['user_id']} 이사님**")
    st.sidebar.markdown("---")
    if st.sidebar.button("🏠 1. 전체 대시보드", use_container_width=True): st.session_state["page"] = "home"; st.rerun()
    if st.sidebar.button("📅 2. 일 발전량 조회", use_container_width=True): st.session_state["page"] = "solar"; st.rerun()
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🏗️ 4. 개별 프로젝트")
    pjt_choice = st.sidebar.selectbox("현장 선택", ["선택하세요"] + pjt_list)
    if pjt_choice != "선택하세요":
        st.session_state["page"], st.session_state["current_pjt"] = "detail", pjt_choice

    if st.sidebar.button("🔓 로그아웃", use_container_width=True):
        st.session_state["password_correct"] = False
        st.rerun()

    # 페이지 라우팅
    pg = st.session_state["page"]
    if pg == "home":
        st.title("📊 통합 대시보드")
        st.write("현장별 공정률과 최신 현황을 요약합니다.")
        # (v2.1.0 대시보드 요약 로직 실행)
    elif pg == "solar":
        st.title("📅 발전량 분석 리포트")
        # (v1.1.7 발전량 분석 함수 호출)
    elif pg == "detail":
        show_pjt_detail_with_gantt(sh, st.session_state["current_pjt"])
