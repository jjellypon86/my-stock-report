import streamlit as st
import os
import requests
import xml.etree.ElementTree as ET
import yfinance as yf
from pykrx import stock as krx
import pandas_ta as ta
import datetime
from dotenv import load_dotenv
from anthropic import Anthropic

# 1. 초기 인프라 설정
st.set_page_config(page_title="AI 투자 리포트", page_icon="📈", layout="centered")
load_dotenv()
api_key = st.secrets.get("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
client = Anthropic(api_key=api_key)

# 2. 뉴스 수집 함수 (기존 30개 확장 로직 복구)
def get_headlines():
    urls = [
        "https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=ko&gl=KR&ceid=KR:ko",
        "https://news.google.com/rss/headlines/section/topic/TECHNOLOGY?hl=ko&gl=KR&ceid=KR:ko"
    ]
    all_headlines = []
    for url in urls:
        root = ET.fromstring(requests.get(url).content)
        all_headlines.extend([item.find('title').text for item in root.findall('.//item')[:15]])
    sorted_headlines = sorted(list(set(all_headlines))) 
    return "\n".join([f"{i + 1}. {title}" for i, title in enumerate(sorted_headlines)])

# 3. 시장 지수 분석 (기존 60일 RSI 로직 복구)
def get_market_context():
    indices = {"KOSPI": "^KS11", "KOSDAQ": "^KQ11"}
    summary = ""
    for name, ticker in indices.items():
        try:
            df = yf.download(ticker, period="60d", progress=False, auto_adjust=True)
            if not df.empty:
                rsi = float(ta.rsi(df['Close'], length=14).iloc[-1])
                price = float(df['Close'].iloc[-1])
                summary += f"{name}: {price:.2f} (RSI: {rsi:.1f}) / "
        except: continue
    return summary

# 4. 실시간 시세 검증 함수 (시세 오류 방지용 추가)
def verify_realtime_price(ticker_code):
    try:
        # 오늘 날짜 확인
        today = datetime.date.today().strftime("%Y%m%d")
        # 네이버/KRX에서 해당 종목의 오늘 시세 가져오기
        df = krx.get_market_ohlcv_by_date(today, today, ticker_code)
        
        if df.empty:
            # 오늘 장 시작 전이면 어제 종가 가져오기
            yesterday = (datetime.date.today() - datetime.timedelta(days=1)).strftime("%Y%m%d")
            df = krx.get_market_ohlcv_by_date(yesterday, yesterday, ticker_code)

        if not df.empty:
            current_price = int(df['종가'].iloc[-1])
            return current_price, f"{ticker_code} (K-Market)"
            
    except Exception as e:
        st.error(f"시세 조회 오류: {e}")
    return None, None

# --- UI 화면 및 실행 ---
st.title("📊 실시간 AI+퀀트 투자 리포트")
st.markdown("양대 시장 지수와 뉴스를 분석하여 **실시간 검증된 1픽**을 추천합니다.")

if st.button("🚀 오늘자 분석 시작"):
    with st.spinner("데이터 분석 및 시세 검증 중..."):
        try:
            news_data = get_headlines()
            market_context = get_market_context()

            # [STEP 1] 뉴스 분석을 통한 타겟 종목 추출
            selector_prompt = f"아래 뉴스를 보고 오늘 급등할 종목 1개의 '6자리 숫자 코드'만 출력해.\n뉴스: {news_data}"
            selection = client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=10,
                temperature=0,
                messages=[{"role": "user", "content": selector_prompt}]
            )
            discovered_ticker = selection.content[0].text.strip()

            # [STEP 2] 파이썬이 실시간 시세 강제 주입 (환각 원천 차단)
            real_price, full_symbol = verify_realtime_price(discovered_ticker)

            if not real_price:
                st.error(f"❌ 종목({discovered_ticker})의 최신 시세 획득 실패. 토큰을 아끼기 위해 중단합니다.")
                st.stop()

            # [STEP 3] 검증된 데이터로 리포트 생성 (출력 요구사항 5가지 유지)
            final_prompt = f"""
            너는 대한민국 수석 퀀트다. 아래 실시간 데이터를 바탕으로 리포트를 작성해라.
            현재가 정보는 반드시 제공된 {real_price}원만 사용하고, 네 지식을 절대 쓰지 마.

            [시장 데이터]: {market_context}
            [대상 종목]: {full_symbol} / 현재가: {real_price:,.0f}원
            [뉴스 데이터]: {news_data}

            [출력 요구사항]:
            1. 📰 메인 뉴스 제목: 파급력 큰 3가지
            2. 💡 인사이트: 뉴스 이면의 의도 분석
            3. 🚀 1주일 내 5% 급등 기대 종목 Top 1: (종목명/목표가/손절가)
            4. 🎯 추천 이유: 기술적 지표와 {real_price:,.0f}원 기준의 상승 여력 분석
            5. 🏁 최종 실행 가이드: 내일 오전 구체적 대응 전략
            """

            response = client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=2000,
                temperature=0,
                messages=[{"role": "user", "content": final_prompt}]
            )

            st.markdown("---")
            st.markdown(response.content[0].text)
            st.success(f"✅ {full_symbol} (현재가: {real_price:,.0f}원) 분석 완료")

        except Exception as e:
            st.error(f"❌ 시스템 에러: {e}")

st.sidebar.info("운영 모드: 지수분석 + 실시간 시세동기화\n모델: Claude 4.5 Sonnet")
