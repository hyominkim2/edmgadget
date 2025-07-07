import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- 페이지 기본 설정 ---
st.set_page_config(layout="wide", page_title="통합 전력 최적화 시뮬레이터")


# --- 시뮬레이션 함수 ---
def run_integrated_simulation(params):
    """
    데이터센터와 전력 거래를 통합한 시뮬레이션 실행
    """
    sim_hours = params['sim_hours']

    # 1. 환경 생성: 전력 가격(SMP) 및 IT 워크로드 프로파일 생성
    time = np.arange(sim_hours)
    # SMP: 하루 주기성을 가진 가격 곡선
    smp = 100 - np.cos(time * np.pi / 12) * 50 + np.random.randn(sim_hours) * 5
    smp = np.maximum(smp, 20)

    # IT 워크로드: 기본 부하 + 특정 시간에 몰리는 유연 부하(Deferrable Load)
    base_it_load = np.full(sim_hours, params['base_it_load_kw']) + np.sin(time * np.pi / 12) * 10
    deferrable_load_schedule = np.zeros(sim_hours)
    # 오후(13~16시)에 유연 부하 집중 발생
    deferrable_load_schedule[13:17] = params['deferrable_load_kw']
    deferrable_load_schedule[13 + 24:17 + 24] = params['deferrable_load_kw']  # 이틀치 시뮬레이션

    # 2. 시뮬레이션 변수 초기화
    # DC 관련
    dc_total_load_log, pue_log, it_load_processed_log = [], [], []
    deferred_bank = 0  # 미뤄진 작업 저장소 (단위: kWh)

    # 거래 관련
    soc_log = [params['ess_capacity_kwh'] / 2]
    grid_power_log = []
    total_cost_log = [0]

    # 로그용
    actions_log = []

    # 3. 시간대별 시뮬레이션 루프
    for t in range(sim_hours):
        current_smp = smp[t]
        current_soc = soc_log[-1]

        # --- 입력(State) 기반 행동(Action) 결정 ---
        action = "일반 모드"
        pue = params['pue_normal']

        # 유연 부하를 은행에 추가
        deferred_bank += deferrable_load_schedule[t]

        # 정책 1: 가격이 너무 비싸면 비용 절감 모드 돌입
        if current_smp > params['cost_saving_threshold']:
            action = "비용 절감 모드 (부하 지연)"
            pue = params['pue_eco']
            processed_it_load = base_it_load[t]  # 기본 부하만 처리

        # 정책 2: 가격이 싸고, 처리할 작업이 남아있으면 고성능 모드
        elif current_smp < params['buy_threshold'] and deferred_bank > 0:
            action = "고성능 모드 (지연 부하 처리)"
            pue = params['pue_normal']
            # 은행에 쌓인 작업 처리 (처리 능력 한도 내에서)
            processable_load = params['max_process_power'] - base_it_load[t]
            processed_from_bank = min(deferred_bank, processable_load)
            processed_it_load = base_it_load[t] + processed_from_bank
            deferred_bank -= processed_from_bank

        # 정책 3: 일반적인 상황
        else:
            processed_it_load = base_it_load[t]
            # 남는 처리 능력이 있다면 은행 작업도 처리
            processable_load = params['max_process_power'] - base_it_load[t]
            processed_from_bank = min(deferred_bank, processable_load)
            processed_it_load += processed_from_bank
            deferred_bank -= processed_from_bank

        # DC 총 전력 소비량 계산
        cooling_load = processed_it_load * (pue - 1)
        current_dc_total_load = processed_it_load + cooling_load

        # --- 전력 공급원 결정 (ESS vs Grid) ---
        power_needed = current_dc_total_load

        # ESS 방전 결정 (DC에 전력 공급 or 판매)
        if current_smp > params['sell_threshold'] and current_soc > 0:
            power_from_ess = min(current_soc, params['max_power_kw'])
            soc_change = -power_from_ess
            power_from_grid = power_needed - power_from_ess  # < 0 이면 판매
        # ESS 충전 결정
        elif current_smp < params['buy_threshold'] and current_soc < params['ess_capacity_kwh']:
            charge_amount = min(params['max_power_kw'], params['ess_capacity_kwh'] - current_soc)
            soc_change = charge_amount
            power_from_grid = power_needed + charge_amount
        # ESS로 DC 부하 우선 감당
        else:
            power_from_ess = min(current_soc, power_needed, params['max_power_kw'])
            soc_change = -power_from_ess
            power_from_grid = power_needed - power_from_ess

        # 변수 업데이트 및 로그 기록
        soc_log.append(current_soc + soc_change)
        total_cost_log.append(
            total_cost_log[-1] + max(0, power_from_grid) * current_smp - max(0, -power_from_grid) * current_smp)

        dc_total_load_log.append(current_dc_total_load)
        pue_log.append(pue)
        it_load_processed_log.append(processed_it_load)
        grid_power_log.append(power_from_grid)
        actions_log.append(action)

    # 결과 데이터프레임 생성
    results_df = pd.DataFrame({
        '시간': time, '전력가격 (SMP)': smp, 'DC 총 소비전력 (kW)': dc_total_load_log,
        '처리된 IT 부하 (kW)': it_load_processed_log, '그리드 전력 (kW)': grid_power_log,
        'ESS 충전량 (kWh)': soc_log[:-1], '적용된 PUE': pue_log, '누적 비용 (원)': total_cost_log[:-1],
        '에이전트 행동': actions_log
    })
    return results_df, deferred_bank



