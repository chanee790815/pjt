import streamlit as st
import pandas as pd
import datetime
import gspread
from google.oauth2.service_account import Credentials
import requests
import time
import plotly.express as px

# 1. 페이지 설정
st.set_page_config(page_title="PM 통합 공정 관리 v1.1.6", page_icon="🏗️", layout="wide")

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
# [SECTION 1] 백엔드 및 동기화 로직 (v1.1.4 가이드 준수 버전)
# ---------------------------------------------------------

@st.cache_resource
def get_client():
    key_dict = dict(st.secrets["gcp_service_account"])
    if "private_key" in key_dict: key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")
    creds = Credentials.from_service_account_info(key_dict, scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
    return gspread.authorize(creds)

def sync_yearly_data_v116(sh, stn_id, stn_name, target_year):
    try:
        db_ws = sh.worksheet('Solar_DB')
        SERVICE_KEY = 'ba10959184b37d5a2f94b2fe97ecb2f96589f7d8724ba17f85fdbc22d47fb7fe'
        start_dt = f"{target_year}0101"
        end_dt = f"{target_year}1231" if int(target_year) < datetime.date.today().year else datetime.date.today().strftime("%Y%m%d")
        url = f'http://apis.data.go.kr/1360000/AsosDalyInfoService/getWthrDataList?serviceKey={SERVICE_KEY}&numOfRows=366&pageNo=1&dataType=JSON&dataCd=ASOS&dateCd=DAY&stnIds={stn_id}&startDt={start_dt}&endDt={end_dt}'
        res = requests.get(url, timeout=15).json()
        items = res.get('response', {}).get('body', {}).get('items', {}).get('item', [])
        new_rows = [[i['tm'], stn_name, round(float(i.get('sumGsr', 0)) / 3.6, 2), i.get('sumGsr', 0)] for i in items]
        if new_rows:
            all_data = db_ws.get_all_values()
            df_filtered = pd.DataFrame(all_data[1:], columns=all_data[0]) if len(all_data) > 1 else pd.DataFrame()
            if not df_filtered.empty:
                df_filtered['날짜'] = pd.to_datetime(df_filtered['날짜'], errors='coerce')
                df_filtered = df_filtered.loc[df_filtered['날짜'].dt.year != int(target_year)].dropna(subset=['날짜'])
            db_ws.clear()
            db_ws.append_row(["날짜", "지점", "발전시간", "일사량합계"])
            if not df_filtered.empty:
                df_filtered['날짜'] = df_filtered['날짜'].dt.strftime('%Y-%m-%d')
                db_ws.append_rows(df_filtered.values.tolist())
            db_ws.append_rows(new_rows)
            return len(new_rows)
    except: return 0

# ---------------------------------------------------------
# [SECTION 2] 페이지 렌더링 함수 (복구 완료)
# ---------------------------------------------------------

def show_dashboard_summary(sh, pjt_list):
    st.title("📊 프로젝트 통합 대시보드")
    st.write(f"현재 운영 중인 **{len(pjt_list)}개** 현장 현황입니다.")
    st.markdown("---")
    try:
        hist_df = pd.DataFrame(sh.worksheet('weekly_history').get_all_records())
        cols = st.columns(2)
        for idx, p_name in enumerate(pjt_list):
            with cols[idx % 2]:
                p_df = pd.DataFrame(sh.worksheet(p_name).get_all_records())
                prog = round(pd.to_numeric(p_df['진행률'], errors='coerce').mean(), 1) if '진행률' in p_df.columns else 0
                note = hist_df[hist_df['프로젝트명'] == p_name].iloc[-1]['주요현황'] if not hist_df.empty and not hist_df[hist_df['프로젝트명'] == p_name].empty else "브리핑 없음"
                st.markdown(f'<div class="pjt-card"><span class="status-badge">진행 중</span><h3 style="margin:10px 0;">🏗️ {p_name}</h3><p style="font-size:14px;"><b>최신 현황:</b> {note}</p></div>', unsafe_allow_html=True)
                st.progress(prog / 100, text=f"공정 진척률: {prog}%")
    except: st.error("대시보드 로드 실패")

def show_daily_solar(sh):
    st.title("📅 연도별 발전량 분석 리포트")
    with st.expander("📥 데이터 정밀 동기화 (기상청 API)"):
        c1, c2, c3 = st.columns([1, 1, 1])
        stn = c1.selectbox("지점", [127, 108, 131, 159], format_func=lambda x: {127:"충주", 108:"서울", 131:"청주", 159:"부산"}[x])
        year = c2.selectbox("수집 연도", list(range(2026, 2019, -1)))
        if c3.button(f"🚀 {year}년 데이터 수집/정정", use_container_width=True):
            with st.spinner('동기화 중...'):
                count = sync_yearly_data_v116(sh, stn, {127:"충주", 108:"서울", 131:"청주", 159:"부산"}[stn], year)
                if count > 0: st.success(f"{year}년 완료!"); time.sleep(1); st.rerun()

    sel_year = st.selectbox("📊 분석할 연도 선택", list(range(2026, 2019, -1)), index=3) # 기본 2023년
    try:
        df = pd.DataFrame(sh.worksheet('Solar_DB').get_all_records())
        if not df.empty:
            df['날짜'] = pd.to_datetime(df['날짜'], errors='coerce')
            y_df = df.loc[df['날짜'].dt.year == int(sel_year)].copy()
            if not y_df.empty:
                avg_val = round(pd.to_numeric(y_df['발전시간']).mean(), 2)
                st.metric(f"✨ {sel_year}년 일 평균 발전시간", f"{avg_val} h")
                y_df['월'] = y_df['날짜'].dt.month
                m_avg = y_df.groupby('월')['발전시간'].mean().reset_index()
                st.plotly_chart(px.bar(m_avg, x='월', y='발전시간', color_discrete_sequence=['#f1c40f']), use_container_width=True)
    except: st.info("데이터를 동기화해 주세요.")

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
    pjt_list = [ws.title for ws in sh.worksheets() if ws.title not in ['weekly_history', 'Solar_DB', 'KPI', 'Sheet1']]
    if "page" not in st.session_state: st.session_state["page"] = "home"
    
    st.sidebar.title("📁 PMO 센터"); st.sidebar.markdown("---")
    if st.sidebar.button("🏠 1. 전체 대시보드", use_container_width=True): st.session_state["page"] = "home"; st.rerun()
    if st.sidebar.button("📅 일 발전량 조회", use_container_width=True): st.session_state["page"] = "solar_day"; st.rerun()
    if st.sidebar.button("📉 3. 경영지표 (KPI)", use_container_width=True): st.session_state["page"] = "kpi"; st.rerun()
    
    st.sidebar.markdown("---"); st.sidebar.markdown("### 🏗️ 4. 프로젝트 목록")
    pjt_choice = st.sidebar.selectbox("현장 선택 (팝업)", ["선택하세요"] + pjt_list)
    if pjt_choice != "선택하세요":
        st.session_state["page"], st.session_state["current_pjt"] = "detail", pjt_choice
    
    if st.sidebar.button("🔓 로그아웃", use_container_width=True):
        for k in list(st.session_state.keys()): del st.session_state[k]
        st.rerun()

    pg = st.session_state["page"]
    if pg == "home": show_dashboard_summary(sh, pjt_list)
    elif pg == "solar_day": show_daily_solar(sh)
    elif pg == "kpi":
        st.title("📉 경영지표 (KPI)")
        try: st.dataframe(pd.DataFrame(sh.worksheet('KPI').get_all_records()), use_container_width=True)
        except: st.error("KPI 시트가 없습니다.")
    elif pg == "detail":
        st.title(f"🏗️ {st.session_state['current_pjt']} 상세 관리")
