import streamlit as st
import pandas as pd
import datetime
import gspread
from google.oauth2.service_account import Credentials
import time
import json
import plotly.express as px

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

        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        
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
        except gspread.SpreadsheetNotFound:
            st.error("🚨 구글 시트를 찾을 수 없습니다.")
            return pd.DataFrame(), None
        except Exception as e:
             st.error(f"🚨 데이터 읽기 오류: {e}")
             return pd.DataFrame(), None
    return pd.DataFrame(), None

# --- 메인 화면 ---
st.title("🏗️ 당진 적서리 태양광 PMS (Secure Ver.)")

# 데이터 로딩
df, sheet = get_pms_data()

if sheet is None:
    st.warning("데이터베이스 연결 대기 중...")
    st.stop()

# 탭 구성
tab1, tab2 = st.tabs(["📊 공정표 (Gantt)", "📝 일정 업데이트"])

# [탭 1] 간트 차트 및 조회
with tab1:
    st.subheader("실시간 공정 현황")
    
    if not df.empty:
        if '시작일' in df.columns and '종료일' in df.columns:
            try:
                # 데이터 전처리
                df['시작일'] = pd.to_datetime(df['시작일'])
                df['종료일'] = pd.to_datetime(df['종료일'])
                
                # [개선 1] 구분이 비어있는 경우(직접 업데이트 항목 등) 이름 부여
                df['구분'] = df['구분'].astype(str).replace('', '인허가 보완/진행')
                df['구분'] = df['구분'].fillna('인허가 보완/진행')
                
                df = df.sort_values(by="시작일")
                
                # 간트 차트 생성
                fig = px.timeline(
                    df, 
                    x_start="시작일", 
                    x_end="종료일", 
                    y="구분", 
                    color="진행상태",
                    hover_data=["대분류", "비고"],
                    title="전체 공정 스케줄"
                )

                # [개선 2] 차트 레이아웃 수정 (상단 년월, 격자선 추가)
                fig.update_layout(
                    plot_bgcolor="white",          # 배경을 흰색으로 변경
                    xaxis=dict(
                        side="top",                # 년월 표시를 상단으로 이동
                        showgrid=True,             # 가로 격자선(월별 구분선) 활성화
                        gridcolor="rgba(220, 220, 220, 0.8)", # 연한 실선 색상
                        dtick="M1",                # 1개월 단위 눈금
                        tickformat="%Y-%m",        # 표시 형식
                        ticks="outside"
                    ),
                    yaxis=dict(
                        autorange="reversed",      # 상단부터 시간순 배치
                        showgrid=True,             # 세로 격자선(항목 구분선) 활성화
                        gridcolor="LightGray"
                    ),
                    height=600,                    # 차트 높이 조절
                    margin=dict(t=100, l=10, r=10, b=10) # 상단 축 공간 확보
                )
                
                # 막대 테두리 및 두께 조절 (표 느낌 강조)
                fig.update_traces(marker_line_color="rgb(8,48,107)", marker_line_width=1, opacity=0.9)
                
                st.plotly_chart(fig, use_container_width=True)
                
            except Exception as e:
                st.warning(f"차트 생성 중 오류: {e}")

        st.divider()
        st.write("📋 상세 데이터 목록")
        
        def color_status(val):
            if val == '완료': return 'background-color: #d4edda'
            elif val == '진행중': return 'background-color: #fff3cd'
            elif val == '지연': return 'background-color: #f8d7da'
            return ''
            
        try:
            display_df = df.copy()
            if '시작일' in display_df.columns:
                display_df['시작일'] = display_df['시작일'].dt.strftime('%Y-%m-%d')
                display_df['종료일'] = display_df['종료일'].dt.strftime('%Y-%m-%d')
            
            st.dataframe(
                display_df.style.map(color_status, subset=['진행상태']),
                use_container_width=True,
                height=500,
                hide_index=True
            )
        except:
            st.dataframe(df, use_container_width=True)
    else:
        st.info("💡 데이터가 없습니다. 옆 탭에서 일정을 등록해주세요.")

# [탭 2] 일정 입력
with tab2:
    st.subheader("일정 등록")
    with st.form("input_form"):
        c1, c2 = st.columns(2)
        input_start = c1.date_input("시작일", datetime.date.today())
        input_end = c2.date_input("종료일", datetime.date.today() + datetime.timedelta(days=30))
        
        c3, c4 = st.columns(2)
        input_dae = c3.selectbox("대분류", ["인허가", "설계/조사", "계약", "토목공사", "건축공사", "송전선로", "변전설비", "전기공사", "준공", "MILESTONE"])
        input_gubun = c4.text_input("구분", placeholder="예: 부지 정지 작업")
        
        c5, c6 = st.columns(2)
        input_status = c5.selectbox("진행상태", ["예정", "진행중", "완료", "지연"])
        input_note = c6.text_input("비고")
        
        submitted = st.form_submit_button("저장하기 💾", use_container_width=True)
        
        if submitted:
            # 입력값이 비어있을 경우에 대한 기본값 처리 (차트 오류 방지)
            save_gubun = input_gubun if input_gubun.strip() != "" else "인허가 보완/진행"
            
            new_row = [
                input_start.strftime('%Y-%m-%d'), 
                input_end.strftime('%Y-%m-%d'), 
                input_dae, 
                save_gubun, 
                input_status, 
                input_note
            ]
            sheet.append_row(new_row)
            st.success("✅ 일정이 성공적으로 저장되었습니다!")
            time.sleep(1)
            st.rerun()
