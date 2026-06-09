"""EcoCharge Jeonbuk — 데이터 로딩 모듈."""

import os
import pandas as pd
import numpy as np
from config import FILES, SIGUNGU_CENTERS, SIGUNGU_AREA_KM2


# ── 전기차 등록 현황 ──────────────────────────────────────────────────────────

def load_ev() -> pd.DataFrame:
    """시군별 전기차 등록 대수 (EV 수요 지표)."""
    df = pd.read_csv(FILES["ev"], encoding="cp949")
    df.columns = df.columns.str.strip()
    df["대수"] = pd.to_numeric(df["대수"], errors="coerce").fillna(0)
    agg = df.groupby("시군", as_index=False)["대수"].sum()
    agg.columns = ["sigungu", "ev_count"]
    return agg


# ── 산업단지 현황 ─────────────────────────────────────────────────────────────

def load_industry() -> pd.DataFrame:
    """시군별 산업단지 입주업체 수·면적 (산업 수요 지표).

    원본의 시군명은 '군산', '익산' 등 접미사 없는 형태 →
    SIGUNGU_CENTERS 키(군산시, 익산시…)로 변환.
    """
    df = pd.read_csv(FILES["industry"], encoding="cp949")
    df.columns = df.columns.str.strip()
    df["입주업체 수"] = pd.to_numeric(df["입주업체 수"], errors="coerce").fillna(0)
    df["관리 면적"]  = pd.to_numeric(df["관리 면적"],  errors="coerce").fillna(0)

    def _normalize(name: str) -> str:
        name = str(name).strip()
        for sg in SIGUNGU_CENTERS:
            # "군산시".startswith("군산") or "완주군".startswith("완주")
            base = sg.rstrip("시군")
            if name == base or name == sg:
                return sg
        return name   # 매칭 실패 시 원본 유지

    df["sigungu"] = df["시군명"].apply(_normalize)
    agg = df.groupby("sigungu", as_index=False).agg(
        industry_firms=("입주업체 수", "sum"),
        industry_area_ha=("관리 면적", "sum"),
    )
    return agg


# ── 관광지 위치정보 ───────────────────────────────────────────────────────────

def load_tourism() -> pd.DataFrame:
    """관광지별 위경도 좌표 (GPS 포함, 직접 사용 가능)."""
    df = pd.read_csv(FILES["tourism"], encoding="cp949", low_memory=False)
    df.columns = df.columns.str.strip()
    df = df.rename(columns={"관광지명": "name", "주소": "address", "위도": "lat", "경도": "lon"})
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["lon"] = pd.to_numeric(df["lon"], errors="coerce")
    df = df.dropna(subset=["lat", "lon"])

    # 시군 추출 (주소 2번째 토큰: "전북전주시..." → "전주시")
    def _extract_sigungu(addr: str) -> str:
        addr = str(addr).replace("전북", "").replace("전라북도", "").replace("전북특별자치도", "")
        for sg in SIGUNGU_CENTERS:
            if sg in addr:
                return sg
        return "기타"

    df["sigungu"] = df["address"].apply(_extract_sigungu)
    return df.reset_index(drop=True)


def load_tourism_by_sigungu() -> pd.DataFrame:
    """시군별 관광지 수 집계."""
    df = load_tourism()
    return df.groupby("sigungu", as_index=False).size().rename(columns={"size": "tourism_count"})


# ── 버스정류장 이용 현황 ──────────────────────────────────────────────────────

def load_bus() -> pd.DataFrame:
    """최다 이용 버스정류장 — 지역별 총 이용인원."""
    df = pd.read_csv(FILES["bus"], encoding="cp949")
    df.columns = df.columns.str.strip()
    df["총 이용인원"] = pd.to_numeric(df["총 이용인원"], errors="coerce").fillna(0)

    def _map_sigungu(region: str) -> str:
        region = str(region)
        for sg in SIGUNGU_CENTERS:
            if sg.replace("시", "").replace("군", "") in region or sg in region:
                return sg
        return "기타"

    df["sigungu"] = df["지역"].apply(_map_sigungu)
    agg = df.groupby("sigungu", as_index=False)["총 이용인원"].sum()
    agg.columns = ["sigungu", "bus_usage"]
    return agg


