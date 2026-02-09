import streamlit as st
import pandas as pd
import datetime
import gspread
from google.oauth2.service_account import Credentials
import time
import plotly.express as px

# 1. 페이지 설정
st.set_page_config(page_title="PM 통합 공정 관리 시스템", page_icon="🏗️", layout="wide")

# --- 구글 시트 연결 함수 ---
@st.cache_resource
def get_client():
    try:
        if "gcp_service_account" not in st.secrets:
            st.error("🚨 Streamlit Cloud의 Secrets 설정 확인이 필요합니다.")
            return None
        key_dict = dict(st.secrets["gcp_service_account"])
        if "private_key" in key_dict:
            key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(key_dict, scopes=scopes)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"🚨 구글 인증 연결 실패: {e}")
        return None

# --- [기능] 새 프로젝트(시트) 생성 ---
def create_new_project(sh, project_name):
    try:
        existing_sheets = [s.title for s in sh.worksheets()]
        if project_name in existing_sheets:
            return False, "이미 존재하는 프로젝트 이름입니다."
        new_sheet = sh.add_worksheet(title=project_name, rows="100", cols="20")
        headers = ["시작일", "종료일", "대분류", "구분", "진행상태", "비고", "진행률", "담당자"]
        new_sheet.append_row(headers)
        return True, "성공"
    except Exception as e:
        return False, str(e)

# --- [기능] 기존 프로젝트(시트) 삭제 ---
def delete_project(sh, project_name):
    try:
        # 최소 하나의 시트는 남겨두어야 함 (구글 시트 제약)
        if len(sh.worksheets()) <= 1:
            return False, "마지막 남은 프로젝트 시트는 삭제할 수 없습니다."
        target_sheet = sh.worksheet(project_name)
        sh.del_worksheet(target_sheet)
        return True, "성공"
    except Exception as e:
        return False, str(e)

# --- 사이드바: 프로젝트 관리 ---
st.sidebar.title("📁 PMO 프로젝트 센터")

client = get_client()
if client:
    sh = client.open('pms_db')
    real_project_list = [s.title for s in sh.worksheets()]
else:
    real_project_list = ["연결 오류"]
    st.stop()

selected_pjt = st.sidebar.selectbox("🎯 관리 프로젝트 선택", real_project_list)

st.sidebar.divider()

# --- 프로젝트 추가/삭제 관리 섹션 ---
with st.sidebar.expander("🛠️ 프로젝트 목록 관리"):
    # 1. 추가 기능
    st.write("**[프로젝트 추가]**")
    add_name = st.text_input("새 프로젝트명", key="add_pjt")
    if st.button("시트 생성"):
        if add_name:
            success, msg = create_new_project(sh, add_name)
            if success:
                st.success("생성 완료!")
                time.sleep(1)
                st.rerun()
            else:
                st.error(msg)
    
    st.divider()
    
    # 2. 삭제 기능
    st.write("**[프로젝트 삭제]**")
    del_target = st.selectbox("삭제할 프로젝트 선택", real_project_list, key="del_pjt")
    confirm_del = st.checkbox(f"'{del_target}' 시트를 영구 삭제합니다.")
    
    if st.button("시트 삭제"):
        if confirm_del:
            success, msg = delete_project(sh, del_target)
            if success:
                st.warning("삭제 완료!")
                time.sleep(1)
                st.rerun()
            else:
                st.error(msg)
        else:
            st.info("삭제하려면 위 체크박스를 선택하세요.")

st.sidebar.divider()
st.sidebar.info(f"현재 접속: **{selected_pjt}**")

# --- 메인 화면 (기존 로직 유지) ---
st.title(f"🏗️ {selected_pjt} 공정 관리 시스템")

# 데이터 로드 로직 (get_project_data 생략 - 기존과 동일하게 유지)
def get_project_data(project_name):
    try:
        worksheet = sh.worksheet(project_name)
        data = worksheet.get_all_records()
        return pd.DataFrame(data), worksheet
    except:
        return pd.DataFrame(), None

df_raw, worksheet = get_project_data(selected_pjt)

if worksheet is None:
    st.warning("데이터를 불러올 수 없습니다.")
    st.stop()

# 이후 탭 1, 2, 3 구성은 이전 코드와 동일하게 적용하시면 됩니다.
# ... (중략) ...
