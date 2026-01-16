import streamlit as st
import pandas as pd
import datetime
import gspread
from google.oauth2.service_account import Credentials
import time
import json
import plotly.express as px
import plotly.graph_objects as go

# 1. 페이지 설정
st.set_page_config(page_title="현장 공정 관리", page_icon="🏗️", layout="wide")

# --- 구글 시트 연결 함수 ---
@st.cache_resource
def get_connection():
    try:
        if "gcp_service_account" not in st.secrets:
            st.error("🚨 Secrets 설정이 비어있습니다!")
            return None
        key_dict = dict(st.secrets["gcp_service_account"])
        if "private_key" in key_dict:
            key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(key_dict, scopes=scopes)
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        st.error(f"🚨 인증 연결 실패: {e}")
        return None

def get_pms_data():
    client = get_connection()
    if client:
        try:
            sh = client.open('pms_db') 
            worksheet = sh.sheet1
            data = worksheet.get_all_records()
            return pd.DataFrame(data), worksheet
        except Exception as e:
             st.error(f"🚨 데이터 읽기 오류: {e}")
             return pd.DataFrame(), None
    return pd.DataFrame(), None

# --- 메인 화면 ---
st.title("🏗️ 당진 적서리 태양광 PMS (Secure Ver.)")

df, sheet = get_pms_data()
if sheet is None:
    st.warning("데이터베이스 연결 대기 중...")
    st.stop()

# 탭 구성: 수정/삭제 기능을 위한 세 번째 탭 추가
tab1, tab2, tab3 = st.tabs(["📊 공정표 (Gantt)", "📝 일정 등록", "⚙️ 일정 관리 (수정/삭제)"])

# [탭 1] 공정표 조회
with tab1:
    st.subheader("실시간 공정 현황")
    if not df.empty:
        try:
            df['시작일'] = pd.to_datetime(df['시작일'])
            df['종료일'] = pd.to_datetime(df['종료일'])
            df['구분'] = df['구분'].astype(str).str.strip().replace('', '내용 없음').fillna('내용 없음')
            
            # 날짜순 정렬 및 Y축 순서 고정
            df_plot = df.sort_values(by="시작일", ascending=True)
            main_df = df_plot[df_plot['대분류'] != 'MILESTONE'].copy()
            y_order = main_df['구분'].unique().tolist()

            fig = px.timeline(main_df, x_start="시작일", x_end="종료일", y="구분", color="진행상태",
                             hover_data=["대분류", "비고"], category_orders={"구분": y_order})
            
            fig.update_layout(plot_bgcolor="white", height=600, margin=dict(t=100, l=10, r=10, b=10),
                              xaxis=dict(side="top", showgrid=True, dtick="M1", tickformat="%Y-%m"),
                              yaxis=dict(autorange="reversed", showgrid=True))
            
            fig.update_traces(marker_line_color="rgb(8,48,107)", marker_line_width=1, opacity=0.9)
            st.plotly_chart(fig, use_container_width=True)
        except Exception as e:
            st.warning(f"차트 생성 중 오류: {e}")
        st.divider()
        st.dataframe(df, use_container_width=True, hide_index=True)

# [탭 2] 일정 등록 (기존 기능)
with tab2:
    st.subheader("새로운 일정 등록")
    with st.form("input_form"):
        c1, c2 = st.columns(2)
        in_start = c1.date_input("시작일", datetime.date.today())
        in_end = c2.date_input("종료일", datetime.date.today() + datetime.timedelta(days=30))
        in_dae = st.selectbox("대분류", ["인허가", "설계/조사", "계약", "토목공사", "건축공사", "송전선로", "MILESTONE"])
        in_gubun = st.text_input("구분")
        in_status = st.selectbox("진행상태", ["예정", "진행중", "완료", "지연"])
        in_note = st.text_input("비고")
        if st.form_submit_button("저장하기 💾", use_container_width=True):
            sheet.append_row([str(in_start), str(in_end), in_dae, in_gubun, in_status, in_note])
            st.success("✅ 저장되었습니다!"); time.sleep(1); st.rerun()

# [탭 3] 일정 관리 (수정 및 삭제)
with tab3:
    st.subheader("기존 일정 수정 및 삭제")
    if not df.empty:
        # 수정/삭제할 항목 선택 (항목명 + 시작일로 구분)
        df_manage = df.copy()
        df_manage['selection'] = df_manage['구분'] + " (" + df_manage['시작일'].astype(str) + ")"
        target_item = st.selectbox("수정 또는 삭제할 항목을 선택하세요", df_manage['selection'].tolist())
        
        # 선택된 항목의 데이터 가져오기
        selected_idx = df_manage[df_manage['selection'] == target_item].index[0]
        row_data = df.iloc[selected_idx]
        
        # 수정 폼
        with st.form("edit_form"):
            st.write(f"📍 대상 행: 구글 시트 {selected_idx + 2}번 행")
            e_c1, e_c2 = st.columns(2)
            # 날짜 변환 처리
            curr_start = pd.to_datetime(row_data['시작일']).date()
            curr_end = pd.to_datetime(row_data['종료일']).date()
            
            up_start = e_c1.date_input("시작일 수정", curr_start)
            up_end = e_c2.date_input("종료일 수정", curr_end)
            
            e_c3, e_c4 = st.columns(2)
            up_dae = e_c3.selectbox("대분류 수정", ["인허가", "설계/조사", "계약", "토목공사", "건축공사", "송전선로", "MILESTONE"], 
                                   index=["인허가", "설계/조사", "계약", "토목공사", "건축공사", "송전선로", "MILESTONE"].index(row_data['대분류']) if row_data['대분류'] in ["인허가", "설계/조사", "계약", "토목공사", "건축공사", "송전선로", "MILESTONE"] else 0)
            up_gubun = e_c4.text_input("구분 수정", value=row_data['구분'])
            
            e_c5, e_c6 = st.columns(2)
            up_status = e_c5.selectbox("진행상태 수정", ["예정", "진행중", "완료", "지연"], 
                                      index=["예정", "진행중", "완료", "지연"].index(row_data['진행상태']) if row_data['진행상태'] in ["예정", "진행중", "완료", "지연"] else 0)
            up_note = e_c6.text_input("비고 수정", value=row_data['비고'])
            
            btn_col1, btn_col2 = st.columns(2)
            update_submitted = btn_col1.form_submit_button("내용 수정하기 🆙", use_container_width=True)
            delete_submitted = btn_col2.form_submit_button("항목 삭제하기 🗑️", use_container_width=True)
            
            if update_submitted:
                # 구글 시트 번호는 헤더 포함이라 index + 2
                cell_range = f"A{selected_idx + 2}:F{selected_idx + 2}"
                new_values = [[str(up_start), str(up_end), up_dae, up_gubun, up_status, up_note]]
                sheet.update(cell_range, new_values)
                st.success("✅ 일정이 수정되었습니다!"); time.sleep(1); st.rerun()
                
            if delete_submitted:
                # 해당 행 삭제
                sheet.delete_rows(selected_idx + 2)
                st.error("🗑️ 항목이 삭제되었습니다!"); time.sleep(1); st.rerun()
    else:
        st.info("관리할 데이터가 없습니다.")
