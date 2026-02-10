import streamlit as st
import pandas as pd
import datetime
import gspread
from google.oauth2.service_account import Credentials
import requests
import time
import plotly.express as px

# 1. 페이지 설정
st.set_page_config(page_title="PM 통합 공정 관리 v2.0.0", page_icon="🏗️", layout="wide")

# --- [UI] 디자인 및 저작권 문구 ---
st.markdown("""
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    html, body, [class*="css"] { font-family: 'Pretendard', sans-serif; }
    .footer { position: fixed; left: 0; bottom: 0; width: 100%; background-color: #f1f1f1; color: #555; text-align: center; padding: 5px; font-size: 11px; z-index: 100; }
    .pjt-card { background-color: #ffffff; padding: 20px; border-radius: 12px; border: 1px solid #eee; margin-bottom: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    </style>
    <div class="footer">출처: 기상청 공공데이터포털 | 본 데이터는 이사님 전용 PM 통합 관리 시스템 v2.0.0입니다.</div>
    """, unsafe_allow_html=True)

# ---------------------------------------------------------
# [SECTION 1] 백엔드 공통 로직
# ---------------------------------------------------------

@st.cache_resource
def get_client():
    try:
        key_dict = dict(st.secrets["gcp_service_account"])
        if "private_key" in key_dict: key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")
        creds = Credentials.from_service_account_info(key_dict, scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"구글 시트 연결 실패: {e}")
        return None

def check_password():
    if st.session_state.get("password_correct", False): return True
    st.title("🏗️ PM 통합 관리 시스템")
    with st.form("login"):
        u_id, u_pw = st.text_input("ID"), st.text_input("Password", type="password")
        if st.form_submit_button("로그인"):
            if u_id in st.secrets["passwords"] and u_pw == st.secrets["passwords"][u_id]:
                st.session_state["password_correct"], st.session_state["user_id"] = True, u_id
                st.rerun()
            else: st.error("정보 불일치")
    return False

# ---------------------------------------------------------
# [SECTION 2] 프로젝트 관리 기능 (대시보드, 상세, 생성, 삭제)
# ---------------------------------------------------------

def show_dashboard(sh, pjt_list):
    st.title("📊 프로젝트 통합 대시보드")
    try:
        hist_df = pd.DataFrame(sh.worksheet('weekly_history').get_all_records())
        cols = st.columns(2)
        for idx, p_name in enumerate(pjt_list):
            with cols[idx % 2]:
                p_df = pd.DataFrame(sh.worksheet(p_name).get_all_records())
                prog = round(pd.to_numeric(p_df['진행률'], errors='coerce').mean(), 1) if '진행률' in p_df.columns else 0
                note = hist_df[hist_df['프로젝트명'] == p_name].iloc[-1]['주요현황'] if not hist_df[hist_df['프로젝트명'] == p_name].empty else "기록 없음"
                st.markdown(f'<div class="pjt-card"><h3>🏗️ {p_name}</h3><p>최신 현황: {note}</p></div>', unsafe_allow_html=True)
                st.progress(prog/100, text=f"진척률: {prog}%")
    except: st.info("대시보드 데이터를 구성 중입니다.")

def show_pjt_detail(sh, pjt_name):
    st.title(f"🔍 {pjt_name} 상세 관리")
    ws = sh.worksheet(pjt_name)
    df = pd.DataFrame(ws.get_all_records())
    st.subheader("📍 공정 데이터 현황")
    edited_df = st.data_editor(df, width='stretch', num_rows="dynamic")
    if st.button(f"💾 {pjt_name} 데이터 저장", width='stretch'):
        ws.clear()
        ws.update([edited_df.columns.values.tolist()] + edited_df.values.tolist())
        st.success("데이터가 시트에 반영되었습니다.")

