import streamlit as st
import pandas as pd
import datetime
import gspread
from gspread.exceptions import APIError, WorksheetNotFound
from google.oauth2.service_account import Credentials
import requests
import time
import plotly.express as px
import plotly.graph_objects as go
import io

# 1. 페이지 설정
st.set_page_config(page_title="PM 통합 공정 관리 v4.5.0", page_icon="🏗️", layout="wide")

# API KEY 및 기본 설정
SERVICE_KEY = "ba10959184b37d5a2f94b2fe97ecb2f96589f7d8724ba17f85fdbc22d47fb7fe"

# --- [UI] 스타일 ---
st.markdown("""
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    html, body, [class*="css"] { font-family: 'Pretendard', sans-serif; }
    .pjt-card { background-color: #ffffff; padding: 20px; border-radius: 12px; border: 1px solid #eee; margin-bottom: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .footer { position: fixed; left: 0; bottom: 0; width: 100%; background-color: #f1f1f1; color: #555; text-align: center; padding: 5px; font-size: 11px; z-index: 100; }
    .weekly-box { background-color: #f8f9fa; padding: 12px; border-radius: 6px; margin-top: 10px; font-size: 13px; line-height: 1.6; color: #333; border: 1px solid #edf0f2; white-space: pre-wrap; }
    .history-box { background-color: #e3f2fd; padding: 15px; border-radius: 8px; border-left: 5px solid #2196f3; margin-bottom: 20px; }
    .pm-tag { background-color: #f1f3f5; color: #495057; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: 600; margin-left: 10px; }
    .risk-high { border-left: 5px solid #ff4b4b !important; }
    .risk-normal { border-left: 5px solid #1f77b4 !important; }
    </style>
    <div class="footer">시스템 상태: 정상 (v4.5.0) | 일조량 API 연동 및 지역별 분석 기능 복원</div>
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
    except Exception as e:
        st.error(f"구글 클라우드 연결 실패: {e}")
        return None

def get_solar_api_data(target_date, stn_id="129"):
    """기상청 ASOS 일 최저/최고/일조량 데이터 수집"""
    url = "http://apis.data.go.kr/1360000/AsosDalyInfoService/getWthrDataList"
    date_str = target_date.strftime("%Y%m%d")
    params = {
        'serviceKey': SERVICE_KEY,
        'numOfRows': '10', 'pageNo': '1', 'dataType': 'JSON',
        'dataCd': 'ASOS', 'dateKind': 'DAY',
        'startDt': date_str, 'endDt': date_str, 'stnIds': stn_id
    }
    try:
        res = requests.get(url, params=params, timeout=10)
        items = res.json()['response']['body']['items']['item']
        if items:
            item = items[0]
            return {
                "발전시간": float(item.get('sumSsHr', 0)), # 합계 일조시간
                "일사량": float(item.get('sumGsr', 0))     # 합계 일사량
            }
    except: return None
    return None

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

# 1. 통합 대시보드 (기존 소스 동일)
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
                ws = sh.worksheet(p_name)
                df = pd.DataFrame(ws.get_all_records())
                pm_name = ws.acell('J1').value or "미지정"
                
                if not df.empty and '진행률' in df.columns:
                    avg_act = round(pd.to_numeric(df['진행률'], errors='coerce').fillna(0).mean(), 1)
                    avg_plan = round(df.apply(lambda r: calc_planned_progress(r.get('시작일'), r.get('종료일')), axis=1).mean(), 1)
                else: avg_act, avg_plan = 0.0, 0.0
                
                status_ui, c_style = "🟢 정상", "pjt-card risk-normal"
                if (avg_plan - avg_act) >= 10: status_ui, c_style = "🔴 지연", "pjt-card risk-high"
                elif avg_act >= 100: status_ui = "🔵 완료"
                
                weekly_content = "등록된 주간업무가 없습니다."
                if not hist_df.empty:
                    p_match = hist_df[hist_df['프로젝트명'] == p_name.strip()]
                    if not p_match.empty:
                        latest = p_match.iloc[-1]
                        this_w = str(latest.get('금주업무', latest.get('주요현황', ''))).strip()
                        next_w = str(latest.get('차주업무', '')).strip()
                        summary = []
                        if this_w and this_w != 'nan': summary.append(f"<b>[금주]</b> {this_w[:70]}")
                        if next_w and next_w != 'nan': summary.append(f"<b>[차주]</b> {next_w[:70]}")
                        if summary: weekly_content = "<br>".join(summary)
                
                st.markdown(f'''<div class="{c_style}">
                    <h4>🏗️ {p_name} <span class="pm-tag">PM: {pm_name}</span> <span style="font-size:14px; float:right;">{status_ui}</span></h4>
                    <p style="font-size:13px; color:#666;">계획: {avg_plan}% | 실적: {avg_act}%</p>
                    <div class="weekly-box">{weekly_content}</div>
                    </div>''', unsafe_allow_html=True)
                st.progress(min(1.0, max(0.0, avg_act/100)))
            except: pass

# 2. 프로젝트 상세 관리 (기존 소스 동일)
def view_project_detail(sh, pjt_list):
    st.title("🏗️ 프로젝트 상세 관리")
    selected_pjt = st.selectbox("현장 선택", ["선택"] + pjt_list)
    if selected_pjt != "선택":
        ws = sh.worksheet(selected_pjt)
        df = pd.DataFrame(ws.get_all_records())
        if '진행률' in df.columns: df['진행률'] = pd.to_numeric(df['진행률'], errors='coerce').fillna(0)
        current_pm = ws.acell('J1').value or ""
        
        col_pm1, col_pm2 = st.columns([3, 1])
        with col_pm1: new_pm = st.text_input("프로젝트 담당 PM", value=current_pm)
        with col_pm2: 
            st.write(" ")
            if st.button("PM 정보 저장"): ws.update('J1', [[new_pm]]); st.success("저장 완료")

        tab1, tab2, tab3 = st.tabs(["📊 간트 차트", "📈 S-Curve 분석", "📝 주간 업무 보고"])
        with tab1:
            cdf = df.copy()
            cdf['시작일'] = pd.to_datetime(cdf['시작일'], errors='coerce')
            cdf['종료일'] = pd.to_datetime(cdf['종료일'], errors='coerce')
            cdf = cdf.dropna(subset=['시작일', '종료일'])
            if not cdf.empty:
                y_axis = '구분' if '구분' in cdf.columns else '대분류'
                fig = px.timeline(cdf, x_start="시작일", x_end="종료일", y=y_axis, color="진행률", color_continuous_scale='RdYlGn', range_color=[0, 100])
                fig.update_yaxes(autorange="reversed")
                st.plotly_chart(fig, use_container_width=True)
        # (tab2, tab3 로직 생략 - 기존과 동일)
        
        st.subheader("📝 상세 공정표 편집")
        edited = st.data_editor(df, use_container_width=True, num_rows="dynamic")
        if st.button("💾 공정표 데이터 저장"):
            rows = edited.fillna("").astype(str).values.tolist()
            ws.update([edited.columns.values.tolist()] + rows)
            ws.update('J1', [[new_pm]])
            st.success("저장되었습니다!"); st.rerun()

# 3. 일 발전량 분석 (API 연동 버전)
def view_solar(sh):
    st.title("☀️ 일 발전량 및 일조 분석")
    
    # 지점 매핑 (필요시 추가)
    LOC_CODES = {"서산(당진)": "129", "천안": "232", "청주": "131", "광주": "156"}
    
    with st.sidebar.expander("🌐 데이터 수집 설정", expanded=True):
        sel_loc = st.selectbox("대상 지역", list(LOC_CODES.keys()))
        sel_date = st.date_input("수집일", datetime.date.today() - datetime.timedelta(days=1))
        if st.button("기상청 API 데이터 가져오기"):
            res = get_solar_api_data(sel_date, LOC_CODES[sel_loc])
            if res:
                db_ws = sh.worksheet('Solar_DB')
                db_ws.append_row([sel_date.strftime("%Y-%m-%d"), sel_loc, res['발전시간'], res['일사량']])
                st.success(f"{sel_loc} 데이터 저장 성공!"); time.sleep(1); st.rerun()
            else: st.error("데이터를 가져오지 못했습니다.")

    try:
        db_ws = sh.worksheet('Solar_DB')
        df_db = pd.DataFrame(db_ws.get_all_records())
        if not df_db.empty:
            df_db['날짜'] = pd.to_datetime(df_db['날짜'], errors='coerce')
            
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("📊 지역별 월간 평균 발전시간")
                m_avg = df_db.groupby([df_db['날짜'].dt.month, '지점'])['발전시간'].mean().reset_index()
                fig = px.bar(m_avg, x='날짜', y='발전시간', color='지점', barmode='group', color_discrete_sequence=px.colors.qualitative.Prism)
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                st.subheader("📈 일사량-발전시간 상관관계")
                fig2 = px.scatter(df_db, x='일사량합계', y='발전시간', color='지점', trendline="ols")
                st.plotly_chart(fig2, use_container_width=True)
            
            st.subheader("📋 최근 수집 데이터 (Solar_DB)")
            st.dataframe(df_db.sort_values('날짜', ascending=False), use_container_width=True)
    except Exception as e: st.info(f"Solar_DB 관리: {e}")

# (기타 view_kpi, view_risk_dashboard, view_project_admin 함수는 기존과 동일하게 유지)
# ... [생략] ...

# ---------------------------------------------------------
# [SECTION 3] 메인 컨트롤러
# ---------------------------------------------------------

if check_login():
    client = get_client()
    if client:
        try:
            sh = client.open('pms_db')
            pjt_list = [ws.title for ws in sh.worksheets() if ws.title not in ['weekly_history', 'Solar_DB', 'KPI', 'Sheet1', 'conflict']]
            
            st.sidebar.title("📁 PMO 메뉴")
            menu = st.sidebar.radio("메뉴 선택", ["통합 대시보드", "리스크 현황", "프로젝트 상세", "일 발전량 분석", "경영지표(KPI)", "프로젝트 설정"])
            
            if menu == "통합 대시보드": view_dashboard(sh, pjt_list)
            elif menu == "프로젝트 상세": view_project_detail(sh, pjt_list)
            elif menu == "일 발전량 분석": view_solar(sh)
            # ... 나머지 메뉴 연결 ...
            
            if st.sidebar.button("로그아웃"): st.session_state.logged_in = False; st.rerun()
        except Exception as e: st.error(f"DB 연결 오류: {e}")
