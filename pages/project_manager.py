import streamlit as st
import pandas as pd
import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import time

# --- 페이지 설정 ---
st.set_page_config(page_title="현장 공정 관리", page_icon="🏗️", layout="wide")

# ==========================================
# 🔐 [비밀 열쇠 구역]
# 1. 컴퓨터에 다운받은 JSON 파일을 메모장으로 여세요.
# 2. 내용 전체(괄호 포함)를 복사하세요.
# 3. 아래 'google_key =' 뒤에 있는 { ... } 부분을 다 지우고 붙여넣으세요!
# ==========================================

google_key = {
  "type": "service_account",
  "project_id": "mp-pms-app",
  "private_key_id": "7ba1030c03350897938cce36b9f44d1c466607ee",
  "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQCaFu8wLRq0awDn\nlxRZ5ZFulKBbIWPaydx6NBcRB9sZ8W2dHu8g2vS/AwnvRQVwDMrEPBQ6POZ4aX6F\nJT8/bzHLlGajmZDkVLdaRjl5aOez7g5lHXSGD0VHjsPxQwgwZ6hOI9y3+Fqmog8m\n6idlvThZDpC5/c1WzWZd1MJGhDrQW7uDmcERZe1xqqE8XAz3eoWcuBEn8klPtUgh\ndaHPbJDLLu5tRcuBDNGIHBGlV8s8KrKD2oymvsrHA6wlS9R8XOkv3v22uaDvp64F\nzDR60GVGNv7LApRxslbiZ0kjILKfvbAEjF/jeopuDnkURSgdx3lyeaTM4SppdtdR\nbjiIFV1hAgMBAAECggEABMyPT0WuWd1lyjC2Q2z/FC24l1IBR0aHcX5nFAKVwDd4\n2Z6FpdUv73WHpQ42IsThOU6iNiSgrHIjrL+p2j7LMxsYfcKqBLR/P+ZlQprh8YSJ\n6fwKfaTi3F1NzLkw23oU/7cF+CxZ3Wv5cxWym6xyoXJuzz4ge7I6vJQkZ1gVsVjH\nqAW/bG6GgCWab/5mLIYXCNY6yb9PTWYENH2EBkexOvayuyPYh1EXbpmKQ5Xm8R/B\narpH6ZGnk3tmpIwoWVWRTjyviPw7k7FxeNa8mIOfafgbCDpDi9HKQcaCFWQngoA5\nS4x2ktAf4yKGrN+korctLxHuS7eYr+NE4W0k3i43AQKBgQDSr69cNKPwFy8f+LFv\nF8phf60mgQCFGhqtrPZfin/5LeJXvyOXhWSoUECLJYfgwQbS5HxarBmHIG9GjFPH\nMhK+mxwnuOWsEUlwWuvBNJKq1BSkrb5IYVrDNITCIutbdgFxXki99uu5TXNOts8g\ndIMOIPfGhTiVy0OSbxAZAlvIoQKBgQC7Ow4ZRg4c8BzFJucggmuLTA7eDNo2YQ2+\nFufDmptJaRoE/hx5qlZvBblVealQbeowvZ3cNb3oL5rjLor63rhk1RJhpF6B8fpy\nn1vfbynnthghScUR97+uswJy8jGvMGqC8DruiY9nOUsnrl1eLCLlutCyUSQt5m6/\naWljygGcwQKBgQCHEls6ogT4R+TOeoJG1tnI6DH6HXpX2wR/lAPf/MtO1TvnRYNs\nAPknb0vx6X3Tee0GB7Yx62PyXbj5Yb3UVyXtTUQfs0qLpgmPHrtGgo4FNzKE4V68\nyK2HuIPkcr6xRFZoeCnqoANAKYdjT5A7Hndm93viqkY8wrPvjYSkg/6UAQKBgFGI\n+i7Pbz3y4tSIiIaDxUm4KZFRj4W25kEtwGhSX+WsO4SJFOV25IUcvQUYIj/AXggz\nyxcm4DjI4m6kyilN7IccsxCKgA2ezy4zb9LxmhIqHoAAnC2i8nqlwh9EkZZ1Qy0a\naM+QYD7XmH8DU+260sewf0noRBUpEHmS8i5evi0BAoGAU224At3323dxMYebe+93\nMeXQa0YQs2Vsf+AOPDzEUPqAWjUWeXlT8WU6FR4ADYubNRl2AAzZV7Jsc/glci1t\njJpYtxyOC0zuIlN0gdbGSu0JSPPp66JdDV1qt9vaLovoBrdrvRfzSwsEltmI0uZS\nYI7Y0HZQ/TG6dQGCdjNbuhg=\n-----END PRIVATE KEY-----\n",
  "client_email": "streamlit-bot@mp-pms-app.iam.gserviceaccount.com",
  "client_id": "100863669822809695078",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/streamlit-bot%40mp-pms-app.iam.gserviceaccount.com",
  "universe_domain": "googleapis.com"
}


# ==========================================

# --- 구글 시트 연결 함수 ---
def get_pms_data():
    # 1. 인증 설정
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_dict(google_key, scope)
    client = gspread.authorize(creds)
    
    # 2. 시트 열기 (이름이 'pms_db'가 맞는지 확인)
    sh = client.open('pms_db') 
    worksheet = sh.sheet1
    
    # 3. 데이터 가져오기
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
                df = df.sort_values(by="시작일")
            
            # 진행상태별 색상 (진행중=노랑, 완료=초록, 지연=빨강)
            def color_status(val):
                color = ''
                if val == '완료': color = 'background-color: #d4edda'
                elif val == '진행중': color = 'background-color: #fff3cd'
                elif val == '지연': color = 'background-color: #f8d7da'
                return color
            
            # 데이터프레임 표시 (높이 조절)
            st.dataframe(
                df.style.applymap(color_status, subset=['진행상태']),
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
            # 날짜 입력
            input_start = c1.date_input("시작일", datetime.date.today())
            input_end = c2.date_input("종료일", datetime.date.today() + datetime.timedelta(days=30))
            
            # 내용 입력
            c3, c4 = st.columns(2)
            input_dae = c3.selectbox("대분류", ["인허가", "설계/조사", "계약", "토목공사", "건축공사", "송전선로", "변전설비", "전기공사", "준공", "MILESTONE"])
            input_gubun = c4.text_input("구분 (세부내용)", placeholder="예: 부지 정지 작업")
            
            # 상태 입력
            c5, c6 = st.columns(2)
            input_status = c5.selectbox("진행상태", ["예정", "진행중", "완료", "지연"])
            input_note = c6.text_input("비고", placeholder="특이사항 입력")
            
            submitted = st.form_submit_button("일정 저장하기 💾", use_container_width=True)
            
            if submitted:
                # 구글 시트에 행 추가
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
    st.write(f"에러 내용: {e}")
    st.warning("팁: requirements.txt에 gspread가 있는지, JSON 키를 제대로 붙여넣었는지 확인해보세요.")
