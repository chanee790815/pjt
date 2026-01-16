import streamlit as st
import pandas as pd
import datetime
import gspread
from google.oauth2.service_account import Credentials
import time

# --- 페이지 설정 ---
st.set_page_config(page_title="현장 공정 관리", page_icon="🏗️", layout="wide")

# ==========================================
# 🚨 [비상용] 인증 키 직접 입력
# ==========================================
secrets_dict = {
  "type": "service_account",
  "project_id": "mp-pms-app",
  "private_key_id": "7ba1030c03350897938cce36b9f44d1c466607ee",
  "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQCaFu8wLRq0awDn\nlxRZ5ZFulKBbIWPaydx6NBcRB9sZ8W2dHu8g2vS/AwnvRQVwDMrEPBQ6POZ4aX6F\nJT8/bzHLlGajmZDkVLdaRjl5aOez7g5lHXSGD0VHjsPxQwgwZ6hOI9y3+Fqmog8m\n6idlvThZDpC5/c1WzWZd1MJGhDrQW7uDmcERZe1xqqE8XAz3eoWcuBEn8klPtUgh\ndaHPbJDLLu5tRcuBDNGIHBGlV8s8KrKD2oymvsrHA6wlS9R8XOkv3v22uaDvp64F\nzDR60GVGNv7LApRxslbiZ0kjILKfvbAEjF/jeopuDnkURSgdx3lyeaTM4SppdtdR\nbjiIFV1hAgMBAAECggEABMyPT0WuWd1lyjC2Q2z/FC24l1IBR0aHcX5nFAKVwDd4\n2Z6FpdUv73WHpQ42IsThOU6iNiSgrHIjrL+p2j7LMxsYfcKqBLR/P+ZlQprh8YSJ\n6fwKfaTi3F1NzLkw23oU/7cF+CxZ3Wv5cxWym6xyoXJuzz4ge7I6vJQkZ1gVsVjH\nqAW/bG6GgCWab/5mLIYXCNY6yb9PTWYENH2EBkexOvayuyPYh1EXbpmKQ5Xm8R/B\narpH6ZGnk3tmpIwoWVWRTjyviPw7k7FxeNa8mIOfafgbCDpDi9HKQcaCFWQngoA5\nS4x2ktAf4yKGrN+korctLxHuS7eYr+NE4W0k3i43AQKBgQDSr69cNKPwFy8f+LFv\nF8phf60mgQCFGhqtrPZfin/5LeJXvyOXhWSoUECLJYfgwQbS5HxarBmHIG9GjFPH\nMhK+mxwnuOWsEUlwWuvBNJKq1BSkrb5IYVrDNITCIutbdgFxXki99uu5TXNOts8g\ndIMOIPfGhTiVy0OSbxAZAlvIoQKBgQC7Ow4ZRg4c8BzFJucggmuLTA7eDNo2YQ2+\nFufDmptJaRoE/hx5qlZvBblVealQbeowvZ3cNb3oL5rjLor63rhk1RJhpF6B8fpy\nn1vfbynnthghScUR97+uswJy8jGvMGqC8DruiY9nOUsnrl1eLCLlutCyUSQt5m6/\naWljygGcwQKBgQCHEls6ogT4R+TOeoJG1tnI6DH6HXpX2wR/lAPf/MtO1TvnRYNs\nAPknb0vx6X3Tee0GB7Yx62PyXbj5Yb3UVyXtTUQfs0qLpgmPHrtGgo4FNzKE4V68\nyK2HuIPkcr6xRFZoeCnqoANAKYdjT5A7Hndm93viqkY8wrPvjYSkg/6UAQKBgFGI\n+i7Pbz3y4tSIiIaDxUm4KZFRj4W25kEtwGhSX+WsO4SJFOV25IUcvQUYIj/AXggz\nyxcm4DjI4m6kyilN7IccsxCKgA2ezy4zb9LxmhIqHoAAnC2i8nqlwh9EkZZ1Qy0a\naM+QYD7XmH8DU+260sewf0noRBUpEHmS8i5evi0BAoGAU224At3323dxMYebe+93\nMeXQa0YQs2Vsf+AOPDzEUPqAWjUWeXlT8WU6FR4ADYubNRl2AAzZV7Jsc/glci1t\njJpYtxyOC0zuIlN0gdbGSu0JSPPp66JdDV1qt9vaLovoBrdrvRfzSwsEltmI0uZS\nYI7Y0HZQ/TG6dQGCdjNbuhg=\n-----END PRIVATE KEY-----\n",
  "client_email": "streamlit-bot@mp-pms-app.iam.gserviceaccount.com",
  "client_id": "100863669822809695078",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/streamlit-bot%40mp-pms-app.iam.gserviceaccount.com"
}
# ==========================================

