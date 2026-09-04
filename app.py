
import streamlit as st
import pandas as pd
import numpy as np
import geopandas as gpd
import plotly.graph_objects as go

st.set_page_config(page_title="학생수 감소 조기진단", layout="wide")

THREE = ["대전", "대구", "부산"]
SIDO_FULL = {"대전": "대전광역시", "대구": "대구광역시", "부산": "부산광역시"}
GRADE_COLORS = {1: "#7f1d1d", 2: "#dc2626", 3: "#f97316", 4: "#fbbf24", 5: "#7dd3fc"}

# 1~2등급은 확실히 크게, 3~5등급도 색이 흐려서 안 보이던 문제 해결 위해 최소 크기/투명도 상향
GRADE_SIZE = {1: 16, 2: 13, 3: 10, 4: 9, 5: 8}
GRADE_OPACITY = {1: 1.0, 2: 0.95, 3: 0.8, 4: 0.75, 5: 0.7}

# 유형별 배지 색상 — 순전출형은 파란 계열, 인구감소형은 빨간 계열, 비위험은 회색
TYPE_STYLE = {
    "순전출형": {"bg": "#dbeafe", "fg": "#1e40af"},
    "인구감소형": {"bg": "#fee2e2", "fg": "#991b1b"},
    "비위험": {"bg": "#f3f4f6", "fg": "#374151"},
}


def type_badge(유형):
    style = TYPE_STYLE.get(유형, TYPE_STYLE["비위험"])
    return (
        f"<span style='background-color:{style['bg']}; color:{style['fg']}; "
        f"padding:4px 12px; border-radius:6px; font-weight:600; font-size:0.95rem;'>"
        f"{유형}</span>"
    )


def pin_polygon(lon, lat, size_deg=0.015, n=24):
    """지도 위경도 기준 핀(물방울) 모양 폴리곤 좌표를 만든다. 뾰족한 끝이 정확히 학교 위치(lon, lat)."""
    head_lat = lat + size_deg * 1.4
    angles = np.linspace(np.radians(200), np.radians(-20), n)
    arc_lon = lon + size_deg * np.cos(angles)
    arc_lat = head_lat + size_deg * np.sin(angles)
    coords = list(zip(arc_lon, arc_lat)) + [(lon, lat), (arc_lon[0], arc_lat[0])]
    return coords


@st.cache_data
def load_data():
    return pd.read_csv("school_dashboard.csv")


@st.cache_data
def load_boundary():
    sgg = gpd.read_parquet("assets/sgg.parquet").to_crs(epsg=4326)
    sgg3 = sgg[sgg["sidonm"].isin(SIDO_FULL.values())].reset_index(drop=True)
    return sgg3, sgg3.__geo_interface__


df = load_data()
sgg3, geojson = load_boundary()
df_map = df[df["시도"].isin(THREE)].dropna(subset=["위도", "경도"]).copy()

st.title("🏫 학생수 감소 조기진단")
st.caption("학교명을 검색하거나, 지도 위 점을 클릭하면 오른쪽에 상세정보가 뜹니다")

query = st.text_input("학교명 검색 (예: 대구명곡초)")

matched = pd.DataFrame()
center_lat, center_lon, zoom_level = 36.0, 128.3, 6.3

if query:
    matched = df_map[df_map["학교명"].str.contains(query, na=False)].reset_index(drop=True)
    if len(matched) == 0:
        st.warning("검색 결과 없음")
    else:
        center_lat = float(matched.iloc[0]["위도"])
        center_lon = float(matched.iloc[0]["경도"])
        zoom_level = 13

map_col, info_col = st.columns([7, 3])

