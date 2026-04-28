"""
extract_transport.py - GTFS transport frequency scoring for Sydney suburbs.

Data source
-----------
TfNSW GTFS Timetables (Full) dataset, obtained from
    https://opendata.transport.nsw.gov.au/data/dataset/timetables-complete-gtfs

Static timetables, stop locations, and route shape information in General
Transit Feed Specification (GTFS) format for all operators (train, bus, metro,
light rail, ferry) across NSW. Downloaded once and cached locally; this script
consumes the unzipped files from data/raw/transport/.

License: Creative Commons Attribution 4.0 (CC-BY-4.0).

Methodology
-----------
For every suburb defined in data/raw/arcgis/suburbs.geojson (filtered to
Greater Sydney via centroid bounding box):

1. Spatially join GTFS stops against the suburb polygon (WGS84, EPSG:4326)
   using geopandas `within` predicate. No coordinates are hardcoded.

2. For each stop, count the number of departures in the weekday peak window
   (Mon-Fri, 07:00-09:00). Weekday services are identified via calendar.txt.

3. Services-per-hour at a stop = peak_event_count / peak_window_hours.

4. Aggregate to suburb level by taking the mean services-per-hour across all
   stops within each suburb polygon.

5. Normalise to a 0-1 score relative to the best-served suburb in scope, so
   that the top suburb scores 1.0. This is a within-pool comparison, not a
   city-wide absolute index.

Output
------
data/processed/transport_scores.json:

    {
      "Newtown": {"transport_score": 0.91, "avg_services_per_hour": 14.2, "stop_count": 8},
      ...
    }

Consumed downstream by `/api/civic` and by `ingest_transport.py` which writes
these rows into the `transport_scores` PostgreSQL table.

Usage
-----
    python data_extraction/extract_transport.py
"""
from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import pandas as pd

# ---- Paths ----
REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = REPO_ROOT / "data" / "raw" / "transport"
PROCESSED_DIR = REPO_ROOT / "data" / "processed"
SUBURBS_FILE = REPO_ROOT / "data" / "raw" / "arcgis" / "suburbs.geojson"
OUTPUT_FILE = PROCESSED_DIR / "transport_scores.json"

# ---- Configuration ----
SUBURB_COL = "SAL_NAME21"            # ABS SAL 2021 name column
PEAK_HOURS = range(7, 9)             # 07:00-08:59 weekday commuter window
PEAK_WINDOW_HOURS = len(list(PEAK_HOURS))
CHUNK_SIZE = 100_000                 # pandas chunksize for stop_times.txt

# Greater Sydney bounding box (covers Sydney metro inc. Blue Mountains, Central
# Coast fringe, Sutherland, Penrith, Hawkesbury). Filters out regional NSW
# (Newcastle, Wollongong, Albury, Dubbo, etc).
GREATER_SYDNEY_BBOX = {
    "min_lon": 150.5,
    "max_lon": 151.4,
    "min_lat": -34.2,
    "max_lat": -33.4,
}


def load_suburbs() -> gpd.GeoDataFrame:
    """Load suburb polygons, filter to Greater Sydney, normalise names."""
    gdf = gpd.read_file(SUBURBS_FILE)

    # Strip "(NSW)" suffix used in ABS SAL data ("Glebe (NSW)" -> "Glebe")
    gdf["suburb_clean"] = (
        gdf[SUBURB_COL]
        .str.replace(r"\s*\(NSW\)\s*$", "", regex=True)
        .str.strip()
    )

    # Reproject to WGS84 if needed
    if gdf.crs is None or gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs("EPSG:4326")

    # Filter to Greater Sydney by centroid (drops regional NSW suburbs)
    centroids = gdf.geometry.centroid
    in_sydney = (
        (centroids.x >= GREATER_SYDNEY_BBOX["min_lon"]) &
        (centroids.x <= GREATER_SYDNEY_BBOX["max_lon"]) &
        (centroids.y >= GREATER_SYDNEY_BBOX["min_lat"]) &
        (centroids.y <= GREATER_SYDNEY_BBOX["max_lat"])
    )
    gdf = gdf[in_sydney].copy().reset_index(drop=True)
    return gdf


