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
st.title("🏗️ 당진 적서리 태양광 PMS (Final Corrected)")

df_raw, sheet = get_pms_data()
if sheet is None:
    st.warning("데이터베이스 연결 대기 중...")
    st.stop()

# 탭 구성: 조회 / 등록 / 수정 및 삭제
tab1, tab2, tab3 = st.tabs(["📊 공정표 (Gantt)", "📝 일정 등록", "⚙️ 일정 수정 및 삭제"])

# [탭 1] 공정표 조회
with tab1:
    st.subheader("실시간 공정 현황")
    if not df_raw.empty:
        try:
            df = df_raw.copy()
            # 1. 날짜 데이터 형식 변환 및 전처리
            df['시작일'] = pd.to_datetime(df['시작일'])
            df['종료일'] = pd.to_datetime(df['종료일'])
            # 구분이 비어있으면 '내용 없음'으로 채워 차트 누락 방지
            df['구분'] = df['구분'].astype(str).str.strip().replace('', '내용 없음').fillna('내용 없음')
            
            # 2. [핵심] 시작일 기준으로 오름차순 정렬 (빠른 날짜가 위로)
            df = df.sort_values(by="시작일", ascending=True).reset_index(drop=True)

            # 3. 마일스톤과 일반 공정 분리
            main_df = df[df['대분류'] != 'MILESTONE'].copy()
            ms_df = df[df['대분류'] == 'MILESTONE'].copy()
            
            # 4. [중요] Y축 표시 순서를 정렬된 데이터의 '구분' 순서 그대로 고정
            y_order = main_df['구분'].unique().tolist()

            # 5. 간트 차트 생성
            fig = px.timeline(
                main_df, 
                x_start="시작일", 
                x_end="종료일", 
                y="구분", 
                color="진행상태",
                hover_data=["대분류", "비고"],
                category_orders={"구분": y_order}  # 리스트 순서대로 Y축 배치 강제
            )

            # 6. 상단 마일스톤 화살표 추가 (PDF 스타일)
            if not ms_df.empty:
                for _, row in ms_df.iterrows():
                    fig.add_trace(go.Scatter(
                        x=[row['시작일']],
                        y=[y_order[0]] if y_order else [0], 
                        mode='markers+text',
                        marker=dict(symbol='arrow-bar-down', size=20, color='black'),
                        text=f"▼ {row['구분']}",
                        textposition="top center",
                        textfont=dict(color="red", size=12, family="Arial Black"),
                        name='MILESTONE',
                        showlegend=False,
                        cliponaxis=False
                    ))

            # 7. 레이아웃 최종 교정 (상단 년월 및 격자선)
            fig.update_layout(
                plot_bgcolor="white",
                xaxis=dict(
                    side="top",
                    showgrid=True,
                    gridcolor="rgba(220, 220, 220, 0.8)",
                    dtick="M1",
                    tickformat="%Y-%m",
                    ticks="outside"
                ),
                yaxis=dict(
                    autorange="reversed", # 리스트의 첫 항목(빠른 날짜)이 맨 위로 오게 함
                    showgrid=True, 
                    gridcolor="rgba(240, 240, 240, 0.8)"
                ),
                height=800,
                margin=dict(t=150, l=10, r=10, b=50),
                showlegend=True
            )
            
            fig.update_traces(marker_line_color="rgb(8,48,107)", marker_line_width=1, opacity=0.8)
            st.plotly_chart(fig, use_container_width=True)
            
        except Exception as e:
            st.warning(f"차트 생성 중 오류: {e}")

        st.divider()
        st.write("📋 상세 데이터 목록")
        # 목록도 날짜순으로 정렬해서 보여줌
        st.dataframe(df.sort_values(by="시작일"), use_container_width=True, hide_index=True)

# [탭 2] 일정 등록
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
            # 빈 구분에 대한 보정
            final_gubun = in_gubun if in_gubun.strip() != "" else "내용 없음"
            sheet.append_row([str(in_start), str(in_end), in_dae, final_gubun, in_status, in_note])
            st.success("✅ 일정이 저장되었습니다!"); time.sleep(1); st.rerun()

# [탭 3] 일정 수정 및 삭제
with tab3:
    st.subheader("기존 일정 관리")
    if not df_raw.empty:
        df_manage = df_raw.copy()
        # 선택박스에서 식별하기 편하도록 구분+날짜 결합
        df_manage['selection'] = df_manage['구분'].astype(str) + " (" + df_manage['시작일'].astype(str) + ")"
        
        target_item = st.selectbox("수정 또는 삭제할 항목 선택", df_manage['selection'].tolist())
        selected_idx = df_manage[df_manage['selection'] == target_item].index[0]
        row_data = df_raw.iloc[selected_idx]
        
        with st.form("edit_form"):
            st.write(f"📍 대상 데이터 위치: 구글 시트 {selected_idx + 2}번 행")
            e_c1, e_c2 = st.columns(2)
            up_start = e_c1.date_input("시작일 수정", pd.to_datetime(row_data['시작일']).date())
            up_end = e_c2.date_input("종료일 수정", pd.to_datetime(row_data['종료일']).date())
            
            e_c3, e_c4 = st.columns(2)
            up_dae = e_c3.selectbox("대분류 수정", ["인허가", "설계/조사", "계약", "토목공사", "건축공사", "송전선로", "MILESTONE"], 
                                   index=["인허가", "설계/조사", "계약", "토목공사", "건축공사", "송전선로", "MILESTONE"].index(row_data['대분류']) if row_data['대분류'] in ["인허가", "설계/조사", "계약", "토목공사", "건축공사", "송전선로", "MILESTONE"] else 0)
            up_gubun = e_c4.text_input("구분 수정", value=row_data['구분'])
            
            e_c5, e_c6 = st.columns(2)
            up_status = e_c5.selectbox("진행상태 수정", ["예정", "진행중", "완료", "지연"], 
                                      index=["예정", "진행중", "완료", "지연"].index(row_data['진행상태']) if row_data['진행상태'] in ["예정", "진행중", "완료", "지연"] else 0)
            up_note = e_c6.text_input("비고 수정", value=row_data['비고'])
            
            b1, b2 = st.columns(2)
            if b1.form_submit_button("내용 업데이트 🆙", use_container_width=True):
                cell_range = f"A{selected_idx + 2}:F{selected_idx + 2}"
                new_values = [[str(up_start), str(up_end), up_dae, up_gubun, up_status, up_note]]
                sheet.update(cell_range, new_values)
                st.success("✅ 수정 완료!"); time.sleep(1); st.rerun()
                
            if b2.form_submit_button("항목 삭제하기 🗑️", use_container_width=True):
                sheet.delete_rows(selected_idx + 2)
                st.error("🗑️ 삭제 완료!"); time.sleep(1); st.rerun()
