## [PMS Revision History]
## 버전: Rev. 0.5.2 (Multi-User Auth)
## 업데이트 요약:
## 1. 멀티 계정 로그인: secrets의 [passwords] 섹션에 등록된 모든 사용자 허용
## 2. 사용자별 세션 관리: 로그인한 사용자의 이름을 사이드바에 표시
## 3. 보안 최적화: ID/PW가 모두 일치해야 시스템 진입 가능

import streamlit as st
import pandas as pd
import datetime
import gspread
from google.oauth2.service_account import Credentials
import time
import plotly.express as px

# 1. 페이지 설정
st.set_page_config(page_title="PM 통합 공정 관리 v0.5.2", page_icon="🔐", layout="wide")

# --- [수정] 멀티 계정 로그인 체크 함수 ---
def check_password():
    """아이디와 비밀번호 리스트를 대조하여 로그인 여부를 결정합니다."""
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False

    if st.session_state["password_correct"]:
        return True

    st.title("🏗️ PM 통합 공정 관리 시스템")
    st.subheader("팀원 계정으로 로그인해 주세요.")
    
    with st.form("login_form"):
        user_id = st.text_input("아이디 (Username)")
        password = st.text_input("비밀번호 (Password)", type="password")
        submit_button = st.form_submit_button("로그인")
        
        if submit_button:
            # secrets.toml의 [passwords] 섹션 가져오기
            user_db = st.secrets["passwords"]
            
            # 아이디 존재 여부 및 비밀번호 일치 확인
            if user_id in user_db and password == user_db[user_id]:
                st.session_state["password_correct"] = True
                st.session_state["user_id"] = user_id # 접속자 아이디 저장
                st.success(f"✅ {user_id}님, 환영합니다!")
                time.sleep(1)
                st.rerun()
            else:
                st.error("😕 아이디 또는 비밀번호가 잘못되었습니다.")
    return False

# 로그인 실행
if not check_password():
    st.stop()

# --- 구글 시트 연결 함수 ---
@st.cache_resource
def get_client():
    try:
        # secrets에서 gcp_service_account 정보를 읽어옴
        key_dict = dict(st.secrets["gcp_service_account"])
        if "private_key" in key_dict:
            key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(key_dict, scopes=scopes)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"🚨 인증 오류: {e}"); return None

# --- 메인 실행 ---
client = get_client()
if client:
    sh = client.open('pms_db')
    all_ws = sh.worksheets()
    pjt_names = [s.title for s in all_ws]
    
    # [사이드바]
    st.sidebar.title("📁 PMO 프로젝트 센터")
    
    # 누가 접속했는지 표시
    st.sidebar.write(f"👤 접속자: **{st.session_state['user_id']}**")
    
    if st.sidebar.button("🔓 로그아웃"):
        st.session_state["password_correct"] = False
        st.rerun()
    
    st.sidebar.divider()
    
    # (이후 메뉴 선택, 대시보드 및 공정표 로직은 v0.5.1과 동일)
    menu = ["🏠 전체 대시보드"] + pjt_names
    selected = st.sidebar.selectbox("🎯 메뉴 선택", menu)
    
    # ... [이하 중략: v0.5.1 코드와 동일하게 유지] ...
