"""EcoCharge Jeonbuk AI — 수소·전기차 충전 입지 추천 Streamlit 앱."""

import streamlit as st
import folium
import pandas as pd
import numpy as np
from streamlit_folium import st_folium

from data_loader import build_master, load_tourism
from scoring import compute_suitability, add_reasons, apply_scenario, SCENARIOS

# ── 페이지 설정 ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="EcoCharge Jeonbuk AI",
    page_icon="⚡",
    layout="wide",
)

st.title("⚡ EcoCharge Jeonbuk AI")
st.caption("전북특별자치도 수소·전기차 충전 인프라 최적 입지 추천 플랫폼")


# ── 데이터 로드 (캐시) ────────────────────────────────────────────────────────
@st.cache_data(show_spinner="데이터 통합 및 점수 산출 중…")
def get_scored() -> pd.DataFrame:
    master  = build_master()
    scored  = compute_suitability(master)
    return add_reasons(scored)


@st.cache_data(show_spinner=False)
def get_tourism() -> pd.DataFrame:
    return load_tourism()


scored   = get_scored()
tourism  = get_tourism()


# ── 사이드바 ─────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("🎛️ 정책 시나리오")
    scenario = st.selectbox(
        "입지 우선순위 전략 선택",
        list(SCENARIOS.keys()),
        index=0,
    )
    if scenario != "기본 균형":
        display = apply_scenario(scored, scenario)
    else:
        display = scored.copy()

    st.divider()
    st.header("🔍 필터")
    top_n = st.slider("상위 N개 지역 강조", 1, len(display), 5)
    show_tourism = st.checkbox("관광지 마커 표시", value=True)
    show_chargers = st.checkbox("기존 OSM 충전소 표시", value=False)

    st.divider()
    st.header("📊 전체 데이터 현황")
    st.metric("전북 전기차 총 등록",  f"{int(scored['ev_count'].sum()):,} 대")
    st.metric("관광지",               f"{int(scored['tourism_count'].sum())} 개소")
    st.metric("산업단지 입주업체",     f"{int(scored['industry_firms'].sum()):,} 개")
    st.metric("버스정류장 이용(분석건)", f"{int(scored['bus_usage'].sum()):,} 명")


# ── 탭 구성 ──────────────────────────────────────────────────────────────────
tab_map, tab_rank, tab_detail, tab_guide = st.tabs(
    ["🗺️ 입지 추천 지도", "📋 우선순위 순위표", "📈 지표 분석", "📖 서비스 설명"]
)


# ── 탭1: 지도 ────────────────────────────────────────────────────────────────
with tab_map:
    col_map, col_legend = st.columns([3, 1])

    with col_map:
        m = folium.Map(location=[35.7, 127.1], zoom_start=9, tiles="CartoDB Positron")

        # ESS 점수 → 버블 크기·색상 매핑
        max_ess = display["ess"].max()
        color_map = {1: "#e74c3c", 2: "#e67e22", 3: "#f1c40f",
                     4: "#2ecc71", 5: "#27ae60"}

        for _, row in display.iterrows():
            rank = int(row["rank"])
            ess  = float(row["ess"])

            if rank <= top_n:
                color = color_map.get(rank, "#3498db")
                opacity = 0.85
                radius  = 16 + (max_ess - ess) * 0.3
            else:
                color   = "#95a5a6"
                opacity = 0.45
                radius  = 8

            popup_html = f"""
            <div style='font-family:sans-serif;width:240px'>
              <b style='font-size:14px'>#{rank} {row['sigungu']}</b><br>
              <hr style='margin:4px 0'>
              <b>EcoCharge Score: {ess:.1f}</b><br><br>
              <table style='font-size:11px;width:100%'>
                <tr><td>전기차 수요</td><td align='right'>{row['score_ev']:.0f}/100</td></tr>
                <tr><td>관광 잠재수요</td><td align='right'>{row['score_tourism']:.0f}/100</td></tr>
                <tr><td>산업단지 수요</td><td align='right'>{row['score_industry']:.0f}/100</td></tr>
                <tr><td>버스 접근성</td><td align='right'>{row['score_bus']:.0f}/100</td></tr>
                <tr><td>충전 공백도</td><td align='right'>{row['score_gap']:.0f}/100</td></tr>
              </table>
              <hr style='margin:4px 0'>
              <span style='font-size:10px;color:#555'>{row['reason']}</span>
            </div>
            """

            folium.CircleMarker(
                location=[row["lat"], row["lon"]],
                radius=radius,
                color=color,
                fill=True,
                fill_color=color,
                fill_opacity=opacity,
                popup=folium.Popup(popup_html, max_width=260),
                tooltip=f"#{rank} {row['sigungu']} — ESS {ess:.1f}",
            ).add_to(m)

            if rank <= top_n:
                folium.Marker(
                    location=[row["lat"] + 0.02, row["lon"]],
                    icon=folium.DivIcon(
                        html=f'<div style="font-size:11px;font-weight:bold;color:{color};'
                             f'text-shadow:1px 1px 2px white">#{rank}</div>',
                    ),
                ).add_to(m)

        # 관광지 마커
        if show_tourism:
            t_group = folium.FeatureGroup(name="관광지", show=True)
            for _, row in tourism.iterrows():
                folium.CircleMarker(
                    location=[row["lat"], row["lon"]],
                    radius=3,
                    color="#8e44ad",
                    fill=True,
                    fill_opacity=0.5,
                    tooltip=row["name"],
                ).add_to(t_group)
            t_group.add_to(m)

        folium.LayerControl().add_to(m)
        st_folium(m, use_container_width=True, height=560)

    with col_legend:
        st.subheader("🏆 상위 지역")
        for _, row in display.head(top_n).iterrows():
            rank = int(row["rank"])
            medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(rank, f"#{rank}")
            st.markdown(f"**{medal} {row['sigungu']}**")
            st.progress(int(row["ess"]), text=f"ESS {row['ess']:.1f}")
            st.caption(row["reason"][:60] + "…" if len(row["reason"]) > 60 else row["reason"])
            st.write("")

        st.divider()
        st.caption(f"**시나리오:** {scenario}")
        st.caption("버블 클릭 시 상세 점수 확인 가능")


