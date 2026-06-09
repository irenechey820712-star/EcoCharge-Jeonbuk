"""EcoCharge Suitability Score 산출 모듈.

각 시군구에 대해 5개 차원의 점수를 0~100으로 정규화한 뒤
config.WEIGHTS 가중합으로 최종 점수를 계산한다.
"""

import numpy as np
import pandas as pd
from config import WEIGHTS


# ── 정규화 헬퍼 ───────────────────────────────────────────────────────────────

def _minmax(series: pd.Series) -> pd.Series:
    """0~100 Min-Max 정규화."""
    lo, hi = series.min(), series.max()
    if hi == lo:
        return pd.Series(50.0, index=series.index)
    return (series - lo) / (hi - lo) * 100


# ── 개별 점수 산출 ────────────────────────────────────────────────────────────

def score_ev_demand(master: pd.DataFrame) -> pd.Series:
    """전기차 밀도 기반 수요 점수.

    km² 당 등록 대수가 높을수록 현재 충전 수요가 높음.
    단, 농촌·관광지의 잠재 수요를 놓치지 않도록
    절대 대수(ev_count)와 밀도(ev_per_km2)를 5:5 혼합.
    """
    density_score  = _minmax(master["ev_per_km2"])
    absolute_score = _minmax(master["ev_count"])
    return (density_score * 0.5 + absolute_score * 0.5).rename("score_ev")


def score_tourism(master: pd.DataFrame) -> pd.Series:
    """관광지 수 기반 잠재 수요 점수.

    외지 방문객이 많은 관광지 밀집 지역은
    장거리 이동 후 충전 수요가 높음.
    """
    return _minmax(master["tourism_count"]).rename("score_tourism")


def score_industry(master: pd.DataFrame) -> pd.Series:
    """산업단지 규모 기반 수요 점수.

    입주업체 수와 단지 면적을 균등 반영.
    상용차·출퇴근 차량의 정기 충전 수요를 반영.
    """
    firms_score = _minmax(master["industry_firms"])
    area_score  = _minmax(master["industry_area_ha"])
    return (firms_score * 0.6 + area_score * 0.4).rename("score_industry")


def score_bus_access(master: pd.DataFrame) -> pd.Series:
    """버스정류장 이용량 기반 접근성 점수.

    대중교통 이용이 많은 거점은 교통 접근성이 높음 →
    충전소 설치 후 이용률도 높을 가능성이 큼.
    """
    return _minmax(master["bus_usage"]).rename("score_bus")


def score_gap(master: pd.DataFrame) -> pd.Series:
    """기존 충전소 공백 점수.

    가장 가까운 기존 충전소까지 거리가 멀수록
    신규 설치 필요도가 높음 → 높은 점수.
    """
    return _minmax(master["nearest_charger_deg"]).rename("score_gap")


# ── 종합 점수 계산 ────────────────────────────────────────────────────────────

def compute_suitability(master: pd.DataFrame) -> pd.DataFrame:
    """EcoCharge Suitability Score 전체 파이프라인.

    Returns
    -------
    master DataFrame에 개별 점수와 종합 점수(ess)를 추가한 사본.
    """
    result = master.copy()

    result["score_ev"]       = score_ev_demand(master).values
    result["score_tourism"]  = score_tourism(master).values
    result["score_industry"] = score_industry(master).values
    result["score_bus"]      = score_bus_access(master).values
    result["score_gap"]      = score_gap(master).values

    result["ess"] = (
        result["score_ev"]       * WEIGHTS["ev_demand"]  +
        result["score_tourism"]  * WEIGHTS["tourism"]    +
        result["score_industry"] * WEIGHTS["industry"]   +
        result["score_bus"]      * WEIGHTS["bus_access"] +
        result["score_gap"]      * WEIGHTS["gap"]
    ).round(1)

    result["rank"] = result["ess"].rank(ascending=False, method="min").astype(int)
    result = result.sort_values("ess", ascending=False).reset_index(drop=True)
    return result


# ── 추천 이유 생성 (설명 가능 AI) ────────────────────────────────────────────

def generate_reason(row: pd.Series) -> str:
    """후보지 추천 이유를 자연어로 생성."""
    reasons = []

    if row["score_ev"] >= 70:
        reasons.append(f"전기차 등록 밀도 상위권 (점수 {row['score_ev']:.0f}/100)")
    elif row["score_ev"] >= 40:
        reasons.append(f"전기차 수요 중간 수준 (점수 {row['score_ev']:.0f}/100)")

    if row["score_tourism"] >= 60:
        reasons.append(f"관광지 밀집 - 외지 방문객 충전 수요 높음 (점수 {row['score_tourism']:.0f}/100)")

    if row["score_industry"] >= 60:
        reasons.append(f"산업단지 집중 - 상용차·출퇴근 충전 수요 발생 (점수 {row['score_industry']:.0f}/100)")

    if row["score_bus"] >= 60:
        reasons.append(f"버스 거점 이용량 높음 - 교통 접근성 우수 (점수 {row['score_bus']:.0f}/100)")

    if row["score_gap"] >= 70:
        reasons.append(f"기존 충전소 공백 지역 - 신규 설치 필요도 높음 (점수 {row['score_gap']:.0f}/100)")

    if not reasons:
        reasons.append("복합 지표 중간 수준 - 균형적 설치 고려 필요")

    return " · ".join(reasons)


def add_reasons(scored: pd.DataFrame) -> pd.DataFrame:
    """scored DataFrame에 추천 이유 열 추가."""
    scored = scored.copy()
    scored["reason"] = scored.apply(generate_reason, axis=1)
    return scored


# ── 시나리오 재가중치 ─────────────────────────────────────────────────────────

SCENARIOS = {
    "기본 균형":       {"ev_demand": 0.30, "tourism": 0.25, "industry": 0.20, "bus_access": 0.15, "gap": 0.10},
    "관광 우선":       {"ev_demand": 0.15, "tourism": 0.45, "industry": 0.10, "bus_access": 0.15, "gap": 0.15},
    "산업단지 우선":   {"ev_demand": 0.20, "tourism": 0.10, "industry": 0.45, "bus_access": 0.15, "gap": 0.10},
    "충전 사각지대 해소": {"ev_demand": 0.15, "tourism": 0.15, "industry": 0.10, "bus_access": 0.10, "gap": 0.50},
    "대중교통 연계":   {"ev_demand": 0.20, "tourism": 0.20, "industry": 0.15, "bus_access": 0.40, "gap": 0.05},
}


def apply_scenario(master: pd.DataFrame, scenario_name: str) -> pd.DataFrame:
    """시나리오별 가중치를 적용해 점수 재산출."""
    w = SCENARIOS[scenario_name]
    result = master.copy()

    for key in ["score_ev", "score_tourism", "score_industry", "score_bus", "score_gap"]:
        if key not in result.columns:
            result = compute_suitability(master)
            break

    result["ess"] = (
        result["score_ev"]       * w["ev_demand"]  +
        result["score_tourism"]  * w["tourism"]    +
        result["score_industry"] * w["industry"]   +
        result["score_bus"]      * w["bus_access"] +
        result["score_gap"]      * w["gap"]
    ).round(1)

    result["rank"] = result["ess"].rank(ascending=False, method="min").astype(int)
    return result.sort_values("ess", ascending=False).reset_index(drop=True)
