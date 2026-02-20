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
st.set_page_config(page_title="PM 통합 공정 관리 v4.5.2", page_icon="🏗️", layout="wide")

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
    </style>
    <div class="footer">시스템 상태: 정상 (v4.5.2) | 지역별 독립 차트 및 연도별 추이 분석 기능</div>
    """, unsafe_allow_html=True)

# ---------------------------------------------------------
# [SECTION 1] 백엔드 엔진 (수정 없음)
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
    url = "http://apis.data.go.kr/1360000/AsosDalyInfoService/getWthrDataList"
    date_str = target_date.strftime("%Y%m%d")
    params = {'serviceKey': SERVICE_KEY, 'numOfRows': '10', 'pageNo': '1', 'dataType': 'JSON', 'dataCd': 'ASOS', 'dateKind': 'DAY', 'startDt': date_str, 'endDt': date_str, 'stnIds': stn_id}
    try:
        res = requests.get(url, params=params, timeout=10)
        items = res.json()['response']['body']['items']['item']
        if items:
            item = items[0]
            return {"발전시간": float(item.get('sumSsHr', 0)), "일사량": float(item.get('sumGsr', 0))}
    except: return None
    return None

# ---------------------------------------------------------
# [SECTION 2] 뷰(View) 함수 - 일 발전량 분석 (대폭 업데이트)
# ---------------------------------------------------------

def view_solar(sh):
    st.title("☀️ 일 발전량 및 일조 분석")
    
    LOC_CODES = {"서산(당진)": "129", "천안": "232", "청주": "131", "광주": "156"}
    
    # 1. 데이터 로드 및 전처리
    try:
        db_ws = sh.worksheet('Solar_DB')
        df_db = pd.DataFrame(db_ws.get_all_records())
        if not df_db.empty:
            df_db['날짜'] = pd.to_datetime(df_db['날짜'], errors='coerce')
            df_db['연도'] = df_db['날짜'].dt.year
            df_db['월'] = df_db['날짜'].dt.month
    except Exception as e:
        st.error(f"데이터베이스 로드 실패: {e}")
        return

    # 2. 사이드바 필터 설정
    with st.sidebar:
        st.subheader("🌐 데이터 수집")
        sel_loc = st.selectbox("대상 지역", list(LOC_CODES.keys()))
        sel_date = st.date_input("수집일", datetime.date.today() - datetime.timedelta(days=1))
        if st.button("API 데이터 가져오기"):
            res = get_solar_api_data(sel_date, LOC_CODES[sel_loc])
            if res:
                db_ws.append_row([sel_date.strftime("%Y-%m-%d"), sel_loc, res['발전시간'], res['일사량']])
                st.success("저장 완료!"); time.sleep(1); st.rerun()
        
        st.divider()
        st.subheader("🔍 분석 필터")
        if not df_db.empty:
            years = sorted(df_db['연도'].unique().tolist(), reverse=True)
            sel_years = st.multiselect("비교 연도", years, default=years[:2])
            sel_locs = st.multiselect("조회 지역", df_db['지점'].unique(), default=df_db['지점'].unique()[:1])
        else:
            sel_years, sel_locs = [], []

    # 3. 메인 분석 영역
    if not df_db.empty and sel_locs:
        f_df = df_db[df_db['연도'].isin(sel_years) & df_db['지점'].isin(sel_locs)]
        
        # --- [업데이트] 지역별 독립 차트 (연도별 추이) ---
        st.subheader("📅 지역별/연도별 발전시간 추이 비교")
        
        for loc in sel_locs:
            loc_df = f_df[f_df['지점'] == loc]
            if not loc_df.empty:
                # 월별 평균 계산
                m_avg = loc_df.groupby(['연도', '월'])['발전시간'].mean().reset_index()
                m_avg['연도'] = m_avg['연도'].astype(str) # 범례를 위해 문자열 변환
                
                fig = px.line(m_avg, x='월', y='발전시간', color='연도', markers=True,
                              title=f"📍 {loc} 지점 월별 발전시간 추이 (연도별 비교)",
                              labels={'발전시간': '평균 발전시간(h)', '월': '월'},
                              line_shape="spline", 
                              color_discrete_sequence=px.colors.qualitative.Bold)
                
                fig.update_layout(xaxis=dict(tickmode='linear', tick0=1, dtick=1), hovermode="x unified")
                st.plotly_chart(fig, use_container_width=True)

        st.divider()
        
        # --- [업데이트] 데이터 요약 및 상관관계 ---
        col_t, col_c = st.columns([1, 1])
        with col_t:
            st.subheader("📊 데이터 요약")
            summary = f_df.groupby(['지점', '연도'])['발전시간'].agg(['mean', 'max']).reset_index()
            summary.columns = ['지점', '연도', '평균(h)', '최대(h)']
            st.dataframe(summary, use_container_width=True, hide_index=True)
            
        with col_c:
            st.subheader("📈 일사량 대비 효율")
            # statsmodels 에러 방지를 위해 trendline 제거하고 산점도로만 표현
            fig2 = px.scatter(f_df, x='일사량합계', y='발전시간', color='지점', 
                              hover_data=['날짜'], opacity=0.7)
            st.plotly_chart(fig2, use_container_width=True)

        st.subheader("📋 전체 로그 내역")
        st.dataframe(df_db.sort_values('날짜', ascending=False).head(50), use_container_width=True)
    else:
        st.info("사이드바에서 조회할 연도와 지역을 선택해 주세요.")

# (기타 view_dashboard, view_project_detail 등은 기존 소스 유지)
def view_dashboard(sh, pjt_list):
    st.title("📊 통합 대시보드")
    # ... (기존과 동일) ...

# ---------------------------------------------------------
# [SECTION 3] 메인 컨트롤러
# ---------------------------------------------------------

if check_login():
    client = get_client()
    if client:
        try:
            sh = client.open('pms_db')
            pjt_list = [ws.title for ws in sh.worksheets() if ws.title not in ['weekly_history', 'Solar_DB', 'KPI', 'Sheet1']]
            
            st.sidebar.title("📁 PMO 메뉴")
            menu = st.sidebar.radio("메뉴 선택", ["통합 대시보드", "프로젝트 상세", "일 발전량 분석"])
            
            if menu == "통합 대시보드": view_dashboard(sh, pjt_list)
            elif menu == "프로젝트 상세": view_project_detail(sh, pjt_list)
            elif menu == "일 발전량 분석": view_solar(sh)
            
            if st.sidebar.button("로그아웃"): st.session_state.logged_in = False; st.rerun()
        except Exception as e: st.error(f"DB 연결 오류: {e}")
