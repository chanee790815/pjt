## [PMS Revision History]
## 버전: Rev. 0.6.1 (UI/UX Optimization)
## 업데이트 요약:
## 1. 📂 시트 필터링: 'weekly_history' 등 관리용 시트를 대시보드 리스트에서 자동 제외
## 2. 🎨 가독성 강화: 프로젝트 현황을 가로형 카드와 진행률 바(Progress Bar)로 시각화
## 3. 🚀 내비게이션: 클릭 이동 기능을 유지하면서 UI 디자인 대폭 개선

import streamlit as st
import pandas as pd
import datetime
import gspread
from google.oauth2.service_account import Credentials
import time
import plotly.express as px

# 1. 페이지 설정
st.set_page_config(page_title="PM 통합 공정 관리 v0.6.1", page_icon="🏗️", layout="wide")

# --- [인증] 멀티 계정 체크 ---
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False
    if st.session_state["password_correct"]:
        return True
    st.title("🏗️ PM 통합 공정 관리 시스템")
    with st.form("login_form"):
        user_id = st.text_input("아이디 (ID)")
        password = st.text_input("비밀번호 (PW)", type="password")
        if st.form_submit_button("로그인"):
            user_db = st.secrets["passwords"]
            if user_id in user_db and password == user_db[user_id]:
                st.session_state["password_correct"] = True
                st.session_state["user_id"] = user_id
                st.rerun()
            else:
                st.error("정보가 일치하지 않습니다.")
    return False

if not check_password():
    st.stop()

# --- 구글 시트 연결 ---
@st.cache_resource
def get_client():
    try:
        key_dict = dict(st.secrets["gcp_service_account"])
        if "private_key" in key_dict:
            key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")
        creds = Credentials.from_service_account_info(key_dict, scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"🚨 연결 오류: {e}"); return None

client = get_client()
if client:
    sh = client.open('pms_db')
    
    # [수정] 관리용 시트(history 등)는 리스트에서 제외
    all_ws = [ws for ws in sh.worksheets() if not ws.title.startswith('weekly_history')]
    pjt_names = [s.title for s in all_ws]
    
    try:
        hist_ws = sh.worksheet('weekly_history')
    except:
        hist_ws = sh.add_worksheet(title='weekly_history', rows="1000", cols="5")
        hist_ws.append_row(["날짜", "프로젝트명", "주요현황", "작성자"])

    if "selected_menu" not in st.session_state:
        st.session_state["selected_menu"] = "🏠 전체 대시보드"

    st.sidebar.title("📁 PMO 프로젝트 센터")
    st.sidebar.write(f"👤 접속자: **{st.session_state['user_id']}**")
    
    menu = ["🏠 전체 대시보드"] + pjt_names
    selected = st.sidebar.selectbox("🎯 메뉴 선택", menu, index=menu.index(st.session_state["selected_menu"]), key="nav_menu")
    st.session_state["selected_menu"] = selected

    # ---------------------------------------------------------
    # CASE 1: 전체 대시보드 (가독성 강화 디자인)
    # ---------------------------------------------------------
    if st.session_state["selected_menu"] == "🏠 전체 대시보드":
        st.title("📊 프로젝트 통합 대시보드")
        
        hist_data = pd.DataFrame(hist_ws.get_all_records())
        summary = []
        for ws in all_ws:
            try:
                p_df = pd.DataFrame(ws.get_all_records())
                prog = round(pd.to_numeric(p_df['진행률'], errors='coerce').mean(), 1) if not p_df.empty else 0
                
                note = "최신 브리핑 데이터가 없습니다."
                if not hist_data.empty:
                    latest_p_hist = hist_data[hist_data['프로젝트명'] == ws.title].tail(1)
                    if not latest_p_hist.empty:
                        note = latest_p_hist.iloc[0]['주요현황']
                
                summary.append({"프로젝트명": ws.title, "진척률": prog, "최신현황": note})
            except: continue
        
        if summary:
            st.divider()
            for idx, row in enumerate(summary):
                # 가독성을 위한 카드 스타일 레이아웃
                with st.container():
                    col1, col2, col3 = st.columns([2.5, 2, 5.5])
                    
                    # 1열: 프로젝트명 (강조 버튼)
                    if col1.button(f"📂 {row['프로젝트명']}", key=f"btn_{idx}", use_container_width=True):
                        st.session_state["selected_menu"] = row['프로젝트명']
                        st.rerun()
                    
                    # 2열: 진척률 바 시각화
                    col2.write(f"**진척률: {row['진척률']}%**")
                    col2.progress(row['진척률'] / 100)
                    
                    # 3열: 최신 브리핑 (텍스트 박스)
                    col3.info(f"{row['최신현황']}")
                st.write("") # 간격 조절
            
            st.divider()
            # 전체 진척률 비교 차트
            sum_df = pd.DataFrame(summary)
            st.plotly_chart(px.bar(sum_df, x="프로젝트명", y="진척률", color="진척률", text_auto=True, title="프로젝트별 진척률 비교"), use_container_width=True)
        else:
            st.info("관리 중인 프로젝트가 없습니다.")

    # ---------------------------------------------------------
    # CASE 2: 상세 관리 (기존 로직 유지 및 최적화)
    # ---------------------------------------------------------
    else:
        p_name = st.session_state["selected_menu"]
        target_ws = sh.worksheet(p_name)
        st.title(f"🏗️ {p_name} 상세 관리")
        
        t1, t2, t3, t4 = st.tabs(["📊 통합 공정표", "📝 일정등록", "📢 현황업데이트", "📜 과거기록조회"])

        with t1:
            df = pd.DataFrame(target_ws.get_all_records())
            if not df.empty:
                df['시작일'] = pd.to_datetime(df['시작일'], errors='coerce')
                df['종료일'] = pd.to_datetime(df['종료일'], errors='coerce')
                df = df.sort_values(by='시작일', ascending=True)
                
                # 간트 차트 상단 날짜 표시 유지
                chart_df = df[df['대분류']!='MILESTONE'].dropna(subset=['시작일', '종료일'])
                if not chart_df.empty:
                    fig = px.timeline(chart_df, x_start="시작일", x_end="종료일", y="구분", color="진행상태")
                    fig.update_yaxes(autorange="reversed")
                    fig.update_xaxes(side="top", dtick="M1", tickformat="%Y-%m")
                    st.plotly_chart(fig, use_container_width=True)
                st.dataframe(df, use_container_width=True)

        with t3:
            st.subheader("📢 주간 현황 누적 업데이트")
            with st.form("up_form"):
                new_status = st.text_area("이번 주 주요 현황 및 이슈 작성", placeholder="업무 수행중, 주요 이슈사항 없음")
                if st.form_submit_button("기록 저장 및 대시보드 반영"):
                    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                    hist_ws.append_row([now, p_name, new_status, st.session_state['user_id']])
                    target_ws.update_acell("F2", new_status) # 이전 버전 호환용
                    st.success("히스토리에 저장되었습니다."); time.sleep(1); st.rerun()

        with t4:
            st.subheader("📜 과거 리포트 기록")
            h_data = pd.DataFrame(hist_ws.get_all_records())
            if not h_data.empty:
                p_h = h_data[h_data['프로젝트명'] == p_name].iloc[::-1] # 최신순 정렬
                for _, hr in p_h.iterrows():
                    with st.expander(f"📅 {hr['날짜']} | 작성자: {hr['작성자']}"):
                        st.write(hr['주요현황'])
