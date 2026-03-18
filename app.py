import streamlit as st
import os
import requests
import xml.etree.ElementTree as ET
import yfinance as yf
import pandas_ta as ta
from dotenv import load_dotenv
from anthropic import Anthropic

# 1. 페이지 설정
st.set_page_config(page_title="AI 투자 리포트", page_icon="📈", layout="centered")

# 2. 환경 설정 및 API 로드
load_dotenv()
api_key = st.secrets.get("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
client = Anthropic(api_key=api_key)

# 3. 뉴스 수집 함수 (범위 확장)
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

# 4. 시장 지수 분석 (종목 선정을 위한 환경 데이터)
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

# --- UI 화면 구성 ---
st.title("📊 실시간 AI+퀀트 투자 리포트")
st.markdown("양대 시장을 스캔하여 **오늘의 무조건 베스트 1 종목**을 분석합니다.")

if st.button("🚀 오늘자 리포트 생성 시작"):
    with st.spinner("전 종목 모멘텀 분석 중..."):
        try:
            combined_headlines = get_headlines()
            market_context = get_market_context()

            # Claude 4.5 분석 요청 (종목 분석이 핵심!)
            prompt = f"""
            너는 대한민국 최고의 퀀트 투자 분석가야.
            아래 지수 상황({market_context})과 뉴스 데이터({combined_headlines})를 결합하여,
            대한민국 2,500개 전 종목 중 오늘 '무조건 이거다' 싶은 베스트 종목 딱 1개(Top 1)를 선정해라.

            [출력 요구사항]:
            1. 📰 메인 뉴스 제목: 파급력 큰 3가지
            2. 💡 인사이트: 뉴스 이면의 의도 분석
            3. 🚀 1주일 내 5% 급등 기대 종목 Top 1: (종목명/목표가/손절가)
            4. 🎯 추천 이유: 기술적 지표와 뉴스 재료 결합 분석 (왜 이 종목이 대장주인지 증명)
            5. 🏁 최종 실행 가이드: 내일 오전 구체적 대응 전략
            """

            response = client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=2000,
                temperature=0, 
                messages=[{"role": "user", "content": prompt}]
            )

            st.markdown("---")
            st.markdown(response.content[0].text)
            st.success("✅ 종목 분석 및 리포트 생성이 완료되었습니다!")

        except Exception as e:
            st.error(f"❌ 오류 발생: {e}")

# 사이드바
st.sidebar.info(f"운영 모드: 전 종목 스캔 모드\n모델: Claude 4.5 Sonnet")
