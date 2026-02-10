import streamlit as st
import pandas as pd
import datetime
import gspread
from google.oauth2.service_account import Credentials
import time
import plotly.express as px
import plotly.graph_objects as go
import requests

# 1. 페이지 설정
st.set_page_config(page_title="PM 통합 공정 관리 v0.9.3", page_icon="🏗️", layout="wide")

# --- [UI] 디자인 커스텀 CSS ---
st.markdown("""
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    html, body, [class*="css"] {
        font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, system-ui, Roboto, sans-serif;
    }
    section[data-testid="stSidebar"] { background-color: #f0f2f6; }
    .main .block-container { padding-top: 0.8rem !important; }
    
    .stButton button {
        border-radius: 10px;
        border: 1px solid #e0e0e0;
        transition: all 0.2s;
        background-color: white;
        font-weight: 500;
    }
    
    div.stButton > button[key="kpi_nav_link"], div.stButton > button[key="solar_nav_link"] {
        border: 2px solid #ff4b4b !important;
        color: #ff4b4b !important;
        font-weight: 700 !important;
        margin-top: 5px !important;
    }
    </style>
    """, unsafe_allow_html=True)

# ---------------------------------------------------------
# [SECTION 1] 데이터 및 보안 로직 (Backend)
# ---------------------------------------------------------

def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False
    if st.session_state["password_correct"]:
        return True
    
    st.title("🏗️ PM 통합 관리 시스템") 
    with st.form("login_form"):
        user_id = st.text_input("아이디 (ID)")
        password = st.text_input("비밀번호 (PW)", type="password")
        if st.form_submit_button("로그인"):
            try:
                user_db = st.secrets["passwords"]
                if user_id in user_db and password == user_db[user_id]:
                    st.session_state["password_correct"] = True
                    st.session_state["user_id"] = user_id
                    st.rerun()
                else:
                    st.error("아이디 또는 비밀번호가 일치하지 않습니다.")
            except KeyError:
                st.error("Secrets 설정에 'passwords' 항목이 없습니다.")
    return False

def logout():
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

@st.cache_resource
def get_client():
    try:
        key_dict = dict(st.secrets["gcp_service_account"])
        if "private_key" in key_dict:
            key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")
        creds = Credentials.from_service_account_info(
            key_dict, 
            scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        )
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"🚨 구글 API 인증 오류: {e}"); return None

@st.cache_data(ttl=60)
def get_ws_data(_client_email, pjt_name):
    temp_client = get_client()
    sh = temp_client.open('pms_db')
    return sh.worksheet(pjt_name).get_all_records()

@st.cache_data(ttl=300)
def fetch_dashboard_summary(_client_email):
    try:
        temp_client = get_client()
        sh = temp_client.open('pms_db')
        forbidden = ['weekly_history', 'conflict', 'Sheet1', 'KPI']
        all_ws = [ws for ws in sh.worksheets() if ws.title not in forbidden]
        pjt_names = [ws.title for ws in all_ws]
        
        try:
            hist_data = pd.DataFrame(sh.worksheet('weekly_history').get_all_records())
        except:
            hist_data = pd.DataFrame(columns=["날짜", "프로젝트명", "주요현황", "작성자"])

        try:
            kpi_data = pd.DataFrame(sh.worksheet('KPI').get_all_records())
        except:
            kpi_data = pd.DataFrame()

        summary = []
        for ws in all_ws:
            try:
                data = ws.get_all_records()
                p_df = pd.DataFrame(data)
                prog = 0
                if '진행률' in p_df.columns:
                    prog = round(pd.to_numeric(p_df['진행률'], errors='coerce').mean(), 1)
                
                note = "최신 브리핑이 없습니다."
                if not hist_data.empty:
                    latest = hist_data[hist_data['프로젝트명'] == ws.title].tail(1)
                    if not latest.empty: note = latest.iloc[0]['주요현황']
                summary.append({"프로젝트명": ws.title, "진척률": prog if not pd.isna(prog) else 0, "최신현황": note})
            except:
                summary.append({"프로젝트명": ws.title, "진척률": 0, "최신현황": "데이터 오류"})
            
        return pjt_names, summary, hist_data, kpi_data
    except Exception as e:
        st.error(f"데이터 연동 중 오류 발생: {e}")
        return [], [], pd.DataFrame(), pd.DataFrame()

# ---------------------------------------------------------
# [SECTION 2] 개별 페이지 렌더링 함수 (Frontend Modules)
# ---------------------------------------------------------

def show_solar_analysis():
    """태양광 발전시간 실시간 분석 페이지"""
    st.title("☀️ 태양광 발전 환경 분석 (기상청 API 연동)")
    SERVICE_KEY = 'ba10959184b37d5a2f94b2fe97ecb2f96589f7d8724ba17f85fdbc22d47fb7fe'
    
    col1, col2 = st.columns(2)
    target_date = col1.date_input("조회 날짜", datetime.date.today() - datetime.timedelta(days=1))
    stn_id = col2.selectbox("관측 지점", [127, 108, 131, 159], 
                            format_func=lambda x: {127:"충주 (적서리 인근)", 108:"서울", 131:"청주", 159:"부산"}[x])

    if st.button("데이터 불러오기"):
        with st.spinner('기상청 API 조회 중...'):
            url = 'http://apis.data.go.kr/1360000/AsosHourlyInfoService/getWthrDataList'
            params = {'serviceKey': SERVICE_KEY, 'pageNo': '1', 'numOfRows': '24', 'dataType': 'JSON', 
                      'dataCd': 'ASOS', 'dateCd': 'HR', 'stnIds': str(stn_id), 
                      'startDt': target_date.strftime("%Y%m%d"), 'startHh': '01', 
                      'endDt': target_date.strftime("%Y%m%d"), 'endHh': '23'}
            try:
                res = requests.get(url, params=params)
                data = res.json()['response']['body']['items']['item']
                df = pd.DataFrame(data)
                df['icsr'] = pd.to_numeric(df['icsr'], errors='coerce').fillna(0)
                df['hour'] = pd.to_datetime(df['tm']).dt.hour
                gen_h = round(df['icsr'].sum() / 3.6, 2)
                
                m1, m2 = st.columns(2)
                m1.metric("☀️ 실측 발전시간", f"{gen_h} h")
                m2.metric("누적 일사량", f"{round(df['icsr'].sum(), 2)} MJ/㎡")
                st.plotly_chart(px.area(df, x='hour', y='icsr', title=f"{target_date} 일사량 추이"), use_container_width=True)
            except:
                st.error("API 호출 실패. 키 승인 상태를 확인하세요.")