# ── OSM 기존 충전소 ───────────────────────────────────────────────────────────

def load_existing_chargers_osm(timeout_sec: int = 5) -> pd.DataFrame:
    """OpenStreetMap에서 전북 전기차 충전소 POI 조회.

    캐시 파일이 없으면 Overpass API를 호출한다.
    timeout_sec 이내에 응답 없으면 빈 DataFrame 반환.
    """
    from config import OSM_CACHE
    import threading

    if OSM_CACHE.exists():
        try:
            import geopandas as gpd
            gdf = gpd.read_file(OSM_CACHE)
            pts = gdf[gdf.geometry.geom_type == "Point"]
            return pd.DataFrame({"lat": pts.geometry.y.values, "lon": pts.geometry.x.values}).dropna()
        except Exception:
            pass

    if os.environ.get("SKIP_OSM"):
        return pd.DataFrame(columns=["lat", "lon"])

    result_holder: list[pd.DataFrame] = []

    def _fetch():
        try:
            import osmnx as ox
            # 전북 대략 경계 bbox (south, north, west, east)
            gdf = ox.features_from_bbox(
                bbox=(35.0, 36.3, 126.3, 127.9),
                tags={"amenity": "charging_station"},
            )
            gdf.to_file(OSM_CACHE, driver="GeoJSON")
            pts = gdf[gdf.geometry.geom_type == "Point"]
            result_holder.append(
                pd.DataFrame({"lat": pts.geometry.y.values, "lon": pts.geometry.x.values})
            )
        except Exception as e:
            print(f"[주의] OSM fetch 실패: {type(e).__name__}")

    t = threading.Thread(target=_fetch, daemon=True)
    t.start()
    t.join(timeout=timeout_sec)

    if result_holder:
        return result_holder[0].dropna().reset_index(drop=True)

    print("[주의] OSM 충전소 조회 실패/타임아웃 - gap 점수 기본값 사용")
    return pd.DataFrame(columns=["lat", "lon"])


# ── 통합 마스터 테이블 ────────────────────────────────────────────────────────

def build_master() -> pd.DataFrame:
    """시군별 모든 지표를 하나의 DataFrame으로 통합."""
    sigungu_list = list(SIGUNGU_CENTERS.keys())
    master = pd.DataFrame({"sigungu": sigungu_list})

    # 위경도
    master["lat"] = master["sigungu"].map(lambda s: SIGUNGU_CENTERS[s][0])
    master["lon"] = master["sigungu"].map(lambda s: SIGUNGU_CENTERS[s][1])
    master["area_km2"] = master["sigungu"].map(SIGUNGU_AREA_KM2)

    # 각 지표 병합
    for df in [load_ev(), load_industry(), load_tourism_by_sigungu(), load_bus()]:
        master = master.merge(df, on="sigungu", how="left")

    master = master.fillna(0)

    # 밀도 파생 변수
    master["ev_per_km2"]      = master["ev_count"]      / master["area_km2"]
    master["tourism_per_km2"] = master["tourism_count"]  / master["area_km2"]

    # 기존 충전소까지 최단 거리 (OSM, 실패 시 모두 max)
    chargers = load_existing_chargers_osm()
    if not chargers.empty:
        from scipy.spatial import cKDTree
        tree = cKDTree(chargers[["lat", "lon"]].values)
        coords = master[["lat", "lon"]].values
        dists, _ = tree.query(coords, k=1)
        master["nearest_charger_deg"] = dists
    else:
        master["nearest_charger_deg"] = 0.5   # 약 55km, 충전소 완전 공백 가정

    return master
