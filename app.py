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
            st.error("🚨 Streamlit Cloud의 Secrets 설정에 구글 서비스 계정 정보가 없습니다.")
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

# --- [추가] 새 프로젝트(시트) 생성 함수 ---
def create_new_project(project_name):
    client = get_client()
    if client:
        try:
            sh = client.open('pms_db')
            # 이미 존재하는지 확인
            existing_sheets = [s.title for s in sh.worksheets()]
            if project_name in existing_sheets:
                st.sidebar.warning(f"⚠️ '{project_name}'은 이미 존재하는 프로젝트입니다.")
                return False
            
            # 새 시트 생성 (100행 20열 기본)
            new_sheet = sh.add_worksheet(title=project_name, rows="100", cols="20")
            # 헤더 자동 입력
            headers = ["시작일", "종료일", "대분류", "구분", "진행상태", "비고", "진행률", "담당자"]
            new_sheet.append_row(headers)
            return True
        except Exception as e:
            st.sidebar.error(f"🚨 시트 생성 실패: {e}")
            return False

def get_project_data(project_name):
    client = get_client()
    if client:
        try:
            sh = client.open('pms_db')
            # 실제 구글 시트에 있는 탭 목록을 가져와서 연동
            worksheet = sh.worksheet(project_name)
            data = worksheet.get_all_records()
            return pd.DataFrame(data), worksheet
        except Exception as e:
            return pd.DataFrame(), None
    return pd.DataFrame(), None

# --- 사이드바: 프로젝트 관리 ---
st.sidebar.title("📁 PMO 프로젝트 센터")

# 1. 실제 구글 시트에서 프로젝트 목록(탭 이름) 실시간으로 가져오기
client = get_client()
if client:
    sh = client.open('pms_db')
    real_project_list = [s.title for s in sh.worksheets()]
else:
    real_project_list = ["연결 오류"]

selected_pjt = st.sidebar.selectbox("🎯 관리 프로젝트 선택", real_project_list)

st.sidebar.divider()

# 2. [추가] 새 프로젝트 추가 섹션
with st.sidebar.expander("➕ 새 프로젝트 추가"):
    new_pjt_name = st.text_input("프로젝트명 입력", placeholder="예: 부산 에코 PJT")
    if st.button("시트 생성 및 등록"):
        if new_pjt_name:
            with st.spinner("구글 시트 생성 중..."):
                if create_new_project(new_pjt_name):
                    st.success(f"'{new_pjt_name}' 생성 완료!")
                    time.sleep(1)
                    st.rerun()
        else:
            st.error("이름을 입력하세요.")

st.sidebar.divider()
st.sidebar.info(f"현재 접속 프로젝트: \n**{selected_pjt}**")

# --- 메인 화면 시작 ---
st.title(f"🏗️ {selected_pjt} 공정 관리 시스템")

# 데이터 로드
df_raw, worksheet = get_project_data(selected_pjt)

if worksheet is None:
    st.warning("데이터베이스 연결 대기 중... 왼쪽 사이드바에서 프로젝트를 선택하거나 새로 생성해주세요.")
    st.stop()

# --- 탭 구성 (이하 기존 코드와 동일) ---
tab1, tab2, tab3 = st.tabs(["📊 통합 공정표", "📝 일정 등록", "⚙️ 관리 및 수정"])

# [탭 1] 통합 공정표 조회
with tab1:
    if not df_raw.empty:
        st.subheader("🚩 핵심 마일스톤 현황")
        # 데이터가 있을 때만 처리 (오류 방지)
        if '대분류' in df_raw.columns:
            ms_only = df_raw[df_raw['대분류'] == 'MILESTONE'].copy()
            if not ms_only.empty:
                cols = st.columns(len(ms_only))
                for i, (_, row) in enumerate(ms_only.iterrows()):
                    try:
                        target_date = pd.to_datetime(row['시작일']).date()
                        days_left = (target_date - datetime.date.today()).days
                        cols[i].metric(
                            label=row['구분'], 
                            value=f"D-{days_left}" if days_left > 0 else f"D+{abs(days_left)}", 
                            delta=str(target_date)
                        )
                    except: continue
        
        st.divider()

        # Gantt 차트
        df = df_raw.copy()
        if not df.empty and '시작일' in df.columns:
            df['시작일'] = pd.to_datetime(df['시작일'])
            df['종료일'] = pd.to_datetime(df['종료일'])
            chart_df = df[df['대분류'] != 'MILESTONE'].copy()
            
            if not chart_df.empty:
                fig = px.timeline(
                    chart_df, x_start="시작일", x_end="종료일", y="구분", 
                    color="진행상태", 
                    hover_data={"담당자":True, "진행률":True, "비고":True},
                    title=f"{selected_pjt} 공정 타임라인"
                )
                fig.update_yaxes(autorange="reversed")
                fig.update_layout(height=600, template="plotly_white")
                st.plotly_chart(fig, use_container_width=True)
                
                with st.expander("📋 상세 데이터 시트 보기"):
                    st.dataframe(df_raw, use_container_width=True)
            else:
                st.info("등록된 일반 공정이 없습니다.")
    else:
        st.info("데이터가 비어있습니다. '일정 등록' 탭에서 첫 데이터를 추가해주세요.")

