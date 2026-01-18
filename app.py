## [PMS Revision History]
## 수정 일자: 2026-01-18
## 버전: Rev. 2026-01-18.12
## 업데이트 요약:
## 1. 차트 확대/축소(Zoom) 원천 차단:
##    - 터치 실수로 날짜가 '일/시간' 단위로 쪼개지는 현상 방지
##    - X축 눈금 간격(dtick)을 "M1"(1개월)로 강제 고정하여 항상 '26-01' 형태 유지
## 2. 스크롤 안전장치 강화:
##    - 이동(Pan)만 가능하도록 dragmode를 'pan'으로 고정
##    - 프로젝트 기간 앞뒤 30일까지만 이동 가능하도록 '가드레일(min/max allowed)' 타이트하게 설정
## 3. 기존 기능 통합: 엑셀식 틀 고정, 모바일 축소 모드, D-Day, 최신순 정렬 등

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

# --- 메인 화면 상단 ---
st.title("🏗️ 당진 적서리 태양광 PMS (Rev. 2026-01-18.12)")

df_raw, worksheet = get_pms_data()
if worksheet is None:
    st.warning("데이터베이스 연결 대기 중...")
    st.stop()

# --- 사이드바 설정 ---
st.sidebar.header("⚙️ 화면 설정")
is_mobile_mode = st.sidebar.toggle("📱 모바일 공정명 축소 (5글자)", value=False)

st.sidebar.divider()
st.sidebar.header("🔍 공정 필터링")
all_categories = ["전체"] + sorted(df_raw['대분류'].unique().tolist())
selected_cat = st.sidebar.multiselect("조회할 대분류 선택", all_categories, default="전체")

# --- 데이터 전처리 ---
df = df_raw.copy()
df['시작일'] = pd.to_datetime(df['시작일']).dt.normalize()
df['종료일'] = pd.to_datetime(df['종료일']).dt.normalize()

if '진행률' not in df.columns: df['진행률'] = 0
if '담당자' not in df.columns: df['담당자'] = "미정"

if "전체" not in selected_cat:
    df = df[df['대분류'].isin(selected_cat)]

# [안전장치] 이동 범위 제한 (프로젝트 기간 + 30일 여유)
if not df.empty:
    min_date = df['시작일'].min()
    max_date = df['종료일'].max()
    limit_min = min_date - datetime.timedelta(days=30)
    limit_max = max_date + datetime.timedelta(days=30)
else:
    limit_min = datetime.datetime.now()
    limit_max = datetime.datetime.now()

# --- D-Day 카운터 ---
st.subheader("🚩 핵심 마일스톤 현황")
ms_only = df_raw[df_raw['대분류'] == 'MILESTONE'].copy()
if not ms_only.empty:
    ms_cols = st.columns(len(ms_only))
    for i, (_, row) in enumerate(ms_only.iterrows()):
        target_date = pd.to_datetime(row['시작일']).date()
        days_left = (target_date - datetime.date.today()).days
        ms_cols[i].metric(
            label=row['구분'], 
            value=f"D-{days_left}" if days_left > 0 else f"D+ {abs(days_left)}", 
            delta=str(target_date)
        )

# --- 탭 구성 ---
tab1, tab2, tab3 = st.tabs(["📊 통합 공정표", "📝 일정 등록", "⚙️ 관리 및 수정"])

# [탭 1] 공정표 조회
with tab1:
    view_option = st.radio(
        "👁️ 보기 모드 선택", 
        ["🪟 엑셀식 틀 고정 (추천)", "📄 전체 길게 보기 (스크롤)"], 
        horizontal=True,
        label_visibility="collapsed"
    )
    
    st.caption(f"현재 모드: **{view_option}** - {'상하좌우 드래그로 이동 (확대/축소 잠금됨)' if '틀 고정' in view_option else '브라우저 스크롤 사용'}")

    if not df.empty:
        try:
            df_sorted = df.sort_values(by="시작일", ascending=False).reset_index(drop=True)
            main_df = df_sorted[df_sorted['대분류'] != 'MILESTONE'].copy()
            y_order = main_df['구분'].unique().tolist()[::-1]
            
            if is_mobile_mode:
                y_labels_display = [ (label[:5] + '..') if len(label) > 5 else label for label in y_order ]
                font_size_axis = 11
            else:
                y_labels_display = y_order
                font_size_axis = 12

            main_df['상태표시'] = main_df.apply(lambda x: f"{x['진행상태']} ({x['진행률']}%)", axis=1)

            fig = px.timeline(
                main_df, x_start="시작일", x_end="종료일", y="구분", color="진행상태",
                text="상태표시", 
                hover_data={"구분":True, "대분류":True, "담당자":True, "진행률":True, "비고":True},
                category_orders={"구분": y_order}
            )

            today_dt = datetime.datetime.now()
            fig.add_vline(x=today_dt.timestamp() * 1000, line_width=2, line_dash="dash", line_color="red")

            if "틀 고정" in view_option:
                final_height = 500
                if len(y_order) > 12:
                    range_y = [len(y_order) - 12.5, len(y_order) - 0.5]
                else:
                    range_y = None
            else:
                final_height = max(500, len(main_df) * 40)
                range_y = None

            fig.update_layout(
                plot_bgcolor="white",
                xaxis=dict(
                    side="top", showgrid=True, gridcolor="#E5E5E5", 
                    # [핵심] 줌 잠금 장치
                    dtick="M1",              # 1개월 단위 강제 고정 (확대해도 쪼개지지 않음)
                    tickformat="%y-%m",      # 날짜 형식 고정
                    ticks="outside", 
                    tickfont=dict(size=10),
                    fixedrange=False,        # 이동(Pan)은 허용
                    range=[limit_min, limit_max], # 초기 범위
                    minallowed=limit_min,    # 좌측 이동 한계
                    maxallowed=limit_max     # 우측 이동 한계
                ),
                yaxis=dict(
                    autorange=True if range_y is None else False,
                    range=range_y,
                    showgrid=True, gridcolor="#F0F0F0", 
                    title="", 
                    tickfont=dict(size=font_size_axis),
                    automargin=True,
                    tickmode='array',
                    tickvals=y_order,
                    ticktext=y_labels_display,
                    fixedrange=False # 이동 허용
                ),
                height=final_height,
                margin=dict(t=80, l=10, r=10, b=20),
                legend=dict(orientation="h", yanchor="bottom", y=-0.1, xanchor="center", x=0.5),
                dragmode="pan" # 기본 동작을 '이동'으로 고정
            )
            fig.update_yaxes(ticksuffix=" ")
            fig.update_traces(textposition='inside', textfont_size=10, selector=dict(type='bar'))
            
            st.plotly_chart(
                fig, 
                use_container_width=True, 
                config={
                    'responsive': True, 
                    'scrollZoom': False,        # 휠/핀치 줌 비활성화
                    'doubleClick': 'reset',     # 더블클릭 시 초기 상태로 복구
                    'displayModeBar': False     # 메뉴바 숨김
                }
            )
            
        except Exception as e:
            st.error(f"차트 생성 중 오류: {e}")

