## [PMS Revision History]
## 버전: Rev. 0.6.0 (History Tracking)
## 업데이트 요약:
## 1. 📅 주간 현황 히스토리: '현황 업데이트' 시 별도 시트에 날짜별로 누적 저장
## 2. 🔍 과거 데이터 조회: 프로젝트 상세 페이지에서 과거 기록을 최신순으로 리스트업
## 3. 🚀 내비게이션 최적화: 대시보드 클릭 이동 및 세션 동기화 유지

import streamlit as st
import pandas as pd
import datetime
import gspread
from google.oauth2.service_account import Credentials
import time
import plotly.express as px

# 1. 페이지 설정
st.set_page_config(page_title="PM 통합 공정 관리 v0.6.0", page_icon="🏗️", layout="wide")

# --- [보안] 로그인 체크 ---
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
    
    # 히스토리용 시트 확인 및 생성
    try:
        hist_ws = sh.worksheet('weekly_history')
    except:
        hist_ws = sh.add_worksheet(title='weekly_history', rows="1000", cols="5")
        hist_ws.append_row(["날짜", "프로젝트명", "주요현황", "작성자"])

    all_ws = [ws for ws in sh.worksheets() if ws.title != 'weekly_history']
    pjt_names = [s.title for s in all_ws]
    
    # [내비게이션]
    if "selected_menu" not in st.session_state:
        st.session_state["selected_menu"] = "🏠 전체 대시보드"

    st.sidebar.title("📁 PMO 프로젝트 센터")
    st.sidebar.write(f"👤 접속자: **{st.session_state['user_id']}**")
    
    menu = ["🏠 전체 대시보드"] + pjt_names
    selected = st.sidebar.selectbox("🎯 메뉴 선택", menu, index=menu.index(st.session_state["selected_menu"]), key="nav_menu")
    st.session_state["selected_menu"] = selected

    # ---------------------------------------------------------
    # CASE 1: 전체 대시보드 (최신 현황 표시)
    # ---------------------------------------------------------
    if st.session_state["selected_menu"] == "🏠 전체 대시보드":
        st.title("📊 프로젝트 통합 대시보드")
        
        # 히스토리에서 프로젝트별 최신 데이터 가져오기
        hist_data = pd.DataFrame(hist_ws.get_all_records())
        
        summary = []
        for ws in all_ws:
            try:
                p_name = ws.title
                # 공정 데이터로 진척률 계산
                p_df = pd.DataFrame(ws.get_all_records())
                prog = round(pd.to_numeric(p_df['진행률'], errors='coerce').mean(), 1) if not p_df.empty else 0
                
                # 히스토리 시트에서 해당 프로젝트의 가장 최근 비고 찾기
                if not hist_data.empty:
                    latest_p_hist = hist_data[hist_data['프로젝트명'] == p_name].tail(1)
                    latest_note = latest_p_hist.iloc[0]['주요현황'] if not latest_p_hist.empty else "업데이트 없음"
                else:
                    latest_note = "데이터 없음"
                
                summary.append({"프로젝트명": p_name, "진척률": prog, "최신현황": latest_note})
            except: continue
        
        if summary:
            sum_df = pd.DataFrame(summary)
            for idx, row in sum_df.iterrows():
                c1, c2, c3 = st.columns([2, 1, 4])
                if c1.button(f"📂 {row['프로젝트명']}", key=f"p_{idx}", use_container_width=True):
                    st.session_state["selected_menu"] = row['프로젝트명']; st.rerun()
                c2.metric("진척률", f"{row['진척률']}%")
                c3.info(f"**최신 브리핑:** {row['최신현황']}")
            st.divider()
            st.plotly_chart(px.bar(sum_df, x="프로젝트명", y="진척률", color="진척률", text_auto=True), use_container_width=True)

    # ---------------------------------------------------------
    # CASE 2: 상세 관리 (과거 히스토리 조회 기능 추가)
    # ---------------------------------------------------------
    else:
        p_name = st.session_state["selected_menu"]
        target_ws = sh.worksheet(p_name)
        st.title(f"🏗️ {p_name} 상세 관리")
        
        t1, t2, t3, t4 = st.tabs(["📊 공정표", "📝 일정등록", "📢 현황업데이트", "기록조회"])

        with t1:
            df = pd.DataFrame(target_ws.get_all_records())
            if not df.empty:
                df['시작일'] = pd.to_datetime(df['시작일'])
                df['종료일'] = pd.to_datetime(df['종료일'])
                fig = px.timeline(df[df['대분류']!='MILESTONE'], x_start="시작일", x_end="종료일", y="구분", color="진행상태")
                fig.update_yaxes(autorange="reversed")
                st.plotly_chart(fig, use_container_width=True)

        with t3:
            st.subheader("📢 주간 주요 현황 기록 (누적 저장)")
            with st.form("hist_form"):
                new_status = st.text_area("이번 주 주요 현황 및 이슈 작성")
                if st.form_submit_button("히스토리 저장 및 대시보드 반영"):
                    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                    # 히스토리 시트에 누적 저장
                    hist_ws.append_row([now, p_name, new_status, st.session_state['user_id']])
                    # 대시보드용 개별 시트 첫 행 비고도 업데이트 (호환성)
                    target_ws.update_acell("F2", new_status)
                    st.success("히스토리에 기록되었습니다."); time.sleep(1); st.rerun()

        with t4:
            st.subheader(f"📜 {p_name} 과거 현황 기록")
            h_data = pd.DataFrame(hist_ws.get_all_records())
            if not h_data.empty:
                p_h_data = h_data[h_data['프로젝트명'] == p_name].sort_index(ascending=False)
                if not p_h_data.empty:
                    for _, h_row in p_h_data.iterrows():
                        with st.expander(f"📅 {h_row['날짜']} | 작성자: {h_row['작성자']}"):
                            st.write(h_row['주요현황'])
                else: st.info("기록된 과거 데이터가 없습니다.")
            else: st.info("전체 히스토리가 비어 있습니다.")
