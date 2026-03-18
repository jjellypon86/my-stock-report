import streamlit as st
import os
import requests
import xml.etree.ElementTree as ET
import yfinance as yf
import pandas_ta as ta
from dotenv import load_dotenv
from anthropic import Anthropic

# 1. 페이지 설정 (스마트폰 최적화)
st.set_page_config(page_title="AI 투자 리포트", page_icon="📈", layout="centered")

# 2. 환경 설정 및 API 로드
load_dotenv()
# 로컬에선 .env를 사용하고, 클라우드 배포 시엔 Streamlit Secrets를 우선 참조합니다.
api_key = st.secrets.get("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
client = Anthropic(api_key=api_key)


# 3. 뉴스 수집 함수
def get_headlines():
    url = "https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=ko&gl=KR&ceid=KR:ko"
    root = ET.fromstring(requests.get(url).content)
    items = root.findall('.//item')[:15]
    return "\n".join([f"{i + 1}. {item.find('title').text}" for i, item in enumerate(items)])


# --- UI 화면 구성 ---
st.title("📊 실시간 AI+퀀트 투자 리포트")
st.markdown("매일 아침 시장 이슈와 급등 기대 종목을 분석합니다.")

if st.button("🚀 오늘자 리포트 생성 시작"):
    with st.spinner("실시간 뉴스 수집 및 AI 분석 중..."):
        try:
            # 뉴스 데이터 확보
            combined_headlines = get_headlines()

            # Claude 4.5 분석 요청 (끊김 방지 max_tokens=4000)
            prompt = f"""
            너는 대한민국 최고의 퀀트 투자 분석가야. 아래 뉴스 헤드라인을 보고 투자 리포트를 작성해라.
            절대 중간에 끊지 말고, 마지막 '실행 가이드'까지 완벽하게 작성해.

            [뉴스 데이터]:
            {combined_headlines}

            [출력 요구사항]:
            1. 📰 메인 뉴스 제목: 파급력 큰 3가지
            2. 🔑 핵심 키워드: 돈의 흐름 3가지
            3. 💡 인사이트: 뉴스 이면의 의도 분석
            4. 🚀 1주일 내 5% 급등 기대 종목 Top 3: (종목명/목표가/손절가)
            5. 🎯 추천 이유: 기술적 지표와 뉴스 재료 결합 분석
            6. 🏁 최종 실행 가이드: 내일 오전 구체적 대응 전략
            """

            response = client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=4000,
                temperature=0.7,
                messages=[{"role": "user", "content": prompt}]
            )

            # 결과 출력
            report_text = response.content[0].text
            st.markdown("---")
            st.markdown(report_text)
            st.success("✅ 리포트 생성이 완료되었습니다!")

        except Exception as e:
            st.error(f"❌ 오류가 발생했습니다: {e}")

# 푸터 (ISTJ형 업무 기록)
st.sidebar.info(f"계정 잔액 기반 안정적 운영 중\n모델: Claude 4.5 Sonnet")