def load_stops_in_scope(suburbs_gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Load stops.txt and spatially join to suburb polygons."""
    stops_df = pd.read_csv(RAW_DIR / "stops.txt")
    stops_gdf = gpd.GeoDataFrame(
        stops_df,
        geometry=gpd.points_from_xy(stops_df.stop_lon, stops_df.stop_lat),
        crs="EPSG:4326",
    )
    return gpd.sjoin(
        stops_gdf,
        suburbs_gdf[["suburb_clean", "geometry"]],
        predicate="within",
        how="inner",
    )


def load_peak_stop_events(scope_stop_ids: set[str]) -> pd.DataFrame:
    """Chunk through stop_times.txt; keep only in-scope stops in the peak window."""
    peak_chunks = []
    chunk_iter = pd.read_csv(
        RAW_DIR / "stop_times.txt",
        chunksize=CHUNK_SIZE,
        usecols=["trip_id", "stop_id", "departure_time"],
        dtype={"trip_id": str, "stop_id": str, "departure_time": str},
    )
    for chunk in chunk_iter:
        chunk = chunk[chunk["stop_id"].isin(scope_stop_ids)]
        if chunk.empty:
            continue
        # GTFS times can exceed 24h ("25:03:00" = 1:03am next day). First two
        # chars give the hour without parsing as a real time.
        chunk = chunk.assign(hour=chunk["departure_time"].str.slice(0, 2).astype(int))
        chunk = chunk[chunk["hour"].isin(PEAK_HOURS)]
        if not chunk.empty:
            peak_chunks.append(chunk)
    return pd.concat(peak_chunks, ignore_index=True) if peak_chunks else pd.DataFrame()


def filter_to_weekday_trips(peak_df: pd.DataFrame) -> pd.DataFrame:
    """Restrict peak events to trips running on weekdays (Mon-Fri)."""
    trips_df = pd.read_csv(
        RAW_DIR / "trips.txt",
        usecols=["trip_id", "service_id"],
        dtype={"trip_id": str, "service_id": str},
    )
    try:
        calendar_df = pd.read_csv(RAW_DIR / "calendar.txt")
        weekday_cols = ["monday", "tuesday", "wednesday", "thursday", "friday"]
        calendar_df["is_weekday"] = calendar_df[weekday_cols].sum(axis=1) >= 3
        weekday_services = set(
            calendar_df.loc[calendar_df["is_weekday"], "service_id"].astype(str)
        )
        trips_df = trips_df[trips_df["service_id"].isin(weekday_services)]
    except FileNotFoundError:
        pass
    return peak_df.merge(trips_df[["trip_id"]], on="trip_id", how="inner")


def score_suburbs(
    stops_in_scope: gpd.GeoDataFrame,
    peak_df: pd.DataFrame,
    suburbs_gdf: gpd.GeoDataFrame,
) -> pd.DataFrame:
    """Aggregate to suburb level and normalise to 0-1."""
    services_per_stop = (
        peak_df.groupby("stop_id").size().reset_index(name="service_count")
    )
    services_per_stop["services_per_hour"] = (
        services_per_stop["service_count"] / PEAK_WINDOW_HOURS
    )
    stops_scored = (
        stops_in_scope[["stop_id", "suburb_clean"]]
        .merge(services_per_stop, on="stop_id", how="left")
        .fillna({"service_count": 0, "services_per_hour": 0})
    )
    agg = (
        stops_scored.groupby("suburb_clean")
        .agg(
            avg_services_per_hour=("services_per_hour", "mean"),
            stop_count=("stop_id", "nunique"),
        )
        .reset_index()
    )
    # Ensure every suburb in scope appears, even if it has zero stops
    all_suburbs = pd.DataFrame({"suburb_clean": suburbs_gdf["suburb_clean"].unique()})
    agg = all_suburbs.merge(agg, on="suburb_clean", how="left").fillna(0)

    max_freq = agg["avg_services_per_hour"].max()
    if max_freq == 0:
        raise RuntimeError(
            "No peak-hour services matched any suburb. Check GTFS files and polygon overlap."
        )
    agg["transport_score"] = (agg["avg_services_per_hour"] / max_freq).round(3)
    return agg


def write_output(agg: pd.DataFrame) -> dict:
    """Serialise to the schema Sprint 3 expects."""
    output = {}
    for _, row in agg.iterrows():
        output[row["suburb_clean"]] = {
            "transport_score": float(row["transport_score"]),
            "avg_services_per_hour": round(float(row["avg_services_per_hour"]), 2),
            "stop_count": int(row["stop_count"]),
        }
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=2)
    return output


def run() -> dict:
    """End-to-end pipeline; returns the output dict (also written to disk)."""
    print(f"Loading suburbs from {SUBURBS_FILE}")
    suburbs_gdf = load_suburbs()
    print(f"  {len(suburbs_gdf)} Greater Sydney suburbs (after bbox filter)")

    print("Spatial-joining GTFS stops to suburbs")
    stops_in_scope = load_stops_in_scope(suburbs_gdf)
    print(f"  {len(stops_in_scope):,} stops within scope")

    print(f"Chunking stop_times.txt (chunksize={CHUNK_SIZE:,}) for peak-hour events")
    scope_stop_ids = set(stops_in_scope["stop_id"].astype(str))
    peak_df = load_peak_stop_events(scope_stop_ids)
    print(f"  {len(peak_df):,} peak-hour stop events")

    print("Filtering to weekday services")
    peak_df = filter_to_weekday_trips(peak_df)
    print(f"  {len(peak_df):,} weekday peak-hour events")

    print("Scoring suburbs")
    agg = score_suburbs(stops_in_scope, peak_df, suburbs_gdf)

    output = write_output(agg)
    print(f"\nWrote {OUTPUT_FILE} with {len(output)} suburbs")
    print("\nTop 10 by transport_score:")
    top = agg.sort_values("transport_score", ascending=False).head(10)
    print(top[["suburb_clean", "transport_score", "avg_services_per_hour", "stop_count"]].to_string(index=False))
    return output


if __name__ == "__main__":
    run()