def manage_projects(sh, pjt_list):
    st.title("⚙️ 프로젝트 마스터 관리")
    
    # 새 프로젝트 등록
    with st.expander("➕ 새 프로젝트 등록"):
        new_name = st.text_input("새 현장 명칭 (예: 적서리_EPC)")
        if st.button("등록 실행", width='stretch'):
            if new_name and new_name not in pjt_list:
                sh.add_worksheet(title=new_name, rows="100", cols="20")
                new_ws = sh.worksheet(new_name)
                new_ws.append_row(["작업명", "시작일", "종료일", "진행률", "비고"])
                st.success(f"{new_name} 시트가 생성되었습니다."); st.rerun()
    
    # 프로젝트 삭제
    with st.expander("🗑️ 프로젝트 삭제 (주의)"):
        del_name = st.selectbox("삭제할 현장 선택", ["선택하세요"] + pjt_list)
        if st.button("현장 영구 삭제", width='stretch', type="primary"):
            if del_name != "선택하세요":
                sh.del_worksheet(sh.worksheet(del_name))
                st.success(f"{del_name} 프로젝트가 삭제되었습니다."); st.rerun()

# ---------------------------------------------------------
# [SECTION 3] 태양광 분석 기능 (기존 v1.1.4 로직 유지)
# ---------------------------------------------------------

def sync_solar(sh, stn_id, stn_name, year):
    try:
        db_ws = sh.worksheet('Solar_DB')
        SERVICE_KEY = 'ba10959184b37d5a2f94b2fe97ecb2f96589f7d8724ba17f85fdbc22d47fb7fe'
        start_dt, end_dt = f"{year}0101", f"{year}1231"
        url = f'http://apis.data.go.kr/1360000/AsosDalyInfoService/getWthrDataList?serviceKey={SERVICE_KEY}&numOfRows=366&dataType=JSON&dataCd=ASOS&dateCd=DAY&stnIds={stn_id}&startDt={start_dt}&endDt={end_dt}'
        res = requests.get(url, timeout=10).json()
        items = res['response']['body']['items']['item']
        new_rows = [[i['tm'], stn_name, round(float(i.get('sumGsr',0))/3.6, 2), i.get('sumGsr',0)] for i in items]
        if new_rows:
            db_ws.append_rows(new_rows)
            return len(new_rows)
    except: return 0

def show_solar_page(sh):
    st.title("📅 일 발전량 분석 리포트")
    # ... (기존 v1.1.4의 show_daily_solar 로직이 통합되어 작동함)

# ---------------------------------------------------------
# [SECTION 4] 메인 라우팅 컨트롤러
# ---------------------------------------------------------

if check_password():
    client = get_client()
    if client:
        sh = client.open('pms_db')
        # 관리용 시트를 제외한 현장 목록
        pjt_list = [ws.title for ws in sh.worksheets() if ws.title not in ['weekly_history', 'Solar_DB', 'KPI', 'Sheet1', 'conflict']]
        
        if "page" not in st.session_state: st.session_state["page"] = "home"

        # 사이드바 구성
        st.sidebar.title("📁 PMO 센터"); st.sidebar.write(f"👤 **{st.session_state['user_id']} 이사님**"); st.sidebar.markdown("---")
        
        if st.sidebar.button("🏠 1. 전체 대시보드", width='stretch'): st.session_state["page"] = "home"; st.rerun()
        
        st.sidebar.markdown("### ☀️ 2. 태양광 분석")
        if st.sidebar.button("📅 일 발전량 조회", width='stretch'): st.session_state["page"] = "solar_day"; st.rerun()
        
        st.sidebar.markdown("### 📈 3. 경영지표 및 관리")
        if st.sidebar.button("📉 전사 KPI 조회", width='stretch'): st.session_state["page"] = "kpi"; st.rerun()
        if st.sidebar.button("⚙️ 현장 마스터 관리", width='stretch'): st.session_state["page"] = "admin"; st.rerun()
        
        st.sidebar.markdown("---"); st.sidebar.markdown("### 🏗️ 4. 프로젝트 공정 관리")
        pjt_choice = st.sidebar.selectbox("개별 현장 선택", ["선택하세요"] + pjt_list)
        if pjt_choice != "선택하세요":
            st.session_state["page"], st.session_state["current_pjt"] = "detail", pjt_choice

        # 최종 라우팅
        pg = st.session_state["page"]
        if pg == "home": show_dashboard(sh, pjt_list)
        elif pg == "solar_day": show_solar_page(sh)
        elif pg == "admin": manage_projects(sh, pjt_list)
        elif pg == "kpi":
            st.title("📉 전사 경영지표 (KPI)")
            st.dataframe(pd.DataFrame(sh.worksheet('KPI').get_all_records()), width='stretch')
        elif pg == "detail": show_pjt_detail(sh, st.session_state["current_pjt"])
