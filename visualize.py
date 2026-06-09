"""EcoCharge Jeonbuk AI — 6단계 분석 시각화 리포트 생성기.
matplotlib 없이 Chart.js 기반 순수 HTML로 생성.

실행: python visualize.py
결과: ecocharge_report.html
"""

import sys, os, json, warnings
from pathlib import Path

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(__file__))

# OSM 스레드 비활성화 (시각화에서는 gap 점수 불필요)
os.environ["SKIP_OSM"] = "1"

import pandas as pd
from data_loader import build_master
from scoring import compute_suitability, add_reasons, apply_scenario, SCENARIOS

OUTPUT = Path(__file__).parent / "ecocharge_report.html"

PALETTE = ["#c0392b","#e67e22","#f1c40f","#27ae60","#2980b9",
           "#8e44ad","#16a085","#d35400","#2c3e50","#7f8c8d",
           "#1abc9c","#e74c3c","#3498db","#9b59b6"]

def ess_color(rank: int) -> str:
    return PALETTE[min(rank - 1, len(PALETTE) - 1)]


def build_html(master: pd.DataFrame, scored: pd.DataFrame) -> str:
    snames = list(SCENARIOS.keys())

    # ── 데이터 직렬화 ─────────────────────────────────────────────────────────
    labels    = scored["sigungu"].tolist()
    ev        = scored["ev_count"].tolist()
    tourism   = scored["tourism_count"].tolist()
    industry  = scored["industry_firms"].tolist()
    bus       = scored["bus_usage"].tolist()
    ess       = scored["ess"].tolist()
    s_ev      = scored["score_ev"].tolist()
    s_tour    = scored["score_tourism"].tolist()
    s_ind     = scored["score_industry"].tolist()
    s_bus     = scored["score_bus"].tolist()
    s_gap     = scored["score_gap"].tolist()
    colors    = [ess_color(int(r)) for r in scored["rank"]]

    # 시나리오별 ESS
    scenario_data = {}
    for sname in snames:
        s = scored if sname == "기본 균형" else apply_scenario(scored, sname)
        scenario_data[sname] = {
            sg: float(s[s["sigungu"] == sg]["ess"].values[0])
            for sg in labels
        }

    # 순위표 행
    table_rows = ""
    for _, row in scored.iterrows():
        rank  = int(row["rank"])
        color = ess_color(rank)
        bar   = int(row["ess"])
        reason_short = row["reason"][:70] + ("…" if len(row["reason"]) > 70 else "")
        table_rows += f"""
        <tr>
          <td style="color:{color};font-weight:700">#{rank}</td>
          <td style="font-weight:600">{row['sigungu']}</td>
          <td>
            <div class="bar-wrap">
              <div class="bar-fill" style="width:{bar}%;background:{color}">{row['ess']:.1f}</div>
            </div>
          </td>
          <td>{row['score_ev']:.0f}</td>
          <td>{row['score_tourism']:.0f}</td>
          <td>{row['score_industry']:.0f}</td>
          <td>{row['score_bus']:.0f}</td>
          <td>{row['score_gap']:.0f}</td>
          <td class="reason">{reason_short}</td>
        </tr>"""

    # 시나리오 라인 데이터 (상위 3개 시군)
    top3      = scored.head(3)["sigungu"].tolist()
    top3_colors = ["#c0392b", "#2980b9", "#27ae60"]
    line_datasets = json.dumps([{
        "label": sg,
        "data": [scenario_data[sn][sg] for sn in snames],
        "borderColor": c,
        "backgroundColor": c + "33",
        "tension": 0.3,
        "pointRadius": 6,
        "borderWidth": 2,
    } for sg, c in zip(top3, top3_colors)])

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>EcoCharge Jeonbuk AI — 분석 리포트</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:'Malgun Gothic','맑은 고딕',sans-serif;background:#f0f2f5;color:#2c3e50}}
  .hero{{background:linear-gradient(135deg,#1a252f,#2c3e50 55%,#27ae60);
         color:#fff;padding:44px 60px;text-align:center}}
  .hero h1{{font-size:30px;margin-bottom:8px}}
  .hero p{{font-size:14px;opacity:.8}}
  .kpi-bar{{display:flex;gap:14px;padding:20px 48px;background:#fff;
            border-bottom:2px solid #ecf0f1;flex-wrap:wrap}}
  .kpi{{flex:1;min-width:120px;background:#f8f9fa;border-radius:10px;
        padding:14px 12px;text-align:center}}
  .kpi .val{{font-size:26px;font-weight:700;color:#27ae60}}
  .kpi .lbl{{font-size:11px;color:#888;margin-top:4px}}
  .container{{max-width:1300px;margin:0 auto;padding:28px 40px}}
  .card{{background:#fff;border-radius:12px;margin-bottom:28px;
         box-shadow:0 2px 12px rgba(0,0,0,.07);overflow:hidden}}
  .card-hdr{{padding:14px 22px;background:#2c3e50;color:#fff;
             display:flex;align-items:center;gap:14px}}
  .step-num{{background:#27ae60;padding:3px 11px;border-radius:16px;font-size:11px;font-weight:700}}
  .step-title{{font-size:16px;font-weight:700}}
  .step-desc{{font-size:11px;opacity:.7;margin-left:auto}}
  .chart-grid{{display:grid;grid-template-columns:1fr 1fr;gap:20px;padding:22px}}
  .chart-box{{position:relative;height:300px}}
  .chart-box.tall{{height:380px}}
  table{{width:100%;border-collapse:collapse}}
  th{{background:#ecf0f1;padding:8px 10px;font-size:11px;text-align:left;white-space:nowrap}}
  td{{padding:7px 10px;font-size:12px;border-bottom:1px solid #f0f0f0;vertical-align:middle}}
  tr:hover{{background:#fafafa}}
  .bar-wrap{{background:#eee;border-radius:4px;height:16px;width:180px}}
  .bar-fill{{height:16px;border-radius:4px;color:#fff;font-size:10px;
             line-height:16px;padding-left:5px;min-width:30px;font-weight:700}}
  .reason{{color:#666;font-size:11px;max-width:240px}}
  .footer{{text-align:center;padding:28px;color:#aaa;font-size:11px}}
</style>
</head>
<body>

<div class="hero">
  <h1>⚡ EcoCharge Jeonbuk AI</h1>
  <p>전북특별자치도 수소·전기차 충전 인프라 최적 입지 추천 플랫폼</p>
  <p style="margin-top:6px;font-size:13px">2026 전북특별자치도 공공데이터 AI 활용 창업경진대회</p>
</div>

<div class="kpi-bar">
  <div class="kpi"><div class="val">{int(scored['ev_count'].sum()):,}</div><div class="lbl">전북 전기차 등록(대)</div></div>
  <div class="kpi"><div class="val">{int(scored['tourism_count'].sum())}</div><div class="lbl">분석 관광지(개소)</div></div>
  <div class="kpi"><div class="val">{int(scored['industry_firms'].sum()):,}</div><div class="lbl">산업단지 업체(개)</div></div>
  <div class="kpi"><div class="val">14</div><div class="lbl">분석 시군 수</div></div>
  <div class="kpi"><div class="val">5</div><div class="lbl">정책 시나리오</div></div>
  <div class="kpi"><div class="val">{scored.iloc[0]['sigungu']}</div><div class="lbl">ESS 1순위 시군</div></div>
</div>

<div class="container">

<!-- STEP 1 -->
<div class="card">
  <div class="card-hdr">
    <span class="step-num">STEP 1</span>
    <span class="step-title">데이터 통합</span>
    <span class="step-desc">전기차·관광지·산업단지·버스정류장 공공데이터를 시군 단위로 통합</span>
  </div>
  <div class="chart-grid">
    <div class="chart-box"><canvas id="c1a"></canvas></div>
    <div class="chart-box"><canvas id="c1b"></canvas></div>
  </div>
</div>

<!-- STEP 2 -->
<div class="card">
  <div class="card-hdr">
    <span class="step-num">STEP 2</span>
    <span class="step-title">충전 수요 예측</span>
    <span class="step-desc">현재 EV 수요 + 관광·산업 잠재 수요 결합</span>
  </div>
  <div class="chart-grid">
    <div class="chart-box"><canvas id="c2a"></canvas></div>
    <div class="chart-box"><canvas id="c2b"></canvas></div>
  </div>
</div>

<!-- STEP 3 -->
<div class="card">
  <div class="card-hdr">
    <span class="step-num">STEP 3</span>
    <span class="step-title">충전 공급 사각지대 분석</span>
    <span class="step-desc">기존 충전 인프라 공백 점수 → 우선 개선 지역 탐지</span>
  </div>
  <div class="chart-grid">
    <div class="chart-box"><canvas id="c3a"></canvas></div>
    <div class="chart-box"><canvas id="c3b"></canvas></div>
  </div>
</div>

<!-- STEP 4 -->
<div class="card">
  <div class="card-hdr">
    <span class="step-num">STEP 4</span>
    <span class="step-title">ESS 입지 적합성 점수</span>
    <span class="step-desc">5개 차원 가중합 → EcoCharge Suitability Score 산출</span>
  </div>
  <div class="chart-grid">
    <div class="chart-box tall"><canvas id="c4a"></canvas></div>
    <div class="chart-box tall"><canvas id="c4b"></canvas></div>
  </div>
</div>

<!-- STEP 5 -->
<div class="card">
  <div class="card-hdr">
    <span class="step-num">STEP 5</span>
    <span class="step-title">정책 시나리오 시뮬레이션</span>
    <span class="step-desc">5가지 시나리오별 우선순위 변화 비교</span>
  </div>
  <div class="chart-grid">
    <div class="chart-box tall"><canvas id="c5a"></canvas></div>
    <div class="chart-box tall"><canvas id="c5b"></canvas></div>
  </div>
</div>

<!-- STEP 6 -->
<div class="card">
  <div class="card-hdr">
    <span class="step-num">STEP 6</span>
    <span class="step-title">AI 리포트 — 최종 입지 추천</span>
    <span class="step-desc">ESS 구성 분해 + 설명 가능 AI 추천 이유</span>
  </div>
  <div class="chart-grid">
    <div class="chart-box tall"><canvas id="c6a"></canvas></div>
    <div class="chart-box tall"><canvas id="c6b"></canvas></div>
  </div>
</div>

<!-- 순위표 -->
<div class="card">
  <div class="card-hdr">
    <span class="step-num">📋</span>
    <span class="step-title">ESS 종합 순위표</span>
    <span class="step-desc">AI 추천 이유 포함 전체 시군 순위</span>
  </div>
  <div style="padding:16px;overflow-x:auto">
  <table>
    <thead><tr>
      <th>순위</th><th>시군</th><th>ESS 점수</th>
      <th>전기차(30%)</th><th>관광(25%)</th><th>산업(20%)</th>
      <th>버스(15%)</th><th>공백(10%)</th><th>AI 추천 이유</th>
    </tr></thead>
    <tbody>{table_rows}</tbody>
  </table>
  </div>
</div>

</div><!-- container -->
<div class="footer">EcoCharge Jeonbuk AI · 전북특별자치도 공공데이터 기반 충전 인프라 입지 분석 · 2026</div>

<script>
const L  = {json.dumps(labels, ensure_ascii=False)};
const EV = {json.dumps(ev)};
const TU = {json.dumps(tourism)};
const IN = {json.dumps(industry)};
const BU = {json.dumps(bus)};
const ES = {json.dumps(ess)};
const sEV  = {json.dumps(s_ev)};
const sTU  = {json.dumps(s_tour)};
const sIN  = {json.dumps(s_ind)};
const sBU  = {json.dumps(s_bus)};
const sGAP = {json.dumps(s_gap)};
const CL   = {json.dumps(colors)};
const SN   = {json.dumps(snames, ensure_ascii=False)};
const SD   = {json.dumps(scenario_data, ensure_ascii=False)};
const lineDS = {line_datasets};

const def_bar = (label,data,bg)=>{{return{{label,data,backgroundColor:bg,borderRadius:4}}}};
const hbar = (ctx,labels,datasets,title)=>new Chart(ctx,{{
  type:'bar',
  data:{{labels,datasets}},
  options:{{indexAxis:'y',responsive:true,maintainAspectRatio:false,
    plugins:{{legend:{{display:datasets.length>1}},title:{{display:true,text:title,font:{{size:12}}}}}},
    scales:{{x:{{grid:{{color:'#f0f0f0'}}}},y:{{ticks:{{font:{{size:10}}}}}}}}}}
}});
const vbar = (ctx,labels,datasets,title)=>new Chart(ctx,{{
  type:'bar',
  data:{{labels,datasets}},
  options:{{responsive:true,maintainAspectRatio:false,
    plugins:{{legend:{{display:datasets.length>1}},title:{{display:true,text:title,font:{{size:12}}}}}},
    scales:{{y:{{grid:{{color:'#f0f0f0'}}}},x:{{ticks:{{font:{{size:9}},maxRotation:40}}}}}}}}
}});

// STEP1
hbar(document.getElementById('c1a').getContext('2d'),
  L,[def_bar('전기차 등록 대수',EV,'#3498db')],'전기차 등록 대수 (대)');
hbar(document.getElementById('c1b').getContext('2d'),
  L,[def_bar('관광지 수',TU,'#8e44ad')],'관광지 수 (개소)');

// STEP2
vbar(document.getElementById('c2a').getContext('2d'), L,
  [def_bar('전기차 수요',sEV,'#3498db88'),
   def_bar('관광 잠재수요',sTU,'#8e44ad88'),
   def_bar('산업 잠재수요',sIN,'#e67e2288')],
  '시군별 충전 수요 구성 (점수)');
vbar(document.getElementById('c2b').getContext('2d'), L,
  [def_bar('버스정류장 이용량',BU,'#27ae6088'),
   def_bar('산업단지 업체수',IN,'#e67e2288')],
  '교통·산업 접근성 지표');

// STEP3
const gapSorted = [...L.map((l,i)=>{{return{{l,g:sGAP[i]}}}})]
  .sort((a,b)=>b.g-a.g);
vbar(document.getElementById('c3a').getContext('2d'),
  gapSorted.map(x=>x.l),
  [{{label:'충전 공백 점수',
    data:gapSorted.map(x=>x.g),
    backgroundColor:gapSorted.map(x=>x.g>60?'#c0392b':x.g>40?'#e67e22':'#27ae60'),
    borderRadius:4}}],
  '시군별 충전 인프라 공백 점수 (높을수록 사각지대)');
const latent = sTU.map((t,i)=>+(t*0.5+sIN[i]*0.3+sBU[i]*0.2).toFixed(1));
new Chart(document.getElementById('c3b').getContext('2d'),{{
  type:'scatter',
  data:{{datasets:[{{
    label:'시군',
    data:sEV.map((e,i)=>{{return{{x:e,y:latent[i],label:L[i]}}}}),
    backgroundColor:CL,
    pointRadius:8,
  }}]}},
  options:{{responsive:true,maintainAspectRatio:false,
    plugins:{{legend:{{display:false}},title:{{display:true,text:'현재 수요 vs 잠재 수요 분포',font:{{size:12}}}},
      tooltip:{{callbacks:{{label:c=>c.raw.label+' ('+c.raw.x.toFixed(0)+', '+c.raw.y.toFixed(0)+')'}}}}}},
    scales:{{
      x:{{title:{{display:true,text:'현재 EV 수요 점수'}}}},
      y:{{title:{{display:true,text:'잠재 수요 점수'}}}}
    }}}}
}});

// STEP4
vbar(document.getElementById('c4a').getContext('2d'), L,
  [{{label:'ESS 종합 점수',data:ES,backgroundColor:CL,borderRadius:4}}],
  'EcoCharge Suitability Score 순위');
const top5L = L.slice(0,5);
new Chart(document.getElementById('c4b').getContext('2d'),{{
  type:'bar',
  data:{{labels:top5L,
    datasets:[
      {{label:'전기차(30%)',data:sEV.slice(0,5).map(v=>+(v*0.3).toFixed(1)),backgroundColor:'#3498db88',borderRadius:2}},
      {{label:'관광(25%)', data:sTU.slice(0,5).map(v=>+(v*0.25).toFixed(1)),backgroundColor:'#8e44ad88',borderRadius:2}},
      {{label:'산업(20%)', data:sIN.slice(0,5).map(v=>+(v*0.20).toFixed(1)),backgroundColor:'#e67e2288',borderRadius:2}},
      {{label:'버스(15%)', data:sBU.slice(0,5).map(v=>+(v*0.15).toFixed(1)),backgroundColor:'#27ae6088',borderRadius:2}},
      {{label:'공백(10%)', data:sGAP.slice(0,5).map(v=>+(v*0.10).toFixed(1)),backgroundColor:'#e74c3c88',borderRadius:2}},
    ]}},
  options:{{responsive:true,maintainAspectRatio:false,scales:{{x:{{stacked:true}},y:{{stacked:true}}}},
    plugins:{{legend:{{position:'bottom',labels:{{font:{{size:10}}}}}},
      title:{{display:true,text:'상위 5개 시군 ESS 구성 요소 분해',font:{{size:12}}}}}}}}
}});

// STEP5 — 시나리오별 순위 히트맵 (막대로 대체)
const scenarioESS = SN.map(sn=>L.map(l=>SD[sn][l]));
new Chart(document.getElementById('c5a').getContext('2d'),{{
  type:'bar',
  data:{{labels:L,
    datasets:SN.map((sn,i)=>{{
      const colors2=['#c0392b','#e67e22','#f1c40f','#27ae60','#2980b9'];
      return{{label:sn,data:scenarioESS[i],backgroundColor:colors2[i]+'99',borderRadius:2}};
    }})}},
  options:{{responsive:true,maintainAspectRatio:false,
    plugins:{{legend:{{position:'bottom',labels:{{font:{{size:9}}}}}},
      title:{{display:true,text:'시나리오별 시군 ESS 비교',font:{{size:12}}}}}},
    scales:{{x:{{ticks:{{font:{{size:9}},maxRotation:40}}}},y:{{max:100}}}}}}
}});
new Chart(document.getElementById('c5b').getContext('2d'),{{
  type:'line',
  data:{{labels:SN,datasets:lineDS}},
  options:{{responsive:true,maintainAspectRatio:false,
    plugins:{{legend:{{position:'bottom'}},
      title:{{display:true,text:'상위 3개 시군 — 시나리오별 ESS 변화',font:{{size:12}}}}}},
    scales:{{x:{{ticks:{{font:{{size:9}}}}}},y:{{min:0,max:100}}}}}}
}});

// STEP6
new Chart(document.getElementById('c6a').getContext('2d'),{{
  type:'bar',
  data:{{labels:top5L,
    datasets:[
      {{label:'전기차 수요', data:sEV.slice(0,5),backgroundColor:'#3498db',borderRadius:3}},
      {{label:'관광 수요',   data:sTU.slice(0,5),backgroundColor:'#8e44ad',borderRadius:3}},
      {{label:'산업 수요',   data:sIN.slice(0,5),backgroundColor:'#e67e22',borderRadius:3}},
      {{label:'버스 접근',   data:sBU.slice(0,5),backgroundColor:'#27ae60',borderRadius:3}},
      {{label:'충전 공백',   data:sGAP.slice(0,5),backgroundColor:'#e74c3c',borderRadius:3}},
    ]}},
  options:{{responsive:true,maintainAspectRatio:false,
    plugins:{{legend:{{position:'bottom',labels:{{font:{{size:10}}}}}},
      title:{{display:true,text:'상위 5개 시군 5차원 점수 비교 (100점 만점)',font:{{size:12}}}}}},
    scales:{{y:{{max:100}}}}}}
}});
vbar(document.getElementById('c6b').getContext('2d'),L.slice().reverse(),
  [{{label:'ESS 최종 점수',data:ES.slice().reverse(),
    backgroundColor:CL.slice().reverse(),borderRadius:4}}],
  '전체 시군 ESS 최종 순위');

</script>
</body>
</html>"""


if __name__ == "__main__":
    print("1/3  데이터 로딩 및 점수 산출 중...", flush=True)
    master = build_master()
    scored = add_reasons(compute_suitability(master))
    print("2/3  HTML 리포트 조립 중...", flush=True)
    html = build_html(master, scored)
    print(f"3/3  파일 저장 중...", flush=True)
    OUTPUT.write_text(html, encoding="utf-8")
    print(f"\n완료: {OUTPUT}", flush=True)
    import webbrowser
    webbrowser.open(str(OUTPUT))
