import streamlit as st
import pandas as pd
import datetime
import gspread
from google.oauth2.service_account import Credentials
import requests
import plotly.express as px

# 1. 페이지 설정
st.set_page_config(page_title="PM 통합 공정 관리 v1.1.5", page_icon="🏗️", layout="wide")

# --- [UI] 디자인 및 저작권 문구 ---
st.markdown("""
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    html, body, [class*="css"] { font-family: 'Pretendard', sans-serif; }
    .footer { position: fixed; left: 0; bottom: 0; width: 100%; background-color: #f1f1f1; color: #555; text-align: center; padding: 5px; font-size: 11px; z-index: 100; }
    .pjt-card { background-color: #ffffff; padding: 20px; border-radius: 12px; border: 1px solid #eee; margin-bottom: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .status-badge { background-color: #e3f2fd; color: #1976d2; padding: 4px 10px; border-radius: 20px; font-size: 12px; font-weight: bold; }
    </style>
    <div class="footer">출처: 기상청 공공데이터포털 (ASOS 종관기상관측) | 본 데이터는 기상청에서 제공하는 공공데이터를 활용하였습니다.</div>
    """, unsafe_allow_html=True)

# ---------------------------------------------------------
# [SECTION 1] 백엔드 로직
# ---------------------------------------------------------

@st.cache_resource
def get_client():
    key_dict = dict(st.secrets["gcp_service_account"])
    if "private_key" in key_dict: key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")
    creds = Credentials.from_service_account_info(key_dict, scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
    return gspread.authorize(creds)

def show_dashboard_summary(sh, pjt_list):
    """모든 프로젝트의 요약 정보를 카드 형태로 렌더링"""
    st.title("📊 프로젝트 통합 대시보드")
    st.write(f"현재 운영 중인 **{len(pjt_list)}개** 현장 현황입니다.")
    st.markdown("---")
    
    try:
        # 히스토리 시트 미리 로드
        hist_ws = sh.worksheet('weekly_history')
        hist_df = pd.DataFrame(hist_ws.get_all_records())
        
        # 2개씩 한 줄에 배치
        cols = st.columns(2)
        for idx, p_name in enumerate(pjt_list):
            with cols[idx % 2]:
                # 프로젝트 개별 데이터 로드
                p_df = pd.DataFrame(sh.worksheet(p_name).get_all_records())
                
                # 진행률 계산 (평균)
                prog = 0
                if '진행률' in p_df.columns:
                    prog = round(pd.to_numeric(p_df['진행률'], errors='coerce').mean(), 1)
                
                # 최신 브리핑 추출
                note = "최신 브리핑 기록이 없습니다."
                if not hist_df.empty:
                    p_hist = hist_df[hist_df['프로젝트명'] == p_name]
                    if not p_hist.empty:
                        note = p_hist.iloc[-1]['주요현황']
                
                # 카드형 UI 출력
                st.markdown(f"""
                <div class="pjt-card">
                    <span class="status-badge">진행 중</span>
                    <h3 style="margin: 10px 0;">🏗️ {p_name}</h3>
                    <p style="color: #666; font-size: 14px;"><b>최신 현황:</b> {note}</p>
                </div>
                """, unsafe_allow_html=True)
                st.progress(prog / 100, text=f"공정 진척률: {prog}%")
                st.write("") # 간격 조절
    except Exception as e:
        st.error(f"대시보드 구성 중 오류 발생: {e}")

# (중략: 일 발전량 조회 show_daily_solar 함수 등은 기존 v1.1.4 동일 유지)

# ---------------------------------------------------------
# [SECTION 3] 메인 컨트롤러
# ---------------------------------------------------------

def check_password():
    if "password_correct" not in st.session_state: st.session_state["password_correct"] = False
    if st.session_state["password_correct"]: return True
    st.title("🏗️ PM 통합 관리 시스템") 
    with st.form("login_form"):
        u_id, u_pw = st.text_input("아이디"), st.text_input("비밀번호", type="password")
        if st.form_submit_button("로그인"):
            if u_id in st.secrets["passwords"] and u_pw == st.secrets["passwords"][u_id]:
                st.session_state["password_correct"], st.session_state["user_id"] = True, u_id
                st.rerun()
            else: st.error("정보 불일치")
    return False

if check_password():
    client = get_client(); sh = client.open('pms_db')
    # 관리용 시트를 제외한 프로젝트 목록 추출
    pjt_list = [ws.title for ws in sh.worksheets() if ws.title not in ['weekly_history', 'Solar_DB', 'KPI', 'Sheet1', 'conflict']]
    
    if "page" not in st.session_state: st.session_state["page"] = "home"
    
    st.sidebar.title("📁 PMO 센터"); st.sidebar.write(f"👤 **{st.session_state['user_id']} 이사님**"); st.sidebar.markdown("---")
    if st.sidebar.button("🏠 1. 전체 대시보드", width='stretch'): st.session_state["page"] = "home"; st.rerun()
    if st.sidebar.button("📅 일 발전량 조회", width='stretch'): st.session_state["page"] = "solar_day"; st.rerun()
    
    # 프로젝트 상세 관리 (사이드바 선택박스 유지)
    st.sidebar.markdown("---"); st.sidebar.markdown("### 🏗️ 4. 프로젝트 목록")
    pjt_choice = st.sidebar.selectbox("현장 선택 (팝업)", ["선택하세요"] + pjt_list)
    if pjt_choice != "선택하세요":
        st.session_state["page"], st.session_state["current_pjt"] = "detail", pjt_choice
    
    if st.sidebar.button("🔓 로그아웃", width='stretch'):
        for k in list(st.session_state.keys()): del st.session_state[k]
        st.rerun()

    # 페이지 라우팅
    pg = st.session_state["page"]
    if pg == "home":
        show_dashboard_summary(sh, pjt_list)
    elif pg == "solar_day":
        # show_daily_solar(sh) 호출 로직 (v1.1.4 코드 참조)
        st.write("발전량 조회 화면 로드 중...") 
    elif pg == "detail":
        st.title(f"🏗️ {st.session_state['current_pjt']} 상세 관리")