# --- 구글 시트 연결 함수 ---
@st.cache_resource
def get_connection():
    # ✅ [핵심 수정] 줄바꿈 문자(\n)가 깨진 것을 강제로 고침
    # 이 부분이 없으면 'Invalid JWT Signature' 에러가 납니다.
    if "\\n" in secrets_dict["private_key"]:
        secrets_dict["private_key"] = secrets_dict["private_key"].replace("\\n", "\n")
        
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(secrets_dict, scopes=scopes)
    client = gspread.authorize(creds)
    return client

def get_pms_data():
    client = get_connection()
    # ⚠️ 구글 시트 이름 확인!
    sh = client.open('pms_db') 
    worksheet = sh.sheet1
    data = worksheet.get_all_records()
    return pd.DataFrame(data), worksheet

# --- 메인 화면 ---
st.title("🏗️ 당진 적서리 태양광 PMS (Direct Key)")

try:
    df, sheet = get_pms_data()
    
    tab1, tab2 = st.tabs(["📅 공정표 보기", "📝 일정 업데이트"])
    
    with tab1:
        st.subheader("전체 예정 공정표")
        if not df.empty:
            if '시작일' in df.columns:
                try:
                    df['시작일'] = pd.to_datetime(df['시작일'])
                    df = df.sort_values(by="시작일")
                    df['시작일'] = df['시작일'].dt.strftime('%Y-%m-%d')
                except: pass
            
            def color_status(val):
                if val == '완료': return 'background-color: #d4edda'
                elif val == '진행중': return 'background-color: #fff3cd'
                elif val == '지연': return 'background-color: #f8d7da'
                return ''
            
            try:
                st.dataframe(df.style.map(color_status, subset=['진행상태']), use_container_width=True, height=600, hide_index=True)
            except:
                st.dataframe(df, use_container_width=True) 
        else:
            st.info("데이터가 없습니다.")

    with tab2:
        st.subheader("일정 등록")
        with st.form("input_form"):
            c1, c2 = st.columns(2)
            input_start = c1.date_input("시작일", datetime.date.today())
            input_end = c2.date_input("종료일", datetime.date.today() + datetime.timedelta(days=30))
            c3, c4 = st.columns(2)
            input_dae = c3.selectbox("대분류", ["인허가", "설계/조사", "계약", "토목공사", "건축공사", "송전선로", "변전설비", "전기공사", "준공", "MILESTONE"])
            input_gubun = c4.text_input("구분", placeholder="작업 내용")
            c5, c6 = st.columns(2)
            input_status = c5.selectbox("진행상태", ["예정", "진행중", "완료", "지연"])
            input_note = c6.text_input("비고")
            
            if st.form_submit_button("저장 💾", use_container_width=True):
                sheet.append_row([str(input_start), str(input_end), input_dae, input_gubun, input_status, input_note])
                st.success("저장 완료!")
                time.sleep(1)
                st.rerun()

except Exception as e:
    st.error("🚨 오류 발생!")
    st.write(f"에러 상세: {e}")
    st.warning("⚠️ 만약 여전히 'Invalid JWT' 에러가 난다면, 사용 중인 키 파일이 '삭제(폐기)'되었을 수 있습니다. 구글 클라우드에서 새 키를 받으세요.")
