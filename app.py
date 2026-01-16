import streamlit as st
import pandas as pd
import datetime
import gspread
from google.oauth2.service_account import Credentials # 최신 라이브러리 사용
import time

# --- 페이지 설정 ---
st.set_page_config(page_title="현장 공정 관리", page_icon="🏗️", layout="wide")

# --- 구글 시트 연결 함수 (수정됨) ---
# @st.cache_resource는 DB 연결을 캐싱하여 속도를 높여줍니다.
@st.cache_resource
def get_connection():
    # 1. Secrets에서 인증 정보 가져오기
    # 스트림릿 클라우드에 설정한 secrets를 가져옵니다.
    credentials_info = st.secrets["gcp_service_account"]

    # 2. Scopes 설정
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
    ]
    
    # 3. 인증 처리 (google-auth 라이브러리 사용)
    creds = Credentials.from_service_account_info(
        credentials_info, scopes=scopes
    )
    client = gspread.authorize(creds)
    return client

def get_pms_data():
    client = get_connection()
    # 시트 열기
    sh = client.open('pms_db') 
    worksheet = sh.sheet1
    
    # 데이터 가져오기
    data = worksheet.get_all_records()
    df = pd.DataFrame(data)
    return df, worksheet

# --- 메인 화면 ---
st.title("🏗️ 당진 적서리 태양광 PMS")

# 로그인/연결 시도
try:
    df, sheet = get_pms_data()
    
    # 탭 구성
    tab1, tab2 = st.tabs(["📅 공정표 보기", "📝 일정 업데이트"])
    
    with tab1:
        st.subheader("전체 예정 공정표")
        
        if not df.empty:
            # 날짜순 정렬 (데이터가 있을 때만)
            if '시작일' in df.columns:
                try:
                    df['시작일'] = pd.to_datetime(df['시작일'])
                    df = df.sort_values(by="시작일")
                    # 보여줄 때는 다시 문자열로 (선택사항)
                    df['시작일'] = df['시작일'].dt.strftime('%Y-%m-%d')
                except:
                    pass # 날짜 변환 실패시 그냥 둠
            
            # 진행상태별 색상 함수
            def color_status(val):
                color = ''
                if val == '완료': color = 'background-color: #d4edda' # 연두색
                elif val == '진행중': color = 'background-color: #fff3cd' # 노란색
                elif val == '지연': color = 'background-color: #f8d7da' # 빨간색
                return color
            
            # 스타일 적용 (Pandas 버전에 따라 applymap 혹은 map 사용)
            try:
                styled_df = df.style.map(color_status, subset=['진행상태'])
            except:
                styled_df = df.style.applymap(color_status, subset=['진행상태'])

            st.dataframe(
                styled_df,
                use_container_width=True,
                height=600,
                hide_index=True
            )
        else:
            st.info("데이터가 비어있습니다.")

    with tab2:
        st.subheader("일정 등록 및 수정")
        st.caption("새로운 일정을 입력하면 구글 시트 맨 아래에 추가됩니다.")
        
        with st.form("input_form"):
            c1, c2 = st.columns(2)
            input_start = c1.date_input("시작일", datetime.date.today())
            input_end = c2.date_input("종료일", datetime.date.today() + datetime.timedelta(days=30))
            
            c3, c4 = st.columns(2)
            input_dae = c3.selectbox("대분류", ["인허가", "설계/조사", "계약", "토목공사", "건축공사", "송전선로", "변전설비", "전기공사", "준공", "MILESTONE"])
            input_gubun = c4.text_input("구분 (세부내용)", placeholder="예: 부지 정지 작업")
            
            c5, c6 = st.columns(2)
            input_status = c5.selectbox("진행상태", ["예정", "진행중", "완료", "지연"])
            input_note = c6.text_input("비고", placeholder="특이사항 입력")
            
            submitted = st.form_submit_button("일정 저장하기 💾", use_container_width=True)
            
            if submitted:
                new_row = [
                    str(input_start), 
                    str(input_end), 
                    input_dae, 
                    input_gubun, 
                    input_status, 
                    input_note
                ]
                sheet.append_row(new_row)
                st.success("✅ 저장이 완료되었습니다! (잠시 후 새로고침 됩니다)")
                time.sleep(1.5)
                st.rerun()

except Exception as e:
    st.error("🚨 연결 오류 발생!")
    st.write("Streamlit Secrets 설정을 확인해주세요.")
    st.expander("에러 상세 내용").write(e)
