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
            # 줄바꿈 문자 처리
            key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")
            
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(key_dict, scopes=scopes)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"🚨 구글 인증 연결 실패: {e}")
        return None

def get_project_data(project_name):
    client = get_client()
    if client:
        try:
            # 구글 스프레드시트 파일 이름 'pms_db'를 엽니다.
            sh = client.open('pms_db')
            worksheet = sh.worksheet(project_name)
            data = worksheet.get_all_records()
            return pd.DataFrame(data), worksheet
        except Exception as e:
            st.error(f"🚨 '{project_name}' 데이터를 불러오는데 실패했습니다: {e}")
            return pd.DataFrame(), None
    return pd.DataFrame(), None

# --- 사이드바: 프로젝트 마스터 선택 ---
st.sidebar.title("📁 PMO 프로젝트 센터")
# 관리하실 5개 프로젝트 리스트 (구글 시트 탭 이름과 일치해야 함)
project_list = ["적서리 PJT", "당진 교로리 PJT", "평택 데이터센터 PJT", "새만금 솔라 PJT", "경주 풍력 PJT"]
selected_pjt = st.sidebar.selectbox("🎯 관리 프로젝트 선택", project_list)

st.sidebar.divider()
st.sidebar.info(f"현재 접속 프로젝트: \n**{selected_pjt}**")

st.title(f"🏗️ {selected_pjt} 공정 관리 시스템")

# 데이터 로드
df_raw, worksheet = get_project_data(selected_pjt)

if worksheet is None:
    st.warning("데이터베이스 연결 대기 중... 구글 시트의 탭 이름을 확인해주세요.")
    st.stop()

# --- 탭 구성 ---
tab1, tab2, tab3 = st.tabs(["📊 통합 공정표", "📝 일정 등록", "⚙️ 관리 및 수정"])

# [탭 1] 통합 공정표 조회
with tab1:
    if not df_raw.empty:
        # 1. 마일스톤 D-Day 대시보드
        st.subheader("🚩 핵심 마일스톤 현황")
        ms_only = df_raw[df_raw['대분류'] == 'MILESTONE'].copy()
        if not ms_only.empty:
            cols = st.columns(len(ms_only))
            for i, (_, row) in enumerate(ms_only.iterrows()):
                target_date = pd.to_datetime(row['시작일']).date()
                days_left = (target_date - datetime.date.today()).days
                cols[i].metric(
                    label=row['구분'], 
                    value=f"D-{days_left}" if days_left > 0 else f"D+{abs(days_left)}", 
                    delta=str(target_date)
                )
        
        st.divider()

        # 2. Gantt 차트 (Plotly)
        df = df_raw.copy()
        df['시작일'] = pd.to_datetime(df['시작일'])
        df['종료일'] = pd.to_datetime(df['종료일'])
        
        # 실제 공정만 필터링 (마일스톤 제외하고 차트 표시)
        chart_df = df[df['대분류'] != 'MILESTONE'].copy()
        
        if not chart_df.empty:
            fig = px.timeline(
                chart_df, x_start="시작일", x_end="종료일", y="구분", 
                color="진행상태", 
                hover_data={"담당자":True, "진행률":True, "비고":True},
                title=f"{selected_pjt} 공정 타임라인"
            )
            fig.update_yaxes(autorange="reversed") # 최신 공정이 위로
            fig.update_layout(height=600, template="plotly_white")
            st.plotly_chart(fig, use_container_width=True)
            
            # 3. 상세 테이블
            with st.expander("📋 상세 데이터 시트 보기"):
                st.dataframe(df_raw, use_container_width=True)
        else:
            st.info("등록된 일반 공정이 없습니다.")
    else:
        st.info("데이터가 비어있습니다. '일정 등록' 탭에서 데이터를 추가해주세요.")

# [탭 2] 일정 등록
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

# [탭 3] 관리 및 수정
with tab3:
    st.subheader(f"⚙️ {selected_pjt} 기존 공정 수정 및 삭제")
    if not df_raw.empty:
        # 수정을 위한 항목 선택
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
                # 구글 시트 업데이트 (1-based index, 헤더 포함이므로 idx + 2)
                worksheet.update(f"A{selected_idx + 2}:H{selected_idx + 2}", [update_values])
                st.success("✅ 업데이트 완료!"); time.sleep(1); st.rerun()
                
            if del_col.form_submit_button("항목 삭제하기 🗑️"):
                worksheet.delete_rows(selected_idx + 2)
                st.error("🗑️ 삭제 완료!"); time.sleep(1); st.rerun()
    else:
        st.info("수정할 데이터가 없습니다.")