with map_col:
    fig = go.Figure()

    fig.add_trace(go.Choroplethmap(
        geojson=geojson, locations=sgg3.index, z=[0] * len(sgg3),
        colorscale=[[0, "white"], [1, "white"]], showscale=False,
        marker=dict(opacity=0.3, line=dict(width=1, color="#9ca3af")),
    ))

    trace_refs = [None]

    # 낮은 등급(5→1 순)부터 그려서, 위험도가 높을수록 항상 위에 겹쳐 보이게 함
    for g in sorted(GRADE_COLORS, reverse=True):
        color = GRADE_COLORS[g]
        sub = df_map[df_map["등급"] == g].reset_index(drop=True)
        trace_refs.append(sub)
        fig.add_trace(go.Scattermap(
            lat=sub["위도"], lon=sub["경도"], mode="markers",
            marker=dict(size=GRADE_SIZE[g], color=color, opacity=GRADE_OPACITY[g]),
            text=sub["학교명"],
            hoverinfo="text", name=f"{g}등급",
        ))

    # 검색된 학교 — 진짜 핀(물방울) 모양 다각형. 색은 그 학교의 등급 색 그대로.
    if len(matched) > 0:
        for i, m_row in matched.iterrows():
            coords = pin_polygon(float(m_row["경도"]), float(m_row["위도"]), size_deg=0.004)
            pin_geojson = {
                "type": "FeatureCollection",
                "features": [{
                    "type": "Feature", "id": 0,
                    "geometry": {"type": "Polygon", "coordinates": [coords]},
                    "properties": {},
                }],
            }
            g = int(m_row["등급"])
            fig.add_trace(go.Choroplethmap(
                geojson=pin_geojson, locations=[0], z=[1],
                colorscale=[[0, GRADE_COLORS[g]], [1, GRADE_COLORS[g]]], showscale=False,
                marker=dict(opacity=1.0, line=dict(width=1.5, color="white")),
                hovertext=m_row["학교명"] + " (검색됨)", hoverinfo="text",
                name="검색 결과",
            ))
            trace_refs.append(pd.DataFrame([m_row]))  # 핀 트레이스도 클릭하면 정보 뜨게 등록

    fig.update_layout(
        map=dict(style="carto-positron", center=dict(lat=center_lat, lon=center_lon), zoom=zoom_level),
        height=650, margin=dict(l=0, r=0, t=10, b=0),
        showlegend=False,
    )

    event = st.plotly_chart(
        fig, use_container_width=True, on_select="rerun",
        selection_mode="points", key="risk_map",
    )

with info_col:
    clicked_row = None
    if event and event.selection and event.selection["points"]:
        try:
            point = event.selection["points"][0]
            curve_idx = point["curve_number"]
            point_idx = point.get("point_index", 0)  # 핀(폴리곤) 트레이스는 point_index가 없을 수 있어 기본값 처리
            ref_df = trace_refs[curve_idx]
            if ref_df is not None and point_idx < len(ref_df):
                clicked_row = ref_df.iloc[point_idx]
        except (KeyError, IndexError):
            clicked_row = None  # 핀 클릭 이벤트 형식이 달라 못 읽어도 앱이 죽지 않게

    display_row = clicked_row if clicked_row is not None else (matched.iloc[0] if len(matched) > 0 else None)

    if display_row is not None:
        r = display_row
        st.subheader(f"📍 {r['학교명']}")

        badge_col1, badge_col2 = st.columns(2)
        with badge_col1:
            color = "🔴" if r["등급"] <= 2 else "🟡" if r["등급"] == 3 else "🔵"
            st.metric("위험등급", f"{color} {int(r['등급'])}등급")
        with badge_col2:
            st.write("유형")
            st.markdown(type_badge(r["유형"]), unsafe_allow_html=True)

        st.write(f"**위치**: {r['시도']} {r['행정구']}")
        st.write(f"**학교급**: {r['학교급']}")
        st.write(f"**학생수**: {int(r['n0'])}명")
        st.write(f"**예측 변화**: {r['y']*100:.1f}%")
    else:
        st.info("지도 위 점을 클릭하거나\n학교명을 검색해보세요")
        st.write(f"전체 등록 학교 수(3개 시): {len(df_map):,}개교")