# [탭 2] 일정 등록
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
        in_pic = st.text_input("담당자/협력사")
        in_note = st.text_area("비고")
        if st.form_submit_button("시트 저장 💾"):
            sheet_data = [str(in_start), str(in_end), in_dae, in_gubun, in_status, in_note, in_percent, in_pic]
            worksheet.append_row(sheet_data)
            st.success("✅ 저장이 완료되었습니다!"); time.sleep(1); st.rerun()

# [탭 3] 관리 및 수정
with tab3:
    st.subheader("⚙️ 기존 공정 수정 및 삭제")
    df_manage, _ = get_pms_data()
    if not df_manage.empty:
        df_manage['selection'] = df_manage['구분'].astype(str) + " (" + df_manage['시작일'].astype(str) + ")"
        target_item = st.selectbox("항목 선택", df_manage['selection'].tolist())
        selected_idx = df_manage[df_manage['selection'] == target_item].index[0]
        row_data = df_manage.iloc[selected_idx]
        with st.form("edit_form"):
            st.info(f"📍 선택된 공정: {row_data['구분']}")
            e_c1, e_c2, e_c3 = st.columns(3)
            up_start = e_c1.date_input("시작일 수정", pd.to_datetime(row_data['시작일']).date())
            up_end = e_c2.date_input("종료일 수정", pd.to_datetime(row_data['종료일']).date())
            dae_list = ["인허가", "설계/조사", "계약", "토목공사", "건축공사", "송전선로", "변전설비", "전기공사", "MILESTONE"]
            try: dae_idx = dae_list.index(row_data['대분류'])
            except: dae_idx = 0
            up_dae = e_c3.selectbox("대분류 수정", dae_list, index=dae_idx)
            e_c4, e_c5, e_c6 = st.columns(3)
            up_gubun = e_c4.text_input("공정명 수정", value=row_data['구분'])
            status_list = ["예정", "진행중", "완료", "지연"]
            try: status_idx = status_list.index(row_data['진행상태'])
            except: status_idx = 0
            up_status = e_c5.selectbox("진행상태 수정", status_list, index=status_idx)
            raw_percent = row_data.get('진행률', 0)
            try: default_percent = int(raw_percent) if str(raw_percent).isdigit() else 0
            except: default_percent = 0
            up_percent = e_c6.number_input("진행률 수정 (%)", 0, 100, default_percent)
            up_pic = st.text_input("담당자/협력사 수정", value=row_data.get('담당자', ""))
            up_note = st.text_area("비고 수정", value=row_data['비고'])
            edit_col, del_col = st.columns(2)
            if edit_col.form_submit_button("내용 업데이트 🆙", use_container_width=True):
                update_values = [str(up_start), str(up_end), up_dae, up_gubun, up_status, up_note, up_percent, up_pic]
                worksheet.update(f"A{selected_idx + 2}:H{selected_idx + 2}", [update_values])
                st.success("✅ 업데이트 완료!"); time.sleep(1); st.rerun()
            if del_col.form_submit_button("항목 삭제하기 🗑️", use_container_width=True):
                worksheet.delete_rows(selected_idx + 2)
                st.error("🗑️ 삭제 완료!"); time.sleep(1); st.rerun()
        st.divider()
        st.subheader("📋 실시간 데이터 명단 (전체)")
        df_display = df_manage.copy()
        df_display['시작일'] = pd.to_datetime(df_display['시작일']).dt.strftime('%Y-%m-%d')
        df_display['종료일'] = pd.to_datetime(df_display['종료일']).dt.strftime('%Y-%m-%d')
        st.dataframe(df_display.sort_values(by="시작일"), use_container_width=True, hide_index=True)
