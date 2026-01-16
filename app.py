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
# 🔐 [인증 키 구역] 방금 주신 새 열쇠(f5b0...)를 심었습니다!
# =========================================================
raw_json_data = '''
{
  "type": "service_account",
  "project_id": "mp-pms-app",
  "private_key_id": "f5b012b75886d6044e44f29acb307ffd808a9a4a",
  "private_key": "-----BEGIN PRIVATE KEY-----\\nMIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQDkDvzaqIsoTJ76\\nKw9I7s7KyU/qMz1k2H3i6+Foo70NJVcDZUUnUoRxhix7jWqQFhjHgqHWN8UJ4/sf\\n1Wogz3gx3lTUyAEzlpmD772dOZJB1WN2W/W0M66+vrlAzHiUnENAAVXBLD8b+cme\\n+jMph2BMj3/OmIyzEGqztiOqMjZxyLFfriy6idiAX82PvIATF4czPfIjhap+aCn4\\nhqdUZ4qy1oh/N0Rn2kx/MhLIPZUsJ2rbxeG7eert7CMmnxrBKF77kY70u4MoJCYN\\nKWfTvsP4Z3MUclh/2gMh/StbPdMJxg+01LSdk2fhMN3YD5MJAH6kRa3GBoTRE2wh\\naNkDeiBzAgMBAAECggEARPKpDFxXUfQ0PhLlmJmmSFWrhPU/0uzGxmOk7rNOFRrc\\nXyjvSs+ePgogCax78prTnAHI9tA+kFpuEjY90zSWNJFwmTHsdxHJUMOa0l1U8/VV\\nEDQGKRhU9NMJg+ctb1R82m1s5S2A2O7gP2GKNTx55zudGrMxGnPUpodi6fIrVqOR\\nmRfzqRc3bT8YDr2s2hv5Ne5F+iyEHJHTPB5f/2opUmQ2v9On9N4Vm06n/Fm+Mo5e\\nrJ/quLNx4gcpIeieIwJox02CKonsBuX8tpsgCWP/4Zf3hip2alWx4Ed3BdHI54gg\\nihp8t5yfOk/C1WuHtsCuhxhsV28xbdGwTQSpjyu1wQKBgQD59GQYSk2bXGHfHf61\\nJLKlhXXEfwt4l4qZTB0PSWYymNR5/yIhwtF00EIKYHWQD2rCWA6pu11yaUSy5Msu\\nlxCweqcyUQJh+wbO/RgMoalCyvPQzWw7OJ3Q1IYdUQAsdTZS35l15yBPPE47vMoR\\nKP99L7I8URmOnpkwn5STmJ1CswKBgQDpkwaS0CiXz4EuI1FHYK2RbKtcP1Ksh23d\\nFgDzDRcAlYINNS8JiI0BqC1EA5LVCaizGLG0JTd5N1tQvkFbwcqTL9rozOL9uYjE\\nGPc0DYZoH59NuV0m861MuAdfbCX1Rl9tUTqdOzC02N1SLz3r2FzhLtGjAjXukUYG\\nk2HTtNeLQQKBgQCw2kxgK2KRxGGzXiOzw01rc+yJpWJWZtK3+HSvNj3LGvtrfiuG\\nO7O7tQalFO7ZiS7+ZxOo4FsT8oubD+r7AgPa+k2Gem73KIf+uHDlrxR1n+e3G0Gy\\n/TIcaeKip4c57Y0MQgzwsSHZLlAkUEWgsqNizfaMWs18bZbyIlcbv2W1pQKBgQC7\\nDpEUIHpx4a+dyJD+LdGzBilSDjBilW8JwOZvv8rtH87wTuhlpSLv8cSWlJoR3NNq\\n4trl32xGumt6BXQITPGz4H5bNEKRWfXKvgezeyVp2/FTaKDOYhYmu7bD17Oqc3pW\\n7NeZNd7y5j6Q496eMz9m43zmJA4XCebfu0Z8Knb4QQKBgG+DpJ7ULG910h1yedVJ\\numdWoVCOMvYdr/VrgdEVDSSnK925goABy4wHXzsh8ol8CzMqhmwzMpfeYzNGwTJO\\nmIfCh0vhegb1o97hrwNPl2k3RSqqMDtdcYpGHRDOgYOpmgTl/qNxKrvQIPF8rGCE\\nJNSMtvkVFuUpuDl9kRw8s+WQ\\n-----END PRIVATE KEY-----\\n",
  "client_email": "streamlit-bot@mp-pms-app.iam.gserviceaccount.com",
  "client_id": "100863669822809695078",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/streamlit-bot%40mp-pms-app.iam.gserviceaccount.com",
  "universe_domain": "googleapis.com"
}
'''
# =========================================================

# --- 구글 시트 연결 함수 ---
@st.cache_resource
def get_connection():
    try:
        # JSON 문자열을 파이썬 딕셔너리로 변환
        key_dict = json.loads(raw_json_data)
        
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = Credentials.from_service_account_info(key_dict, scopes=scopes)
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        return None

def get_pms_data():
    client = get_connection()
    if client:
        try:
            # ⚠️ 시트 이름이 'pms_db'가 맞는지 확인 필요
            sh = client.open('pms_db') 
            worksheet = sh.sheet1
            data = worksheet.get_all_records()
            return pd.DataFrame(data), worksheet
        except gspread.SpreadsheetNotFound:
            st.error("🚨 구글 시트를 찾을 수 없습니다. 시트 이름이 'pms_db'인지 확인해주세요.")
            return pd.DataFrame(), None
        except Exception as e:
             st.error(f"🚨 데이터 읽기 오류: {e}")
             return pd.DataFrame(), None
    return pd.DataFrame(), None

# --- 메인 화면 ---
# ✅ 제목이 '(Final Ver.)'로 바뀌면 새 코드가 적용된 것입니다!
st.title("🏗️ 당진 적서리 태양광 PMS (Final Ver.)")

# 데이터 로딩
df, sheet = get_pms_data()

if sheet is None:
    st.error("🚨 데이터베이스 연결에 실패했습니다.")
    st.stop()

# 탭 구성
tab1, tab2 = st.tabs(["📊 공정표 (Gantt)", "📝 일정 업데이트"])

# [탭 1] 간트 차트 및 조회
with tab1:
    st.subheader("실시간 공정 현황")
    
    if not df.empty:
        # 날짜 변환 및 정렬
        if '시작일' in df.columns and '종료일' in df.columns:
            try:
                df['시작일'] = pd.to_datetime(df['시작일'])
                df['종료일'] = pd.to_datetime(df['종료일'])
                df = df.sort_values(by="시작일")
                
                # 간트 차트 그리기
                fig = px.timeline(
                    df, 
                    x_start="시작일", 
                    x_end="종료일", 
                    y="구분", 
                    color="진행상태",
                    hover_data=["대분류", "비고"],
                    title="전체 공정 스케줄"
                )
                fig.update_yaxes(autorange="reversed") # 위에서부터 순서대로
                st.plotly_chart(fig, use_container_width=True)
                
            except Exception as e:
                st.warning(f"차트 생성 중 오류: {e}")

        # 데이터 테이블 스타일링
        st.divider()
        st.write("📋 상세 데이터 목록")
        
        def color_status(val):
            if val == '완료': return 'background-color: #d4edda'
            elif val == '진행중': return 'background-color: #fff3cd'
            elif val == '지연': return 'background-color: #f8d7da'
            return ''
            
        try:
            # 날짜를 다시 보기 좋게 문자열로
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
            # 날짜를 문자열로 변환해서 저장
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
