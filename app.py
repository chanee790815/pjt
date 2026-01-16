## 2026년 1월16일 버전이야

#🚀 Revision 2026-01-16 관리 가이드
#이 소스 코드를 별도로 관리하실 때 참고하실 수 있도록, 현재 적용된 주요 기능을 정리해 드립니다:
#오늘 날짜 표시선 (Today Line): 차트 중앙의 붉은 점선이 현재 날짜를 실시간으로 가리킵니다.
#공정 막대 내 상태 표시: 각 막대 안에 '진행중', '예정' 등의 진행 상태가 텍스트로 바로 표시됩니다.
#날짜 정밀화: 데이터 목록과 차트에서 불필요한 시간 정보(00:00:00)를 완전히 제거하여 가독성을 높였습니다.
#유연한 정렬: 시작일 기준으로 공정이 차례대로 내려오는 계단식 구조를 완성했습니다.
#💡 다음 리비전(Revision)을 위한 제안
#매일 함께 수정하기로 한 만큼, 내일은 이런 기능을 추가해 보는 건 어떨까요?
#진행률(%) 시각화: '진행중'인 공정의 막대 색상을 실제 진행된 만큼만 더 진하게 채워주는 기능.
#공정 간 연결선: 특정 업무가 끝나야 다음 업무가 시작될 수 있음을 보여주는 화살표 연결선.
#D-Day 카운트: 마일스톤(착공, 준공 등)까지 남은 일수를 상단에 자동으로 계산해 보여주는 기능.
# 오늘 고생 많으셨습니다! 이 소스는 꼭 잘 보관해 두시고, 내일 현장 상황에 맞춰 또 업데이트하고 싶은 부분이 생기면 언제든 말씀해 주세요. Would you like me to ...?


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
st.title("🏗️ 당진 적서리 태양광 PMS (Rev. 2026-01-16)")

df_raw, sheet = get_pms_data()
if sheet is None:
    st.warning("데이터베이스 연결 대기 중...")
    st.stop()

tab1, tab2, tab3 = st.tabs(["📊 공정표 (Gantt)", "📝 일정 등록", "⚙️ 일정 수정 및 삭제"])

