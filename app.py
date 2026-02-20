import streamlit as st
import pandas as pd
import datetime
import gspread
from google.oauth2.service_account import Credentials
import requests
import time
import plotly.express as px
import plotly.graph_objects as go
import io

# 1. 페이지 설정
st.set_page_config(page_title="PM 통합 공정 관리 v4.1.6", page_icon="🏗️", layout="wide")

# --- [UI] 스타일 ---
st.markdown("""
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    html, body, [class*="css"] { font-family: 'Pretendard', sans-serif; }
    .pjt-card { background-color: #ffffff; padding: 20px; border-radius: 12px; border: 1px solid #eee; margin-bottom: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .footer { position: fixed; left: 0; bottom: 0; width: 100%; background-color: #f1f1f1; color: #555; text-align: center; padding: 5px; font-size: 11px; z-index: 100; }
    .risk-high { border-left: 5px solid #ff4b4b !important; }
    .risk-normal { border-left: 5px solid #1f77b4 !important; }
    .weekly-box { background-color: #f8f9fa; padding: 12px; border-radius: 6px; margin-top: 10px; font-size: 13px; line-height: 1.6; color: #333; border: 1px solid #edf0f2; white-space: pre-wrap; }
    .status-header { background: #ffffff; padding: 15px; border-radius: 8px; border: 1px solid #e9ecef; border-left: 5px solid #007bff; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
    </style>
    <div class="footer">시스템 상태: 정상 (v4.1.6) | 통합 엑셀 마스터 팩 활성화</div>
    """, unsafe_allow_html=True)

# ---------------------------------------------------------
# [SECTION 1] 백엔드 엔진 & 유틸리티
# ---------------------------------------------------------

def check_login():
    if st.session_state.get("logged_in", False): return True
    
    st.title("🏗️ PM 통합 관리 시스템")
    with st.form("login"):
        u_id = st.text_input("ID")
        u_pw = st.text_input("Password", type="password")
        if st.form_submit_button("로그인"):
            if u_id in st.secrets["passwords"] and u_pw == st.secrets["passwords"][u_id]:
                st.session_state["logged_in"] = True
                st.session_state["user_id"] = u_id
                st.rerun()
            else: st.error("정보 불일치")
    return False

