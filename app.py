import streamlit as st
import os
import requests
import xml.etree.ElementTree as ET
import yfinance as yf
import pandas_ta as ta
import pandas as pd
from dotenv import load_dotenv
from anthropic import Anthropic

# 1. 페이지 설정
st.set_page_config(page_title="AI 퀀트 투자 리포트", page_icon="📈", layout="centered")

# 2. 환경 설정 및 API 로드
load_dotenv()
api_key = st.secrets.get("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
client = Anthropic(api_key=api_key)

# 3. 데이터 수집 함수
def get_headlines():
    url = "https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=ko&gl=KR&ceid=KR:ko"
    root = ET.fromstring(requests.get(url).content)
    items = root.findall('.//item')[:15]
    return "\n".join([f"{i + 1}. {item.find('title').text}" for i, item in enumerate(items)])

def get_quant_data():
    try:
        # auto_adjust=True로 데이터 구조 단순화 및 데이터 로드
        df = yf.download("^KS11", period="60d", interval="1d", progress=False, auto_adjust=True)
        if not df.empty:
            # RSI 및 이평선 계산
            df['RSI'] = ta.rsi(df['Close'], length=14)
            df['MA20'] = ta.sma(df['Close'], length=20)
            
            # [핵심 수정] .iloc[-1] 뒤에 float()를 붙여 '순수 숫자'로 변환 (Series 에러 방지)
            last_close = float(df['Close'].iloc[-1])
            last_rsi = float(df['RSI'].iloc[-1])
            ma20 = float(df['MA20'].iloc[-1])
            
            return f"현재 KOSPI: {last_close:.2f}, RSI(14): {last_rsi:.1f}, 20일 이평선: {ma20:.2f}"
    except Exception as e:
        return f"지수 데이터 분석 실패: {e}"
    return "데이터 없음"

# --- UI 화면 구성 ---
st.title("📊 실시간 AI+퀀트 투자 리포트")
st.markdown("매일 아침 시장 이슈와 **데이터 기반** 급등 종목을 분석합니다.")

if st.button("🚀 오늘자 리포트 생성 시작"):
    with st.spinner("Pandas 지표 계산 및 AI 분석 중..."):
        try:
            combined_headlines = get_headlines()
            quant_metrics = get_quant_data()

            # Claude 4.5 분석 요청 (사용자님이 지정한 4.5 모델명 고정)
            prompt = f"""
            너는 대한민국 최고의 퀀트 투자 분석가야. 아래 뉴스 데이터와 퀀트 지표를 보고 투자 리포트를 작성해라.
            절대 중간에 끊지 말고, 마지막 '실행 가이드'까지 완벽하게 작성해.

            [뉴스 데이터]:
            {combined_headlines}

            [퀀트 지표(Pandas 분석)]:
            {quant_metrics}

            [출력 요구사항]:
            1. 📰 메인 뉴스 제목: 파급력 큰 3가지
            2. 💡 인사이트: 뉴스 이면의 의도 분석
            3. 🚀 1주일 내 5% 급등 기대 종목 Top 1: (종목명/목표가/손절가)
            4. 🎯 추천 이유: 기술적 지표(RSI 등)와 뉴스 재료 결합 분석
            5. 🏁 최종 실행 가이드: 내일 오전 구체적 대응 전략
            """

            response = client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=4000,
                temperature=0.7,
                messages=[{"role": "user", "content": prompt}]
            )

            st.markdown("---")
            st.markdown(response.content[0].text)
            st.success("✅ 퀀트 데이터 기반 리포트 생성 완료!")

        except Exception as e:
            st.error(f"❌ 오류가 발생했습니다: {e}")

st.sidebar.info(f"운영 모드: Pandas 퀀트 엔진 가동 중\n모델: Claude 4.5 Sonnet")
