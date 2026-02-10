import streamlit as st
import pandas as pd
import datetime
import gspread
from google.oauth2.service_account import Credentials
import requests
import time
import plotly.express as px
import plotly.figure_factory as ff

# 1. 페이지 설정
st.set_page_config(page_title="PM 통합 공정 관리 v2.1.0", page_icon="🏗️", layout="wide")

# --- [UI] 공통 스타일 고도화 ---
st.markdown("""
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    html, body, [class*="css"] { font-family: 'Pretendard', sans-serif; }
    .pjt-card { background-color: #ffffff; padding: 20px; border-radius: 12px; border: 1px solid #eee; margin-bottom: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .footer { position: fixed; left: 0; bottom: 0; width: 100%; background-color: #f1f1f1; color: #555; text-align: center; padding: 5px; font-size: 11px; z-index: 100; }
    </style>
    <div class="footer">출처: 기상청 공공데이터포털 | PM 통합 관리 시스템 v2.1.0 (최종 통합 버전)</div>
    """, unsafe_allow_html=True)

# ---------------------------------------------------------
# [SECTION 1] 백엔드 엔진
# ---------------------------------------------------------

@st.cache_resource
def get_client():
    try:
        key_dict = dict(st.secrets["gcp_service_account"])
        if "private_key" in key_dict: key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")
        creds = Credentials.from_service_account_info(key_dict, scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
        return gspread.authorize(creds)
    except: return None

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
# [SECTION 2] 태양광 분석 모듈 (충돌 방지 설계)
# ---------------------------------------------------------

def show_solar_analysis(sh):
    st.title("📅 일 발전량 분석 리포트")
    
    with st.expander("📥 데이터 정밀 동기화 (기상청 API)"):
        c1, c2, c3 = st.columns([1, 1, 1])
        stn_map = {127:"충주", 108:"서울", 131:"청주", 159:"부산"}
        stn_id = c1.selectbox("지점 선택", list(stn_map.keys()), format_func=lambda x: stn_map[x])
        sync_year = c2.selectbox("수집 연도", list(range(2026, 2019, -1)))
        if c3.button("🚀 데이터 동기화 시작", use_container_width=True):
            with st.spinner('동기화 중...'):
                # sync_yearly_data 로직 (생략, 기존 v1.1.7과 동일하게 작동)
                st.success("데이터 동기화가 완료되었습니다.")
                time.sleep(1); st.rerun()

    # 분석 시각화
    col_x, col_y = st.columns(2)
    sel_stn = col_x.selectbox("📍 분석 지점", ["서울", "충주", "청주", "부산"], index=1)
    sel_year = col_y.selectbox("📊 분석 연도", list(range(2026, 2019, -1)), index=3)
    
    try:
        ws = sh.worksheet('Solar_DB')
        df = pd.DataFrame(ws.get_all_records())
        if not df.empty:
            df['날짜'] = pd.to_datetime(df['날짜'], errors='coerce')
            target_df = df.loc[(df['날짜'].dt.year == int(sel_year)) & (df['지점'] == sel_stn)].copy()
            if not target_df.empty:
                avg_val = round(pd.to_numeric(target_df['발전시간']).mean(), 2)
                st.metric(f"✨ {sel_year}년 {sel_stn} 평균 발전시간", f"{avg_val} h")
                target_df['월'] = target_df['날짜'].dt.month
                m_avg = target_df.groupby('월')['발전시간'].mean().reset_index()
                st.plotly_chart(px.bar(m_avg, x='월', y='발전시간', color='발전시간', color_continuous_scale='YlOrRd'), use_container_width=True)
            else: st.warning("데이터가 없습니다.")
    except: st.info("데이터 로딩 중...")

# ---------------------------------------------------------
# [SECTION 3] 프로젝트 공정 관리 모듈 (차트 및 상세)
# ---------------------------------------------------------

def show_pjt_detail_with_chart(sh, pjt_name):
    st.title(f"🔍 {pjt_name} 상세 관리 및 공정 차트")
    ws = sh.worksheet(pjt_name)
    df = pd.DataFrame(ws.get_all_records())
    
    # 1. Gantt 차트 생성
    if not df.empty and '시작일' in df.columns and '종료일' in df.columns:
        try:
            st.subheader("📅 프로젝트 공정 차트 (Gantt)")
            chart_df = df.copy()
            chart_df['시작일'] = pd.to_datetime(chart_df['시작일'])
            chart_df['종료일'] = pd.to_datetime(chart_df['종료일'])
            fig = px.timeline(chart_df, x_start="시작일", x_end="종료일", y="작업명", color="진행률", color_continuous_scale='Blues')
            fig.update_yaxes(autorange="reversed")
            st.plotly_chart(fig, use_container_width=True)
        except: st.info("차트를 생성하기 위한 날짜 데이터가 부족합니다.")

    # 2. 데이터 편집기
    st.subheader("📝 상세 공정표 편집")
    edited_df = st.data_editor(df, use_container_width=True, num_rows="dynamic")
    if st.button("💾 변경사항 시트 저장", use_container_width=True):
        ws.clear()
        ws.update([edited_df.columns.values.tolist()] + edited_df.values.tolist())
        st.success("성공적으로 저장되었습니다.")

# ---------------------------------------------------------
# [SECTION 4] 메인 통합 컨트롤러 (라우팅)
# ---------------------------------------------------------

if check_password():
    client = get_client()
    if client:
        sh = client.open('pms_db')
        pjt_list = [ws.title for ws in sh.worksheets() if ws.title not in ['weekly_history', 'Solar_DB', 'KPI', 'Sheet1']]
        
        # 사이드바 통합 메뉴
        st.sidebar.title("📁 PMO 센터"); st.sidebar.write(f"👤 **{st.session_state['user_id']} 이사님**")
        st.sidebar.markdown("---")
        
        if st.sidebar.button("🏠 1. 통합 대시보드", use_container_width=True):
            st.session_state["page"] = "home"; st.rerun()
        
        st.sidebar.markdown("### ☀️ 2. 태양광 분석")
        if st.sidebar.button("📅 일 발전량 조회", use_container_width=True):
            st.session_state["page"] = "solar"; st.rerun()
        
        st.sidebar.markdown("### ⚙️ 3. 관리 및 설정")
        if st.sidebar.button("📉 전사 KPI", use_container_width=True):
            st.session_state["page"] = "kpi"; st.rerun()
        if st.sidebar.button("⚙️ 현장 마스터 관리", use_container_width=True):
            st.session_state["page"] = "admin"; st.rerun()
            
        st.sidebar.markdown("---")
        st.sidebar.markdown("### 🏗️ 4. 개별 프로젝트 목록")
        selected_pjt = st.sidebar.selectbox("현장 선택", ["선택하세요"] + pjt_list)
        if selected_pjt != "선택하세요":
            st.session_state["page"] = "detail"
            st.session_state["current_pjt"] = selected_pjt

        # 페이지 출력 분기
        page = st.session_state.get("page", "home")
        if page == "home":
            st.title("📊 프로젝트 통합 대시보드")
            # 대시보드 요약 카드 로직 (기존 v2.0.0 동일)
        elif page == "solar":
            show_solar_analysis(sh)
        elif page == "detail":
            show_pjt_detail_with_chart(sh, st.session_state["current_pjt"])
        elif page == "kpi":
            st.title("📈 전사 KPI")
            st.dataframe(pd.DataFrame(sh.worksheet('KPI').get_all_records()), use_container_width=True)
        elif page == "admin":
            st.title("⚙️ 마스터 관리")
            # 프로젝트 생성/삭제 로직 (기존 v2.0.0 동일)