# --- Streamlit UI 구성 ---
st.title("⚡️ DC-XAI 데이터센터 통합 최적화 시뮬레이터")
st.markdown("""
본 시뮬레이터는 **데이터센터 전력 최적화**와 **전력 거래 최적화**를 동시에 수행하는 강화학습 에이전트가 작동하는 방식을 보여줍니다.  
에이전트는 `전력 가격(SMP)`에 따라 `IT 작업 스케줄링`, `냉각 정책`,`ESS 충/방전`을 통합적으로 결정하여 총 운영 비용을 최소화합니다.  
""")


st.markdown("## ✅ Benefits")
st.markdown("""
 💰  **운영 비용 절감**: 전력 가격 변화에 따른 실시간 부하 조절이 가능합니다.  
 🌱  **탄소 배출 저감**: 냉각 정책과 ESS 운용 최적화를 통한 친환경 전략을 세울 수 있습니다.  
 🤖  **AI 기반 의사결정**: 강화학습 정책으로 상황에 따른 최적 행동을 선택하는 AI 모델입니다.  
 📊  **가시성 확보**: ESS, PUE, 전력 가격 등 다양한 지표를 시각적으로 추적할 수 있습니다.  
 🛠️  **시나리오 실험**: 다양한 매개변수를 통해 맞춤형 전략 테스트가 가능합니다.  
""")

# --- 사이드바: 사용자 입력 파라미터 ---
with st.sidebar:
    st.header("⚙️ 시뮬레이션 설정")
    params = {}
    params['sim_hours'] = 48

    with st.expander("🏢 데이터센터 설정", expanded=True):
        params['base_it_load_kw'] = st.slider("기본 IT 부하 (kW)", 50, 500, 100, 10)
        params['deferrable_load_kw'] = st.slider("시간당 유연 부하 (kW)", 20, 200, 80, 10)
        params['max_process_power'] = st.slider("최대 IT 처리 전력 (kW)", 100, 500, 250, 10)
        params['pue_normal'] = st.slider("PUE (일반 모드)", 1.1, 2.0, 1.4, 0.05)
        params['pue_eco'] = st.slider("PUE (에코 모드)", params['pue_normal'], 2.5, 1.7, 0.05)

    with st.expander("🔋 ESS & 전력 거래 설정", expanded=True):
        params['ess_capacity_kwh'] = st.slider("ESS 총 용량 (kWh)", 50, 1000, 200, 10)
        params['max_power_kw'] = st.slider("ESS 최대 충/방전 속도 (kW)", 10, 100, 50, 5)

    with st.expander("🤖 통합 에이전트 정책 설정", expanded=True):
        st.write("가격이 해당 값 **이하**일 때 전력을 사고 작업을 처리합니다.")
        params['buy_threshold'] = st.slider("매수/고성능 기준 가격", 40.0, 150.0, 70.0, 1.0)
        st.write("가격이 해당 값 **이상**일 때 전력을 팔고 작업을 지연합니다.")
        params['sell_threshold'] = st.slider("매도 기준 가격", 100.0, 200.0, 140.0, 1.0)
        params['cost_saving_threshold'] = st.slider("비용 절감(부하 지연) 기준 가격", 100.0, 200.0, 130.0, 1.0)

