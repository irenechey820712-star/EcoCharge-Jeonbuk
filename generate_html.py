"""EcoCharge Jeonbuk AI — 독립 HTML 데모 생성기.

실행: python generate_html.py
결과: ecocharge_demo.html (브라우저에서 바로 열 수 있음)
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import folium
import webbrowser
from pathlib import Path

from data_loader import build_master, load_tourism
from scoring import compute_suitability, add_reasons, apply_scenario, SCENARIOS

OUTPUT = Path(__file__).parent / "ecocharge_demo.html"

# ESS 점수 → 색상
def _ess_color(rank: int) -> str:
    palette = {1: "#c0392b", 2: "#e67e22", 3: "#f39c12",
               4: "#27ae60", 5: "#2980b9"}
    return palette.get(rank, "#7f8c8d")


def build_map() -> folium.Map:
    print("1/3  데이터 로딩 및 점수 산출 중...")
    master  = build_master()
    scored  = add_reasons(compute_suitability(master))
    tourism = load_tourism()

    print("2/3  지도 빌드 중...")
    m = folium.Map(location=[35.7, 127.15], zoom_start=9, tiles="CartoDB Positron")

    # ── 관광지 레이어 ────────────────────────────────────────────────────────
    tour_layer = folium.FeatureGroup(name="관광지", show=True)
    for _, row in tourism.iterrows():
        folium.CircleMarker(
            location=[row["lat"], row["lon"]],
            radius=4,
            color="#8e44ad",
            fill=True,
            fill_opacity=0.55,
            tooltip=row["name"],
        ).add_to(tour_layer)
    tour_layer.add_to(m)

    # ── 시나리오별 레이어 ─────────────────────────────────────────────────────
    scenario_list = list(SCENARIOS.keys())
    for s_idx, scenario in enumerate(scenario_list):
        if scenario == "기본 균형":
            s_scored = scored
        else:
            s_scored = add_reasons(apply_scenario(scored, scenario))

        layer = folium.FeatureGroup(name=f"[시나리오] {scenario}", show=(s_idx == 0))
        max_ess = float(s_scored["ess"].max())

        for _, row in s_scored.iterrows():
            rank    = int(row["rank"])
            ess     = float(row["ess"])
            color   = _ess_color(rank)
            radius  = 10 + (ess / max_ess) * 22

            popup_html = f"""
            <div style='font-family:sans-serif;width:260px;font-size:12px'>
              <b style='font-size:14px'>#{rank} {row['sigungu']}</b>
              <hr style='margin:5px 0'>
              <b style='font-size:15px;color:{color}'>ESS {ess:.1f} / 100</b>
              <table style='width:100%;margin-top:6px'>
                <tr><td>전기차 수요</td>
                    <td align='right'><b>{row['score_ev']:.0f}</b></td></tr>
                <tr><td>관광 잠재수요</td>
                    <td align='right'><b>{row['score_tourism']:.0f}</b></td></tr>
                <tr><td>산업단지 수요</td>
                    <td align='right'><b>{row['score_industry']:.0f}</b></td></tr>
                <tr><td>버스 접근성</td>
                    <td align='right'><b>{row['score_bus']:.0f}</b></td></tr>
                <tr><td>충전 공백도</td>
                    <td align='right'><b>{row['score_gap']:.0f}</b></td></tr>
              </table>
              <hr style='margin:5px 0'>
              <span style='color:#555'>{row['reason']}</span>
              <hr style='margin:5px 0'>
              <span style='color:#888;font-size:10px'>
                전기차 {int(row['ev_count'])}대 &nbsp;|&nbsp;
                관광지 {int(row['tourism_count'])}개 &nbsp;|&nbsp;
                산업단지 {int(row['industry_firms'])}개 업체
              </span>
            </div>"""

            folium.CircleMarker(
                location=[row["lat"], row["lon"]],
                radius=radius,
                color=color,
                fill=True,
                fill_color=color,
                fill_opacity=0.8,
                popup=folium.Popup(popup_html, max_width=280),
                tooltip=f"#{rank} {row['sigungu']} | ESS {ess:.1f}",
            ).add_to(layer)

            # 순위 레이블 (상위 5개)
            if rank <= 5:
                folium.Marker(
                    location=[row["lat"] + 0.025, row["lon"]],
                    icon=folium.DivIcon(
                        html=f'<div style="font-size:11px;font-weight:bold;'
                             f'color:{color};text-shadow:1px 1px 2px white;'
                             f'white-space:nowrap">#{rank} {row["sigungu"]}</div>',
                        icon_size=(120, 20),
                    ),
                ).add_to(layer)

        layer.add_to(m)

    folium.LayerControl(collapsed=False).add_to(m)

    # ── 순위표 패널 ───────────────────────────────────────────────────────────
    rank_rows = ""
    for _, row in scored.head(7).iterrows():
        rank = int(row["rank"])
        color = _ess_color(rank)
        bar_w = int(row["ess"])
        rank_rows += f"""
        <tr>
          <td style='padding:3px 6px;font-weight:bold;color:{color}'>#{rank}</td>
          <td style='padding:3px 6px'>{row['sigungu']}</td>
          <td style='padding:3px 6px'>
            <div style='background:#eee;border-radius:3px;height:14px;width:120px'>
              <div style='background:{color};height:14px;width:{bar_w}%;
                          border-radius:3px;display:flex;align-items:center;
                          padding-left:4px;font-size:10px;color:white'>
                {row['ess']:.1f}
              </div>
            </div>
          </td>
        </tr>"""

    legend = f"""
    <div style="
        position: fixed; bottom: 30px; left: 30px; z-index: 9999;
        background: white; padding: 16px 20px; border-radius: 12px;
        box-shadow: 0 2px 16px rgba(0,0,0,0.22);
        font-family: 'Noto Sans KR', sans-serif; font-size: 13px;
        max-width: 340px;">
      <div style='font-size:16px;font-weight:bold;margin-bottom:10px'>
        ⚡ EcoCharge Jeonbuk AI
      </div>
      <div style='font-size:11px;color:#888;margin-bottom:8px'>
        충전 인프라 최적 입지 추천 &nbsp;|&nbsp; 기본 균형 시나리오
      </div>
      <table style='width:100%;border-collapse:collapse'>
        <tr style='font-size:10px;color:#aaa'>
          <th>순위</th><th>시군</th><th>ESS 점수</th>
        </tr>
        {rank_rows}
      </table>
      <div style='margin-top:10px;font-size:10px;color:#aaa'>
        버블 클릭 시 세부 점수 확인 &nbsp;|&nbsp;
        보라색 점 = 관광지<br>
        우측 상단 레이어 컨트롤로 시나리오 전환
      </div>
    </div>"""

    m.get_root().html.add_child(folium.Element(legend))
    return m


if __name__ == "__main__":
    print("EcoCharge Jeonbuk HTML 생성 시작")
    m = build_map()
    print(f"3/3  HTML 저장 중... -> {OUTPUT}")
    m.save(str(OUTPUT))
    print(f"\n완료! 파일을 브라우저로 여세요:")
    print(f"  {OUTPUT}")
    webbrowser.open(str(OUTPUT))
