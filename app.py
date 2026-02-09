import streamlit as st
import pandas as pd
import datetime
import gspread
from google.oauth2.service_account import Credentials
import plotly.express as px
import time

# 1. 페이지 설정
st.set_page_config(page_title="PM 통합 공정 관리", page_icon="🏗️", layout="wide")

# --- 구글 시트 연결 함수 ---
@st.cache_resource
def get_client():
    if "gcp_service_account" not in st.secrets:
        st.error("🚨 Secrets 설정이 필요합니다.")
        return None
    key_dict = dict(st.secrets["gcp_service_account"])
    if "private_key" in key_dict:
        key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(key_dict, scopes=scopes)
    return gspread.authorize(creds)

def get_project_data(project_name):
    client = get_client()
    if client:
        try:
            sh = client.open('pms_db')
            worksheet = sh.worksheet(project_name)
            data = worksheet.get_all_records()
            return pd.DataFrame(data), worksheet
        except Exception as e:
            st.error(f"🚨 '{project_name}' 시트를 찾을 수 없습니다: {e}")
    return pd.DataFrame(), None

# --- 사이드바: 프로젝트 마스터 선택 ---
st.sidebar.title("📁 PMO 프로젝트 센터")
project_list = ["적서리 PJT", "당진 교로리 PJT", "평택 데이터센터 PJT", "새만금 솔라 PJT", "경주 풍력 PJT"]
selected_pjt = st.sidebar.selectbox("🎯 관리 프로젝트 선택", project_list)

st.title(f"🏗️ {selected_pjt} 공정 관리 시스템")

# 데이터 로드
df_raw, worksheet = get_project_data(selected_pjt)

if worksheet is None:
    st.warning("데이터베이스 연결 대기 중...")
    st.stop()

# --- 탭 구성 (복구 완료) ---
tab1, tab2, tab3 = st.tabs(["📊 통합 공정표", "📝 일정 등록", "⚙️ 관리 및 수정"])

# [탭 1] 통합 공정표
with tab1:
    if not df_raw.empty:
        # 마일스톤 D-Day 대시보드
        ms = df_raw[df_raw['대분류'] == 'MILESTONE'].copy()
        if not ms.empty:
            cols = st.columns(len(ms))
            for i, (_, row) in enumerate(ms.iterrows()):
                d_day = (pd.to_datetime(row['시작일']).date() - datetime.date.today()).days
                cols[i].metric(row['구분'], f"D{d_day:+d}", str(row['시작일']))
        
        # Gantt 차트
        df = df_raw.copy()
        df['시작일'] = pd.to_datetime(df['시작일'])
        df['종료일'] = pd.to_datetime(df['종료일'])
        fig = px.timeline(df[df['대분류'] != 'MILESTONE'], x_start="시작일", x_end="종료일", y="구분", color="진행상태")
        fig.update_yaxes(autorange="reversed")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("데이터가 없습니다. 일정 등록 탭에서 첫 공정을 추가해주세요.")

# [탭 2] 일정 등록 (선택된 프로젝트 시트에 저장)
with tab2:
    st.subheader(f"📝 {selected_pjt} 신규 공정 추가")
    with st.form("input_form"):
        c1, c2, c3 = st.columns(3)
        in_start = c1.date_input("시작일", datetime.date.today())
        in_end = c2.date_input("종료일", datetime.date.today() + datetime.timedelta(days=30))
        in_dae = c3.selectbox("대분류", ["인허가", "설계/조사", "토목공사", "전기공사", "MILESTONE"])
        
        c4, c5, c6 = st.columns(3)
        in_gubun = c4.text_input("공정명")
        in_status = c5.selectbox("진행상태", ["예정", "진행중", "완료", "지연"])
        in_percent = c6.number_input("진행률 (%)", 0, 100, 0)
        
        in_pic = st.text_input("담당자")
        in_note = st.text_area("비고")
        
        if st.form_submit_button(f"{selected_pjt}에 저장 💾"):
            new_row = [str(in_start), str(in_end), in_dae, in_gubun, in_status, in_note, in_percent, in_pic]
            worksheet.append_row(new_row)
            st.success(f"✅ {selected_pjt} 시트에 저장되었습니다!"); time.sleep(1); st.rerun()

# [탭 3] 관리 및 수정 (선택된 프로젝트 시트 데이터 수정)
with tab3:
    st.subheader(f"⚙️ {selected_pjt} 데이터 수정/삭제")
    if not df_raw.empty:
        df_raw['selection'] = df_raw['구분'].astype(str) + " (" + df_raw['시작일'].astype(str) + ")"
        target_item = st.selectbox("수정할 항목 선택", df_raw['selection'].tolist())
        idx = df_raw[df_raw['selection'] == target_item].index[0]
        row = df_raw.iloc[idx]

        with st.form("edit_form"):
            st.info(f"📍 수정 대상: {row['구분']}")
            e_c1, e_c2 = st.columns(2)
            up_start = e_c1.date_input("시작일", pd.to_datetime(row['시작일']).date())
            up_end = e_c2.date_input("종료일", pd.to_datetime(row['종료일']).date())
            
            up_status = st.selectbox("진행상태", ["예정", "진행중", "완료", "지연"], index=["예정", "진행중", "완료", "지연"].index(row['진행상태']))
            up_percent = st.number_input("진행률", 0, 100, int(row['진행률']))
            up_note = st.text_area("비고", value=row['비고'])
            
            edit_btn, del_btn = st.columns(2)
            if edit_btn.form_submit_button("내용 업데이트 🆙"):
                # 구글 시트는 1-based index이며 헤더 포함이므로 idx + 2
                worksheet.update(f"A{idx+2}:H{idx+2}", [[str(up_start), str(up_end), row['대분류'], row['구분'], up_status, up_note, up_percent, row['담당자']]])
                st.success("업데이트 완료!"); time.sleep(1); st.rerun()
            
            if del_btn.form_submit_button("항목 삭제 🗑️"):
                worksheet.delete_rows(idx + 2)
                st.error("삭제 완료!"); time.sleep(1); st.rerun()