# --- 메인 화면 ---
if st.button("🚀 통합 최적화 시뮬레이션 실행", type="primary"):
    results, remaining_deferred_load = run_integrated_simulation(params)

    st.header("📊 시뮬레이션 결과")
    col1, col2, col3 = st.columns(3)
    final_cost = results['누적 비용 (원)'].iloc[-1]
    col1.metric("최종 운영 비용", f"{final_cost:,.0f} 원")
    avg_pue = results['적용된 PUE'].mean()
    col2.metric("평균 PUE", f"{avg_pue:.2f}")
    col3.metric("남은 유연 부하 (kWh)", f"{remaining_deferred_load:.1f}", help="시뮬레이션 종료 후 처리되지 못한 작업량")

    st.subheader("📈 DC 소비전력 vs. 전력 가격(SMP)")
    fig1 = make_subplots(specs=[[{"secondary_y": True}]])
    fig1.add_trace(go.Scatter(x=results['시간'], y=results['전력가격 (SMP)'], name="전력가격(SMP)", line=dict(color='orange')),
                   secondary_y=False)
    fig1.add_trace(go.Scatter(x=results['시간'], y=results['DC 총 소비전력 (kW)'], name="DC 총 소비전력", line=dict(color='blue')),
                   secondary_y=True)
    fig1.update_layout(title_text="DC 소비전력은 전력 가격에 '반응'하여 변동합니다",
                       legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    fig1.update_yaxes(title_text="<b>가격(원/kWh)</b>", secondary_y=False)
    fig1.update_yaxes(title_text="<b>전력(kW)</b>", secondary_y=True)
    st.plotly_chart(fig1, use_container_width=True)

    st.subheader("📈 에너지 흐름 및 누적 비용")
    fig2 = make_subplots(specs=[[{"secondary_y": True}]])
    fig2.add_trace(go.Bar(x=results['시간'], y=results['그리드 전력 (kW)'], name="그리드 전력 (구매/판매)", marker_color='lightgreen'),
                   secondary_y=False)
    fig2.add_trace(
        go.Scatter(x=results['시간'], y=results['ESS 충전량 (kWh)'], name="ESS 충전량(SoC)", line=dict(color='purple')),
        secondary_y=False)
    fig2.add_trace(go.Scatter(x=results['시간'], y=results['누적 비용 (원)'], name="누적 비용", line=dict(color='red', width=3)),
                   secondary_y=True)
    fig2.update_layout(title_text="ESS 운영 및 그리드 상호작용을 통한 비용 최적화",
                       legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    fig2.update_yaxes(title_text="<b>전력(kW/kWh)</b>", secondary_y=False,
                      range=[-params['max_power_kw'] * 1.5, params['max_process_power'] * 2])
    fig2.update_yaxes(title_text="<b>누적 비용(원)</b>", secondary_y=True)
    st.plotly_chart(fig2, use_container_width=True)

    with st.expander("📄 시간별 상세 데이터 로그 보기"):
        st.dataframe(results)

# 입력 폼 (사전 신청, 문의 등)
st.markdown("### 📬 문의 또는 데모 요청")
with st.form("inquiry_form"):
    name = st.text_input("이름")
    email = st.text_input("이메일")
    organization = st.text_input("소속 기관/회사")
    message = st.text_area("문의 내용 또는 데모 요청 사항")
    submitted = st.form_submit_button("제출")
    if submitted:
        st.success("문의가 성공적으로 접수되었습니다. 빠르게 연락드리겠습니다!")
