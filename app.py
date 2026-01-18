## 2026년 1월16일 버전이야

#🌟 업데이트 포인트 설명
#D-Day 대시보드: 차트 최상단에 마일스톤 날짜를 계산해 보여줍니다. PDF에 명시된 '개발행위허가', '종합 준공' 등의 목표일까지 남은 일수를 실시간으로 확인하세요. 
#진행률 가시화: 공정 막대 안에 진행중 (60%) 처럼 수치가 표시되어, 단순한 일정 나열보다 훨씬 전문적인 관리가 가능해집니다.
#사이드바 필터: 공정이 수십 개로 늘어나도 대분류별(인허가, 토목 등)로 필터링하여 보고 싶은 부분만 집중할 수 있습니다. 
#담당자 지정: 각 공정 막대에 마우스를 올리면 어떤 협력사(건화, 청명 등)나 담당자가 맡고 있는지 즉시 나타납니다.

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
st.set_page_config(page_title="현장 공정 관리 PRO", page_icon="🏗️", layout="wide")

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
st.title("🏗️ 당진 적서리 태양광 PMS (Rev. 2026-01-18)")

df_raw, sheet = get_pms_data()
if sheet is None:
    st.warning("데이터베이스 연결 대기 중...")
    st.stop()

# --- 사이드바: 대분류 필터 기능 추가 ---
st.sidebar.header("🔍 공정 필터링")
all_categories = ["전체"] + sorted(df_raw['대분류'].unique().tolist())
selected_cat = st.sidebar.multiselect("조회할 대분류 선택", all_categories, default="전체")

# --- 데이터 전처리 ---
df = df_raw.copy()
df['시작일'] = pd.to_datetime(df['시작일']).dt.normalize()
df['종료일'] = pd.to_datetime(df['종료일']).dt.normalize()

# 진행률/담당자 컬럼 없을 경우 대비 기본값 생성
if '진행률' not in df.columns: df['진행률'] = 0
if '담당자' not in df.columns: df['담당자'] = "미정"

# 필터 적용
if "전체" not in selected_cat:
    df = df[df['대분류'].isin(selected_cat)]

# --- 상단 D-Day 카운터 섹션 ---
st.subheader("🚩 핵심 마일스톤 현황")
ms_only = df_raw[df_raw['대분류'] == 'MILESTONE'].copy()
if not ms_only.empty:
    cols = st.columns(len(ms_only))
    for i, (_, row) in enumerate(ms_only.iterrows()):
        target_date = pd.to_datetime(row['시작일']).date()
        days_left = (target_date - datetime.date.today()).days
        color = "normal" if days_left > 0 else "inverse"
        cols[i].metric(label=row['구분'], value=f"D-{days_left}" if days_left > 0 else f"D+{abs(days_left)}", delta=str(target_date))

tab1, tab2, tab3 = st.tabs(["📊 통합 공정표", "📝 일정 등록", "⚙️ 관리 및 수정"])

# [탭 1] 공정표 조회
with tab1:
    if not df.empty:
        try:
            # 정렬 및 분류
            df = df.sort_values(by="시작일", ascending=False).reset_index(drop=True)
            main_df = df[df['대분류'] != 'MILESTONE'].copy()
            y_order = main_df['구분'].unique().tolist()[::-1]

            # 진행률 텍스트 생성 (예: 진행중 60%)
            main_df['상태표시'] = main_df.apply(lambda x: f"{x['진행상태']} ({x['진행률']}%)", axis=1)

            # 간트 차트 생성
            fig = px.timeline(
                main_df, 
                x_start="시작일", 
                x_end="종료일", 
                y="구분", 
                color="진행상태",
                text="상태표시",
                hover_data={"대분류":True, "담당자":True, "진행률":":.1f%", "비고":True},
                category_orders={"구분": y_order}
            )

            # 오늘 날짜 수직선
            today_dt = datetime.datetime.now()
            fig.add_vline(x=today_dt.timestamp() * 1000, line_width=2, line_dash="dash", line_color="red")

            # 레이아웃 설정
            fig.update_layout(
                plot_bgcolor="white",
                xaxis=dict(side="top", showgrid=True, gridcolor="#E5E5E5", dtick="M1", tickformat="%Y-%m"),
                yaxis=dict(autorange=True, showgrid=True, gridcolor="#F0F0F0", title=""),
                height=800,
                margin=dict(t=100, l=10, r=10, b=50),
                legend_title_text="상태"
            )
            
            fig.update_traces(textposition='inside', selector=dict(type='bar'))
            st.plotly_chart(fig, use_container_width=True)
            
        except Exception as e:
            st.error(f"차트 생성 중 오류: {e}")

# [탭 2] 일정 등록 (컬럼 확장 반영)
with tab2:
    st.subheader("📝 신규 공정 추가")
    with st.form("input_form"):
        c1, c2, c3 = st.columns(3)
        in_start = c1.date_input("시작일", datetime.date.today())
        in_end = c2.date_input("종료일", datetime.date.today() + datetime.timedelta(days=30))
        in_dae = c3.selectbox("대분류", ["인허가", "설계/조사", "계약", "토목공사", "건축공사", "송전선로", "변전설비", "전기공사", "MILESTONE"])
        
        c4, c5, c6 = st.columns(3)
        in_gubun = c4.text_input("공정 구분 (이름)")
        in_status = c5.selectbox("진행상태", ["예정", "진행중", "완료", "지연"])
        in_percent = c6.number_input("진행률 (%)", 0, 100, 0)
        
        in_pic = st.text_input("담당자/협력사 (예: 건화, 김철수 차장)")
        in_note = st.text_area("비고 (특이사항)")
        
        if st.form_submit_button("시트 저장 💾"):
            sheet.append_row([str(in_start), str(in_end), in_dae, in_gubun, in_status, in_note, in_percent, in_pic])
            st.success("✅ 시트에 데이터가 성공적으로 추가되었습니다!"); time.sleep(1); st.rerun()

# [탭 3] 수정 및 삭제 (동일 로직 유지하되 컬럼만 매칭)
with tab3:
    st.info("💡 탭 3은 기존 [Rev. 2026-01-16]의 수정/삭제 로직을 그대로 사용하시되, 시트의 컬럼 순서(A~H)만 맞춰주시면 됩니다.")