# [탭 1] 공정표 조회
with tab1:
    st.subheader("실시간 공정 현황")
    if not df_raw.empty:
        try:
            df = df_raw.copy()
            # 날짜 전처리 (시간 제거)
            df['시작일'] = pd.to_datetime(df['시작일']).dt.normalize()
            df['종료일'] = pd.to_datetime(df['종료일']).dt.normalize()
            df['구분'] = df['구분'].astype(str).str.strip().replace('', '내용 없음').fillna('내용 없음')
            
            # [정렬] 시작일 기준 내림차순 (최신순 상단)
            df = df.sort_values(by="시작일", ascending=False).reset_index(drop=True)

            main_df = df[df['대분류'] != 'MILESTONE'].copy()
            ms_df = df[df['대분류'] == 'MILESTONE'].copy()
            
            # Y축 순서 고정 (역순 리스트 활용)
            y_order_custom = main_df['구분'].unique().tolist()[::-1]

            # 1. 간트 차트 생성
            fig = px.timeline(
                main_df, 
                x_start="시작일", 
                x_end="종료일", 
                y="구분", 
                color="진행상태",
                text="진행상태", # 막대 위에 상태 표시
                hover_data=["대분류", "비고"],
                category_orders={"구분": y_order_custom}
            )

            # 2. 마일스톤 화살표 추가 (Scatter 전용 설정 적용)
            if not ms_df.empty:
                for _, row in ms_df.iterrows():
                    fig.add_trace(go.Scatter(
                        x=[row['시작일']],
                        y=[y_order_custom[0]] if y_order_custom else [0], 
                        mode='markers+text',
                        marker=dict(symbol='arrow-bar-down', size=20, color='black'),
                        text=f"▼ {row['구분']}",
                        textposition="top center", # Scatter 에 맞는 위치값으로 고정
                        textfont=dict(color="red", size=11, family="Arial Black"),
                        name='MILESTONE',
                        showlegend=False
                    ))

            # 3. [추가] 오늘 날짜 표시선 (Today Line)
            today_dt = datetime.datetime.now()
            fig.add_vline(x=today_dt.timestamp() * 1000, line_width=2, line_dash="dash", line_color="red")
            fig.add_annotation(x=today_dt, y=1.05, yref="paper", text="TODAY", showarrow=False, font=dict(color="red", size=12))

            # 4. 레이아웃 설정
            fig.update_layout(
                plot_bgcolor="white",
                xaxis=dict(side="top", showgrid=True, gridcolor="#E5E5E5", dtick="M1", tickformat="%Y-%m", ticks="outside"),
                yaxis=dict(autorange=True, showgrid=True, gridcolor="#F0F0F0"),
                height=800,
                margin=dict(t=150, l=10, r=10, b=50),
                showlegend=True
            )
            
            # 5. 공정 막대 전용 설정 (textposition='inside'는 여기서만 적용)
            fig.update_traces(
                textposition='inside', 
                marker_line_color="rgb(8,48,107)", 
                marker_line_width=1, 
                opacity=0.8,
                selector=dict(type='bar') # Bar 형태의 데이터에만 적용하여 오류 방지
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
        except Exception as e:
            st.warning(f"차트 생성 중 오류: {e}")

        st.divider()
        st.write("📋 상세 데이터 목록")
        display_df = df.copy()
        display_df['시작일'] = display_df['시작일'].dt.strftime('%Y-%m-%d')
        display_df['종료일'] = display_df['종료일'].dt.strftime('%Y-%m-%d')
        st.dataframe(display_df, use_container_width=True, hide_index=True)

# [탭 2] 및 [탭 3] 로직은 기존 코드와 동일하므로, 전체 파일 구성 시 그대로 붙여넣으시면 됩니다.


# [탭 2] 및 [탭 3] 로직은 그대로 유지 (생략)

# [탭 2] 일정 등록
with tab2:
    st.subheader("새로운 일정 등록")
    with st.form("input_form"):
        c1, c2 = st.columns(2)
        in_start = c1.date_input("시작일", datetime.date.today())
        in_end = c2.date_input("종료일", datetime.date.today() + datetime.timedelta(days=30))
        in_dae = st.selectbox("대분류", ["인허가", "설계/조사", "계약", "토목공사", "건축공사", "송전선로", "변전설비", "전기공사", "MILESTONE"])
        in_gubun = st.text_input("구분")
        in_status = st.selectbox("진행상태", ["예정", "진행중", "완료", "지연"])
        in_note = st.text_input("비고")
        if st.form_submit_button("저장하기 💾", use_container_width=True):
            sheet.append_row([str(in_start), str(in_end), in_dae, in_gubun, in_status, in_note])
            st.success("✅ 저장되었습니다!"); time.sleep(1); st.rerun()

# [탭 3] 일정 수정 및 삭제
with tab3:
    st.subheader("기존 일정 수정 및 삭제")
    if not df_raw.empty:
        df_manage = df_raw.copy()
        df_manage['selection'] = df_manage['구분'].astype(str) + " (" + df_manage['시작일'].astype(str) + ")"
        target_item = st.selectbox("항목 선택", df_manage['selection'].tolist())
        selected_idx = df_manage[df_manage['selection'] == target_item].index[0]
        row_data = df_raw.iloc[selected_idx]
        
        with st.form("edit_form"):
            e_c1, e_c2 = st.columns(2)
            up_start = e_c1.date_input("시작일 수정", pd.to_datetime(row_data['시작일']).date())
            up_end = e_c2.date_input("종료일 수정", pd.to_datetime(row_data['종료일']).date())
            
            up_dae = st.selectbox("대분류 수정", ["인허가", "설계/조사", "계약", "토목공사", "건축공사", "송전선로", "변전설비", "전기공사", "MILESTONE"], 
                                   index=["인허가", "설계/조사", "계약", "토목공사", "건축공사", "송전선로", "변전설비", "전기공사", "MILESTONE"].index(row_data['대분류']) if row_data['대분류'] in ["인허가", "설계/조사", "계약", "토목공사", "건축공사", "송전선로", "변전설비", "전기공사", "MILESTONE"] else 0)
            up_gubun = st.text_input("구분 수정", value=row_data['구분'])
            up_status = st.selectbox("진행상태 수정", ["예정", "진행중", "완료", "지연"], 
                                      index=["예정", "진행중", "완료", "지연"].index(row_data['진행상태']) if row_data['진행상태'] in ["예정", "진행중", "완료", "지연"] else 0)
            up_note = st.text_input("비고 수정", value=row_data['비고'])
            
            b1, b2 = st.columns(2)
            if b1.form_submit_button("내용 업데이트 🆙", use_container_width=True):
                sheet.update(f"A{selected_idx + 2}:F{selected_idx + 2}", [[str(up_start), str(up_end), up_dae, up_gubun, up_status, up_note]])
                st.success("✅ 수정 완료!"); time.sleep(1); st.rerun()
            if b2.form_submit_button("항목 삭제하기 🗑️", use_container_width=True):
                sheet.delete_rows(selected_idx + 2)
                st.error("🗑️ 삭제 완료!"); time.sleep(1); st.rerun()



