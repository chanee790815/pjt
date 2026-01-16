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

# =========================================================
# 🔐 [보안 설정 완료] 
# 이제 비밀번호는 Streamlit Secrets에서 안전하게 불러옵니다.
# 코드에는 더 이상 개인 키가 노출되지 않습니다.
# =========================================================

# --- 구글 시트 연결 함수 ---
@st.cache_resource
def get_connection():
    try:
        # 1. Secrets에서 정보 가져오기 (없으면 에러 처리)
        if "gcp_service_account" not in st.secrets:
            st.error("🚨 Secrets 설정이 비어있습니다!")
            return None

        # 2. 딕셔너리로 변환
        key_dict = dict(st.secrets["gcp_service_account"])

        # 3. 줄바꿈 문자(\n)가 깨졌을 경우를 대비해 교정
        if "private_key" in key_dict:
            key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")

        # 4. 권한 설정
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
            # 시트 이름 확인: 'pms_db'
            sh = client.open('pms_db') 
            worksheet = sh.sheet1
            data = worksheet.get_all_records()
            return pd.DataFrame(data), worksheet
        except gspread.SpreadsheetNotFound:
            st.error("🚨 구글 시트를 찾을 수 없습니다. (시트 이름 확인 또는 공유 권한 확인 필요)")
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
                df['시작일'] = pd.to_datetime(df['시작일'])
                df['종료일'] = pd.to_datetime(df['종료일'])
                df = df.sort_values(by="시작일")
                
                fig = px.timeline(
                    df, 
                    x_start="시작일", 
                    x_end="종료일", 
                    y="구분", 
                    color="진행상태",
                    hover_data=["대분류", "비고"],
                    title="전체 공정 스케줄"
                )
                fig.update_yaxes(autorange="reversed") 
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
            new_row = [
                input_start.strftime('%Y-%m-%d'), 
                input_end.strftime('%Y-%m-%d'), 
                input_dae, 
                input_gubun, 
                input_status, 
                input_note
            ]
            sheet.append_row(new_row)
            st.success("✅ 일정이 성공적으로 저장되었습니다!")
            time.sleep(1)
            st.rerun()