@st.cache_resource
def get_client():
    try:
        key_dict = dict(st.secrets["gcp_service_account"])
        if "private_key" in key_dict: key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")
        creds = Credentials.from_service_account_info(key_dict, scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
        return gspread.authorize(creds)
    except: return None

def calc_planned_progress(start, end, target_date=None):
    if target_date is None: target_date = datetime.date.today()
    try:
        s = pd.to_datetime(start).date()
        e = pd.to_datetime(end).date()
        if pd.isna(s) or pd.isna(e): return 0.0
        if target_date < s: return 0.0
        if target_date > e: return 100.0
        total_days = (e - s).days
        if total_days <= 0: return 100.0
        passed_days = (target_date - s).days
        return min(100.0, max(0.0, (passed_days / total_days) * 100))
    except: return 0.0

# ---------------------------------------------------------
# [SECTION 2] 뷰(View) 함수
# ---------------------------------------------------------

def view_dashboard(sh, pjt_list):
    st.title("📊 통합 대시보드 (현황 브리핑)")
    try:
        hist_df = pd.DataFrame(sh.worksheet('weekly_history').get_all_records())
        if not hist_df.empty:
            hist_df.columns = [c.strip() for c in hist_df.columns]
            hist_df['프로젝트명'] = hist_df['프로젝트명'].astype(str).str.strip()
    except: hist_df = pd.DataFrame()
        
    cols = st.columns(2)
    for idx, p_name in enumerate(pjt_list):
        with cols[idx % 2]:
            try:
                df = pd.DataFrame(sh.worksheet(p_name).get_all_records())
                avg_act = round(pd.to_numeric(df['진행률'], errors='coerce').mean(), 1) if not df.empty else 0
                avg_plan = round(df.apply(lambda r: calc_planned_progress(r.get('시작일'), r.get('종료일')), axis=1).mean(), 1) if not df.empty else 0
                
                status_ui = "🟢 정상"
                c_style = "pjt-card risk-normal"
                if (avg_plan - avg_act) >= 10:
                    status_ui = "🔴 지연"
                    c_style = "pjt-card risk-high"
                
                weekly_content = "등록된 주간업무가 없습니다."
                if not hist_df.empty:
                    p_match = hist_df[hist_df['프로젝트명'] == p_name.strip()]
                    if not p_match.empty:
                        latest = p_match.iloc[-1]
                        this_w = str(latest.get('금주업무', '')).strip()
                        next_w = str(latest.get('차주업무', '')).strip()
                        summary = []
                        if this_w and this_w != 'nan': summary.append(f"<b>[금주]</b> {this_w[:70]}")
                        if next_w and next_w != 'nan': summary.append(f"<b>[차주]</b> {next_w[:70]}")
                        if summary: weekly_content = "<br>".join(summary)
                
                st.markdown(f'<div class="{c_style}"><h4>🏗️ {p_name} <span style="font-size:14px; float:right;">{status_ui}</span></h4><p style="font-size:13px; color:#666;">계획: {avg_plan}% | 실적: {avg_act}%</p><div class="weekly-box">{weekly_content}</div></div>', unsafe_allow_html=True)
                st.progress(min(1.0, max(0.0, avg_act/100)))
            except: pass

def view_project_detail(sh, pjt_list):
    st.title("🏗️ 프로젝트 상세 관리")
    selected_pjt = st.selectbox("현장 선택", ["선택"] + pjt_list)
    if selected_pjt != "선택":
        ws = sh.worksheet(selected_pjt)
        df = pd.DataFrame(ws.get_all_records())
        
        tab1, tab2, tab3 = st.tabs(["📊 간트 차트", "📈 S-Curve", "📝 주간 업무 보고"])
        with tab3:
            st.subheader("📝 주간 주요 업무 보고 작성")
            try: hws = sh.worksheet('weekly_history')
            except: hws = sh.add_worksheet('weekly_history', 1000, 10); hws.append_row(['날짜', '프로젝트명', '금주업무', '차주업무', '작성자'])
            
            with st.form("w_form"):
                in_this = st.text_area("✔️ 금주 주요 업무", height=150)
                in_next = st.text_area("🔜 차주 주요 업무", height=150)
                if st.form_submit_button("저장"):
                    hws.append_row([datetime.date.today().strftime("%Y-%m-%d"), selected_pjt, in_this, in_next, st.session_state.user_id])
                    st.success("저장완료!"); st.rerun()
        
        st.write("---")
        edited = st.data_editor(df, use_container_width=True, num_rows="dynamic")
        if st.button("💾 공정표 저장"):
            ws.clear(); ws.update([edited.columns.values.tolist()] + edited.fillna("").astype(str).values.tolist())
            st.success("저장되었습니다!")

def view_project_admin(sh, pjt_list):
    st.title("⚙️ 마스터 설정")
    t1, t2 = st.tabs(["🔄 엑셀 동기화", "📥 마스터 다운로드"])
    with t1:
        target = st.selectbox("업데이트 프로젝트", ["선택"] + pjt_list)
        file = st.file_uploader("엑셀 파일(.xlsm)", type=['xlsx', 'xlsm'])
        if target != "선택" and file and st.button("구글 시트 덮어쓰기"):
            df = pd.read_excel(file).fillna("").astype(str)
            ws = sh.worksheet(target); ws.clear(); ws.update([df.columns.values.tolist()] + df.values.tolist())
            st.success("동기화 완료!")
    with t2:
        st.info("💡 모든 현장 데이터와 주간업무 이력을 포함한 통합 파일을 생성합니다.")
        if st.button("📚 통합 마스터 엑셀 일괄 생성", type="primary", use_container_width=True):
            with st.spinner("모든 시트를 병합 중..."):
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    for p in pjt_list:
                        try: pd.DataFrame(sh.worksheet(p).get_all_records()).to_excel(writer, index=False, sheet_name=p[:31])
                        except: pass
                    try: pd.DataFrame(sh.worksheet('weekly_history').get_all_records()).to_excel(writer, index=False, sheet_name='weekly_history')
                    except: pass
                st.download_button("📥 통합 파일 다운로드", output.getvalue(), f"PMO_Master_Report_{datetime.date.today()}.xlsx", use_container_width=True)

# ---------------------------------------------------------
# [SECTION 3] 컨트롤러
# ---------------------------------------------------------

if check_login():
    client = get_client()
    if client:
        sh = client.open('pms_db')
        pjt_list = [ws.title for ws in sh.worksheets() if ws.title not in ['weekly_history', 'Solar_DB', 'KPI', 'Sheet1']]
        menu = st.sidebar.radio("메뉴", ["통합 대시보드", "프로젝트 상세", "프로젝트 설정"])
        if menu == "통합 대시보드": view_dashboard(sh, pjt_list)
        elif menu == "프로젝트 상세": view_project_detail(sh, pjt_list)
        elif menu == "프로젝트 설정": view_project_admin(sh, pjt_list)
        if st.sidebar.button("로그아웃"): st.session_state.logged_in = False; st.rerun()
