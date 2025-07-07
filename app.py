import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- 페이지 기본 설정 ---
st.set_page_config(layout="wide", page_title="통합 전력 최적화 시뮬레이터")

# --- 시뮬레이션 함수 ---
def run_integrated_simulation(params):
    # [생략: 기존 run_integrated_simulation 정의 코드 유지]
    pass

# --- 인센티브 분석 함수 ---
def analyze_incentive_vs_cost(results, participation_ratio=0.6, incentive_rate=1.2):
    cost = results['누적 비용 (원)'].iloc[-1]
    high_price_threshold = results['전력가격 (SMP)'].quantile(0.8)
    strategic_hours = results[results['전력가격 (SMP)'] > high_price_threshold]
    potential_reduction = (strategic_hours['DC 총 소비전력 (kW)'].mean() * participation_ratio) * len(strategic_hours)
    average_high_price = strategic_hours['전력가격 (SMP)'].mean()
    incentive = potential_reduction * average_high_price * incentive_rate
    return cost, incentive, potential_reduction

# --- Plotly 시각화 함수 ---
def plot_incentive_vs_cost_plotly(cost, incentive):
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=["운영 비용", "수요반응 인센티브"],
        y=[cost, incentive],
        marker_color=["tomato", "seagreen"],
        text=[f"{cost:,.0f} 원", f"{incentive:,.0f} 원"],
        textposition="outside"
    ))
    fig.update_layout(
        title="운영 비용과 수요반응 인센티브 비교",
        yaxis_title="금액 (원)",
        xaxis_title="항목",
        height=500
    )
    return fig

# --- FFR 반응 시각화 ---
def plot_ffr_response():
    t = np.linspace(0, 2, 100)
    frequency = 60 + 0.05 * np.sin(10 * np.pi * t)
    cpu_response = 100 - 30 * np.sin(10 * np.pi * t)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=t, y=frequency, name="전력망 주파수 (Hz)", line=dict(color='royalblue')))
    fig.add_trace(go.Scatter(x=t, y=cpu_response, name="서버 CPU 클럭 반응 (%)", line=dict(color='firebrick')))
    fig.update_layout(title="🔁 Fast Frequency Response (FFR) 시뮬레이션",
                      xaxis_title="시간 (초)",
                      yaxis_title="값",
                      height=400)
    return fig

# --- 가치 저울 시각화 ---
def plot_value_trade_chart():
    labels = ["AI 모델 연산 가치", "전력 판매 가치"]
    values = [45, 55]
    fig = go.Figure(data=[go.Pie(labels=labels, values=values, hole=0.4)])
    fig.update_layout(title="⚖️ 실시간 가치 저울: 컴퓨팅 vs 전력 서비스")
    return fig

# --- Streamlit 앱 시작 ---
st.title("⚡️ DC-XAI 데이터센터 통합 최적화 시뮬레이터")

st.markdown("""
### 🎯 최적화 전략 3단계

#### Level 1: 방어적 최적화 (The Shield - 비용 최소화)
AI는 전력 가격이 쌀 때 IT 부하를 처리하고, 비쌀 때 지연합니다. ESS 차익 거래 및 냉각(PUE) 최적화를 통해 에너지 비용을 최대 15~20% 절감합니다. 경쟁사들이 주로 추구하는 기본적 전략입니다.

#### Level 2: 공격적 최적화 (The Sword - 수익 창출)
AI는 서버·ESS·냉각 부하를 통합한 가상발전소(VPP)를 구성하고, 전력거래소의 DR 및 보조서비스 시장에 참여합니다. 데이터센터는 에너지 비용의 30~50% 절감과 함께 수익도 창출할 수 있습니다.

#### Level 3: 패러다임 전환 (The Game Changer - 비용 소멸)
AI는 수만 대 서버의 CPU 부하 자체를 초고속 그리드 안정화 자원으로 활용합니다. Fast Frequency Response(FFR)를 통해 밀리초 단위로 서버의 소비전력을 조절해 그리드 안정화 서비스를 제공합니다. AI는 컴퓨팅의 가치와 전력거래 가치를 실시간 비교해 가장 높은 가치를 선택합니다. 전력 수익이 전력 비용을 초과하여, 실질 전력 비용이 0에 수렴하는 구조입니다.
""")

st.plotly_chart(plot_ffr_response(), use_container_width=True)
st.plotly_chart(plot_value_trade_chart(), use_container_width=True)

# --- 사용자 시나리오 조정 슬라이더 ---
with st.expander("⚙️ 수요반응 시나리오 조정 (운영팀 vs 구매팀)", expanded=False):
    part_ratio = st.slider("참여 비율 (부하 감축 비율)", 0.1, 1.0, 0.6, 0.1)
    inc_rate = st.slider("인센티브 가중치 (단가 보상 계수)", 0.5, 2.5, 1.2, 0.1)

# --- 시뮬레이션 실행 버튼 ---
if st.button("🚀 통합 최적화 시뮬레이션 실행", type="primary"):
    params = {
        'sim_hours': 48,
        'base_it_load_kw': 100,
        'deferrable_load_kw': 80,
        'max_process_power': 250,
        'pue_normal': 1.4,
        'pue_eco': 1.7,
        'ess_capacity_kwh': 200,
        'max_power_kw': 50,
        'buy_threshold': 70.0,
        'sell_threshold': 140.0,
        'cost_saving_threshold': 130.0
    }
    results, _ = run_integrated_simulation(params)  # 여기에 파라미터 전달
    cost, incentive, reduction_kwh = analyze_incentive_vs_cost(results, part_ratio, inc_rate)
    st.subheader("📈 전략적 수요반응 참여 분석 결과")
    col1, col2, col3 = st.columns(3)
    col1.metric("운영 비용", f"{cost:,.0f} 원")
    col2.metric("예상 인센티브", f"{incentive:,.0f} 원")
    col3.metric("감축한 부하량", f"{reduction_kwh:.1f} kWh")
    st.plotly_chart(plot_incentive_vs_cost_plotly(cost, incentive), use_container_width=True)

# --- 문의 폼 ---
st.markdown("### 📬 문의 또는 데모 요청")
with st.form("inquiry_form"):
    name = st.text_input("이름")
    email = st.text_input("이메일")
    organization = st.text_input("소속 기관/회사")
    message = st.text_area("문의 내용 또는 데모 요청 사항")
    submitted = st.form_submit_button("제출")
    if submitted:
        st.success("문의가 성공적으로 접수되었습니다. 빠르게 연락드리겠습니다!")