# ── 탭2: 순위표 ───────────────────────────────────────────────────────────────
with tab_rank:
    st.subheader(f"EcoCharge Suitability Score 순위 — {scenario}")

    rank_df = display[[
        "rank", "sigungu", "ess",
        "score_ev", "score_tourism", "score_industry", "score_bus", "score_gap",
        "ev_count", "tourism_count", "industry_firms", "bus_usage",
    ]].copy()

    rank_df.columns = [
        "순위", "시군", "ESS",
        "전기차(30%)", "관광(25%)", "산업(20%)", "버스(15%)", "공백(10%)",
        "전기차 등록", "관광지 수", "산업단지 업체", "버스이용량",
    ]

    st.dataframe(
        rank_df.style
            .background_gradient(subset=["ESS"], cmap="RdYlGn")
            .format({"ESS": "{:.1f}", "전기차(30%)": "{:.0f}", "관광(25%)": "{:.0f}",
                     "산업(20%)": "{:.0f}", "버스(15%)": "{:.0f}", "공백(10%)": "{:.0f}",
                     "전기차 등록": "{:,.0f}", "버스이용량": "{:,.0f}"}),
        use_container_width=True,
        height=480,
        hide_index=True,
    )

    st.subheader("📝 추천 이유 (설명 가능 AI)")
    for _, row in display.head(5).iterrows():
        with st.expander(f"#{int(row['rank'])} {row['sigungu']} — ESS {row['ess']:.1f}"):
            st.markdown(row["reason"])
            cols = st.columns(5)
            labels = ["전기차 수요", "관광 수요", "산업 수요", "버스 접근", "충전 공백"]
            scores = [row["score_ev"], row["score_tourism"], row["score_industry"],
                      row["score_bus"], row["score_gap"]]
            for col, label, score in zip(cols, labels, scores):
                col.metric(label, f"{score:.0f}")


# ── 탭3: 지표 분석 ────────────────────────────────────────────────────────────
with tab_detail:
    st.subheader("시군별 원시 지표 현황")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**전기차 등록 대수 (시군별)**")
        ev_chart = display.set_index("sigungu")[["ev_count"]].sort_values("ev_count", ascending=True)
        st.bar_chart(ev_chart)

        st.markdown("**산업단지 입주업체 수 (시군별)**")
        ind_chart = display.set_index("sigungu")[["industry_firms"]].sort_values("industry_firms", ascending=True)
        st.bar_chart(ind_chart)

    with col2:
        st.markdown("**관광지 수 (시군별)**")
        tour_chart = display.set_index("sigungu")[["tourism_count"]].sort_values("tourism_count", ascending=True)
        st.bar_chart(tour_chart)

        st.markdown("**버스정류장 이용량 (시군별)**")
        bus_chart = display.set_index("sigungu")[["bus_usage"]].sort_values("bus_usage", ascending=True)
        st.bar_chart(bus_chart)

    st.divider()
    st.subheader("📥 데이터 다운로드")
    csv = display.to_csv(index=False, encoding="utf-8-sig")
    st.download_button(
        "ESS 분석 결과 CSV 다운로드",
        data=csv,
        file_name="ecocharge_jeonbuk_ess.csv",
        mime="text/csv",
    )


# ── 탭4: 서비스 설명 ──────────────────────────────────────────────────────────
with tab_guide:
    st.subheader("EcoCharge Jeonbuk AI 서비스 개요")
    st.markdown("""
### EcoCharge Suitability Score (ESS) 산출 방식

| 지표 | 기본 가중치 | 데이터 출처 |
|------|------------|------------|
| 전기차 수요 | 30% | 전북특별자치도 전기차 현황 |
| 관광 잠재수요 | 25% | 전북특별자치도 관광지 위치정보 |
| 산업단지 수요 | 20% | 전북특별자치도 산업단지 현황 |
| 버스 접근성 | 15% | 한국교통안전공단 전라북도 최다 이용 정류장 |
| 충전 공백도 | 10% | OpenStreetMap 기존 충전소 POI |

### 정책 시나리오 설명

| 시나리오 | 적합 상황 |
|---------|----------|
| 기본 균형 | 종합적 인프라 확충 계획 수립 |
| 관광 우선 | 전북 관광 시즌 전 충전 인프라 보강 |
| 산업단지 우선 | 친환경 상용차 전환 지원 |
| 충전 사각지대 해소 | 농촌·동부권 지역균형 발전 |
| 대중교통 연계 | 복합 환승 거점 중심 충전소 확충 |

### 활용 방법
1. **사이드바**에서 정책 시나리오 선택
2. **지도 탭** 버블 클릭 → 시군별 상세 점수 확인
3. **순위표 탭** → 전체 순위 및 추천 이유 확인
4. **지표 분석 탭** → 원시 데이터 차트 및 CSV 다운로드
    """)
