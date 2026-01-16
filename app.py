import streamlit as st
import yfinance as yf
import pandas as pd
import requests
from bs4 import BeautifulSoup
import time

# --- 페이지 설정 ---
st.set_page_config(page_title="Gold Spread & Macro", page_icon="💰", layout="centered")

# --- 함수: 데이터 가져오기 ---
def get_financial_data():
    # 1. 국제 금 시세 (GC=F) & 환율 (KRW=X) & 거시지표
    tickers = {
        'Gold_Intl': 'GC=F',       # 금 선물 (달러/트로이온스)
        'USD_KRW': 'KRW=X',        # 원달러 환율
        'SP500': '^GSPC',          # S&P 500
        'Trans_Avg': '^DJT',       # 다우 운송 지수 (물동량/경기 대리 지표)
        'US_10Y': '^TNX'           # 미국 10년물 국채 금리
    }
    
    data = yf.download(list(tickers.values()), period='1d', progress=False)['Close'].iloc[-1]
    
    # yfinance 데이터 정리 (Ticker 매핑)
    result = {
        'Gold_Intl_USD': data['GC=F'],
        'Exchange_Rate': data['KRW=X'],
        'SP500': data['^GSPC'],
        'Trans_Avg': data['^DJT'],
        'US_10Y': data['^TNX']
    }
    return result

def get_krx_gold_price():
    # 2. KRX 금값 (네이버 금융 크롤링 - 가장 정확함)
    # 한국거래소 금 1kg 현물 시세 페이지
    url = "https://finance.naver.com/marketindex/goldDetail.naver"
    try:
        response = requests.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 네이버 페이지 구조에 따른 파싱 (시세는 보통 em 태그 안에 있음)
        price_str = soup.select_one("em.no_up").get_text(strip=True) # 상승장일때
        if not price_str:
            price_str = soup.select_one("em.no_down").get_text(strip=True) # 하락장일때
            
        # 콤마 제거 후 실수 변환
        price = float(price_str.replace(',', ''))
        return price
    except:
        # 장이 닫혀있거나 에러시 기본값 혹은 예외처리 (여기선 예시로 최근 근사값)
        return 0.0

# --- 메인 로직 ---
st.title("💰 Gold & Market Watch")
st.caption(f"Update: {time.strftime('%Y-%m-%d %H:%M:%S')}")

if st.button('데이터 새로고침 🔄'):
    st.rerun()

with st.spinner('데이터를 불러오는 중...'):
    try:
        macro_data = get_financial_data()
        krx_gold = get_krx_gold_price()
        
        # 0. 변수 설정
        intl_gold_usd = macro_data['Gold_Intl_USD'] # 달러/트로이온스
        exchange_rate = macro_data['Exchange_Rate'] # 원/달러
        
        # 1. 이론가 계산 (국제 금값 -> 원/g 변환)
        # 1 트로이온스 = 31.1034768 g
        intl_gold_krw_g = (intl_gold_usd * exchange_rate) / 31.1034768
        
        # 2. 괴리율 계산 (김치 프리미엄)
        if krx_gold > 0:
            spread = ((krx_gold - intl_gold_krw_g) / intl_gold_krw_g) * 100
        else:
            spread = 0
            
        # --- UI 구성: 괴리율 섹션 ---
        st.divider()
        st.subheader("📊 금 가격 괴리율 (Kim-P)")
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric(label="KRX 금시세 (g)", value=f"{krx_gold:,.0f}원")
        with col2:
            st.metric(label="국제 이론가 (g)", value=f"{intl_gold_krw_g:,.0f}원")
            
        st.metric(
            label="괴리율 (Spread)", 
            value=f"{spread:.2f}%", 
            delta=f"{spread:.2f}%",
            delta_color="inverse" # 양수면 빨강(비쌈), 음수면 파랑(저렴)
        )
        
        if spread > 1.0:
            st.warning("⚠️ 국내 금값이 국제 시세보다 1% 이상 비쌉니다.")
        elif spread < -0.5:
            st.success("✅ 국내 금값이 저렴합니다 (역프리미엄).")
        else:
            st.info("ℹ️ 적정 수준의 가격 차이입니다.")

        # --- UI 구성: 시장 지표 섹션 ---
        st.divider()
        st.subheader("🌍 주요 시장 지표")
        
        # 탭으로 구분하여 보여주기
        tab1, tab2 = st.tabs(["🇺🇸 미 증시/금리", "🚛 경기/물동량"])
        
        with tab1:
            c1, c2, c3 = st.columns(3)
            c1.metric("환율(USD)", f"{exchange_rate:,.1f}원")
            c2.metric("S&P 500", f"{macro_data['SP500']:,.0f}")
            c3.metric("미국채 10년", f"{macro_data['US_10Y']:.2f}%")
            
        with tab2:
            st.write("**다우존스 운송지수 (Dow Jones Trans.)**")
            st.caption("실물 경기와 트럭 물량을 대변하는 대표 지수입니다.")
            st.metric("운송 지수", f"{macro_data['Trans_Avg']:,.0f}")
            st.line_chart(yf.download('^DJT', period='1mo')['Close'])

    except Exception as e:
        st.error(f"데이터를 가져오는 중 오류가 발생했습니다: {e}")