def show_project_detail(p_name, sh, full_hist_data):
    """복구된 4대 관리 기능 탭 구성"""
    try:
        data_all = get_ws_data(st.secrets["gcp_service_account"]["client_email"], p_name)
    except:
        st.error("데이터 로딩 중 오류가 발생했습니다.")
        return

    cols = ["시작일", "종료일", "대분류", "구분", "진행상태", "비고", "진행률", "담당자"]
    df_raw = pd.DataFrame(data_all) if data_all else pd.DataFrame(columns=cols)
    
    if not df_raw.empty and '시작일' not in df_raw.columns:
        st.warning(f"시트 컬럼명이 맞지 않습니다. [시작일] 열을 확인하세요.")
        return

    st.title(f"🏗️ {p_name} 상세 관리")
    t1, t2, t3, t4 = st.tabs(["📊 통합 공정표", "📝 일정 등록", "📢 현황 보고", "📜 히스토리"])

    with t1:
        if not df_raw.empty:
            df = df_raw.copy()
            df['시작일'] = pd.to_datetime(df['시작일'], errors='coerce')
            df['종료일'] = pd.to_datetime(df['종료일'], errors='coerce')
            df = df.dropna(subset=['시작일', '종료일'])
            fig = px.timeline(df, x_start="시작일", x_end="종료일", y="구분", color="진행상태",
                              color_discrete_map={"완료": "#0068c9", "진행중": "#ffbd45", "예정": "#d3d3d3", "지연": "#ff4b4b"})
            fig.update_yaxes(autorange="reversed")
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(df_raw, use_container_width=True)
        else:
            st.info("데이터가 없습니다. '일정 등록' 탭에서 첫 공정을 등록하세요.")

    with t2:
        st.subheader("📝 신규 공정 일정 등록")
        with st.form("add_pjt"):
            c1, c2 = st.columns(2)
            sd, ed = c1.date_input("시작일"), c2.date_input("종료일")
            cat = st.selectbox("대분류", ["인허가", "설계", "토목", "설치", "시운전"])
            task = st.text_input("공정명(구분)")
            if st.form_submit_button("공정표에 추가"):
                sh.worksheet(p_name).append_row([str(sd), str(ed), cat, task, "예정", "", 0, st.session_state['user_id']])
                st.cache_data.clear(); st.success("등록되었습니다!"); st.rerun()

    with t3:
        st.subheader("📢 이슈 및 현황 보고")
        with st.form("issue_report"):
            note = st.text_area("활동 사항을 입력하세요.")
            if st.form_submit_button("보고 저장"):
                ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                sh.worksheet('weekly_history').append_row([ts, p_name, note, st.session_state['user_id']])
                st.cache_data.clear(); st.success("보고 완료!"); st.rerun()

    with t4:
        st.subheader("📜 과거 기록 조회")
        if not full_hist_data.empty:
            p_hist = full_hist_data[full_hist_data['프로젝트명'] == p_name].iloc[::-1]
            for _, r in p_hist.iterrows():
                with st.expander(f"📅 {r['날짜']} | {r['작성자']}"):
                    st.write(r['주요현황'])

# ---------------------------------------------------------
# [SECTION 3] 메인 컨트롤러
# ---------------------------------------------------------

if check_password():
    client = get_client()
    if client:
        sh = client.open('pms_db')
        pjt_names, summary, hist_df, kpi_df = fetch_dashboard_summary(st.secrets["gcp_service_account"]["client_email"])
        
        if "selected_project" not in st.session_state:
            st.session_state["selected_project"] = "🏠 전체 대시보드"

        st.sidebar.title("📁 PMO 프로젝트 센터")
        st.sidebar.write(f"👤 접속자: **{st.session_state['user_id']} 이사님**")
        
        selected_menu = st.sidebar.selectbox("🎯 메뉴 선택", ["🏠 전체 대시보드", "☀️ 태양광 분석", "📈 경영지표"] + pjt_names)
        if st.sidebar.button("🔓 로그아웃"): logout()

        if selected_menu == "🏠 전체 대시보드":
            st.title("📊 프로젝트 통합 현황")
            for item in summary:
                st.info(f"**{item['프로젝트명']}** (진척률: {item['진척률']}%) \n\n {item['최신현황']}")
        elif selected_menu == "☀️ 태양광 분석":
            show_solar_analysis()
        elif selected_menu == "📈 경영지표":
            st.title("📈 전사 KPI 지표")
            st.dataframe(kpi_df, use_container_width=True)
        else:
            show_project_detail(selected_menu, sh, hist_df)
