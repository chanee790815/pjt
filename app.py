## [PMS Revision History]
## 버전: Rev. 0.6.7 (New Project Registration Fix)
## 업데이트 요약:
## 1. 🛠️ 신규 프로젝트 일정 등록 버그 수정: 헤더 표준화 및 빈 시트 데이터 로드 예외 처리 강화
## 2. ➕ 프로젝트 생성 시 초기 데이터 구조 강제화: 첫 행 헤더 입력 로직 정밀화
## 3. 🔄 실시간 동기화: 일정 등록 후 st.rerun()을 통한 즉각적인 차트 반영

import streamlit as st
import pandas as pd
import datetime
import gspread
from google.oauth2.service_account import Credentials
import time
import plotly.express as px

# 1. 페이지 설정
st.set_page_config(page_title="PM 통합 공정 관리 v0.6.7", page_icon="🏗️", layout="wide")

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

# --- [기능] 신규 프로젝트 시트 생성 함수 ---
def create_new_project_sheet(sh, name):
    try:
        existing_sheets = [s.title for s in sh.worksheets()]
        if name in existing_sheets:
            return False, "이미 존재하는 프로젝트 이름입니다."
        
        new_ws = sh.add_worksheet(title=name, rows="100", cols="20")
        # 컬럼명 표준화 (시작일, 종료일, 대분류, 구분, 진행상태, 비고, 진행률, 담당자)
        header = ["시작일", "종료일", "대분류", "구분", "진행상태", "비고", "진행률", "담당자"]
        new_ws.append_row(header)
        return True, "성공"
    except Exception as e:
        return False, str(e)

client = get_client()
if client:
    sh = client.open('pms_db')
    all_ws = [ws for ws in sh.worksheets() if not ws.title.startswith('weekly_history')]
    pjt_names = [s.title for s in all_ws]
    
    try:
        hist_ws = sh.worksheet('weekly_history')
    except:
        hist_ws = sh.add_worksheet(title='weekly_history', rows="1000", cols="5")
        hist_ws.append_row(["날짜", "프로젝트명", "주요현황", "작성자"])

    if "selected_menu" not in st.session_state:
        st.session_state["selected_menu"] = "🏠 전체 대시보드"

    # 사이드바
    st.sidebar.title("📁 PMO 프로젝트 센터")
    menu = ["🏠 전체 대시보드"] + pjt_names
    selected = st.sidebar.selectbox("🎯 메뉴 선택", menu, index=menu.index(st.session_state["selected_menu"]), key="nav_menu")
    st.session_state["selected_menu"] = selected

    # 프로젝트 신규 생성 (이미지 image_4ed25d.png의 기능)
    with st.sidebar.expander("➕ 프로젝트 신규 생성", expanded=False):
        new_name = st.text_input("새 프로젝트 명칭")
        if st.button("프로젝트 시트 생성"):
            if new_name:
                success, msg = create_new_project_sheet(sh, new_name)
                if success:
                    st.sidebar.success("생성 완료!"); time.sleep(1); st.rerun()
                else: st.sidebar.error(msg)

    # ---------------------------------------------------------
    # CASE 2: 상세 관리 (이미지 image_4ed25d.png의 '동서발전 1차 사업' 화면)
    # ---------------------------------------------------------
    if st.session_state["selected_menu"] != "🏠 전체 대시보드":
        p_name = st.session_state["selected_menu"]
        target_ws = sh.worksheet(p_name)
        
        # 데이터 로드 시 빈 시트 처리 강화
        data_all = target_ws.get_all_records()
        df_raw = pd.DataFrame(data_all) if data_all else pd.DataFrame(columns=["시작일", "종료일", "대분류", "구분", "진행상태", "비고", "진행률", "담당자"])
        
        st.title(f"🏗️ {p_name} 상세 관리")
        t1, t2, t3, t4 = st.tabs(["📊 통합 공정표", "📝 일정등록", "📢 현황업데이트", "📜 과거기록조회"])

        with t1:
            if not df_raw.empty:
                # 차트 및 테이블 출력 로직 (생략)
                st.dataframe(df_raw, use_container_width=True)
            else:
                st.info("💡 등록된 공정이 없습니다. '일정등록' 탭에서 첫 공정을 추가해 주세요.")

        # [중요] 일정 등록 탭 수정 (image_4ed25d.png에서 안되던 부분)
        with t2:
            st.subheader("📝 신규 일정 등록")
            with st.form("new_schedule_form"):
                col1, col2, col3 = st.columns(3)
                s_date = col1.date_input("시작일")
                e_date = col2.date_input("종료일")
                category = col3.selectbox("대분류", ["인허가", "설계/조사", "토목공사", "계약", "MILESTONE", "기타"])
                
                name = st.text_input("공정명 (구분)")
                status = st.selectbox("진행상태", ["예정", "진행중", "완료", "지연"])
                progress = st.number_input("진행률(%)", 0, 100, 0)
                note = st.text_area("비고")
                
                if st.form_submit_button("공정 추가"):
                    if name:
                        # 시트 형식에 맞춰 데이터 추가
                        new_row = [str(s_date), str(e_date), category, name, status, note, progress, st.session_state['user_id']]
                        target_ws.append_row(new_row)
                        st.success(f"'{name}' 공정이 등록되었습니다.")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.warning("공정명을 입력해 주세요.")