# [탭 2] 일정 등록 (기존과 동일)
with tab2:
    st.subheader(f"📝 {selected_pjt} 신규 공정 추가")
    with st.form("input_form"):
        c1, c2, c3 = st.columns(3)
        in_start = c1.date_input("시작일", datetime.date.today())
        in_end = c2.date_input("종료일", datetime.date.today() + datetime.timedelta(days=30))
        in_dae = c3.selectbox("대분류", ["인허가", "설계/조사", "계약", "토목공사", "건축공사", "송전선로", "변전설비", "전기공사", "MILESTONE"])
        
        c4, c5, c6 = st.columns(3)
        in_gubun = c4.text_input("공정 구분 (이름)")
        in_status = c5.selectbox("진행상태", ["예정", "진행중", "완료", "지연"])
        in_percent = c6.number_input("진행률 (%)", 0, 100, 0)
        
        in_pic = st.text_input("담당자/협력사")
        in_note = st.text_area("비고")
        
        if st.form_submit_button(f"{selected_pjt} 시트에 저장 💾"):
            sheet_data = [str(in_start), str(in_end), in_dae, in_gubun, in_status, in_note, in_percent, in_pic]
            worksheet.append_row(sheet_data)
            st.success(f"✅ {selected_pjt} 시트에 저장이 완료되었습니다!"); time.sleep(1); st.rerun()

# [탭 3] 관리 및 수정 (기존과 동일)
with tab3:
    st.subheader(f"⚙️ {selected_pjt} 기존 공정 수정 및 삭제")
    if not df_raw.empty:
        df_raw['selection'] = df_raw['구분'].astype(str) + " (" + df_raw['시작일'].astype(str) + ")"
        target_item = st.selectbox("항목 선택", df_raw['selection'].tolist())
        selected_idx = df_raw[df_raw['selection'] == target_item].index[0]
        row_data = df_raw.iloc[selected_idx]
        
        with st.form("edit_form"):
            st.info(f"📍 선택된 공정: {row_data['구분']}")
            e_c1, e_c2 = st.columns(2)
            up_start = e_c1.date_input("시작일 수정", pd.to_datetime(row_data['시작일']).date())
            up_end = e_c2.date_input("종료일 수정", pd.to_datetime(row_data['종료일']).date())
            
            up_status = st.selectbox("진행상태 수정", ["예정", "진행중", "완료", "지연"], 
                                     index=["예정", "진행중", "완료", "지연"].index(row_data['진행상태']))
            up_percent = st.number_input("진행률 수정 (%)", 0, 100, int(row_data['진행률']))
            up_note = st.text_area("비고 수정", value=row_data['비고'])
            
            edit_col, del_col = st.columns(2)
            if edit_col.form_submit_button("내용 업데이트 🆙"):
                update_values = [str(up_start), str(up_end), row_data['대분류'], row_data['구분'], up_status, up_note, up_percent, row_data['담당자']]
                worksheet.update(f"A{selected_idx + 2}:H{selected_idx + 2}", [update_values])
                st.success("✅ 업데이트 완료!"); time.sleep(1); st.rerun()
                
            if del_col.form_submit_button("항목 삭제하기 🗑️"):
                worksheet.delete_rows(selected_idx + 2)
                st.error("🗑️ 삭제 완료!"); time.sleep(1); st.rerun()
