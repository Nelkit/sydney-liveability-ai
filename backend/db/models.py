"""SQLAlchemy models for all structured project outputs."""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import UserDefinedType


class PostGISGeometry(UserDefinedType):
    """Minimal PostGIS geometry type wrapper for ORM schema alignment."""

    def get_col_spec(self, **kw: object) -> str:
        return "geometry(MultiPolygon,4326)"


class Base(DeclarativeBase):
    """Shared declarative base for all ORM tables."""


class Suburb(Base):
    """Composite suburb-level liveability outputs."""

    __tablename__ = "suburbs"

    sal_code: Mapped[str] = mapped_column(String, primary_key=True)
    suburb: Mapped[str] = mapped_column(String, nullable=False)
    car_share_bays_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    libraries_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mobility_parking_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sports_facilities_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_facilities: Mapped[int | None] = mapped_column(Integer, nullable=True)
    facilities_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    walkability_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    liveability_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    sa4_area: Mapped[str | None] = mapped_column(String, nullable=True)
    geometry: Mapped[Any | None] = mapped_column(PostGISGeometry(), nullable=True)


class Bocsar(Base):
    """Crime incidents mapped by suburb and SA4 area."""

    __tablename__ = "bocsar"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    suburb: Mapped[str] = mapped_column(String(80), nullable=False)
    crime_type: Mapped[str] = mapped_column(String(120), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    incident_count: Mapped[int] = mapped_column(Integer, nullable=False)
    sa4_area: Mapped[str] = mapped_column(String(80), nullable=False)


class Sentiment(Base):
    """Per-suburb sentiment features derived from social discourse."""

    __tablename__ = "sentiment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    suburb: Mapped[str] = mapped_column(String(80), nullable=False)
    topic: Mapped[str] = mapped_column(String(80), nullable=False)
    vader_score: Mapped[float] = mapped_column(Float, nullable=False)
    textblob_score: Mapped[float] = mapped_column(Float, nullable=False)
    subjectivity: Mapped[float] = mapped_column(Float, nullable=False)
    source: Mapped[str] = mapped_column(String(80), nullable=False)


class TopicWeight(Base):
    """Topic model weights and top terms used in explainability."""

    __tablename__ = "topic_weights"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    suburb: Mapped[str] = mapped_column(String(80), nullable=False)
    topic_label: Mapped[str] = mapped_column(String(80), nullable=False)
    weight: Mapped[float] = mapped_column(Float, nullable=False)
    top_terms: Mapped[str] = mapped_column(Text, nullable=False)


class SentimentScore(Base):
    """Aspect-level sentiment scores generated from suburb discourse."""

    __tablename__ = "sentiment_scores"

    suburb: Mapped[str] = mapped_column(String, primary_key=True)
    aspect: Mapped[str] = mapped_column(String, primary_key=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    mentions: Mapped[int | None] = mapped_column(Integer, nullable=True)


class EmotionProfile(Base):
    """Emotion distribution per suburb from social posts."""

    __tablename__ = "emotion_profiles"

    suburb: Mapped[str] = mapped_column(String, primary_key=True)
    joy: Mapped[float | None] = mapped_column(Float, nullable=True)
    surprise: Mapped[float | None] = mapped_column(Float, nullable=True)
    neutral: Mapped[float | None] = mapped_column(Float, nullable=True)
    sadness: Mapped[float | None] = mapped_column(Float, nullable=True)
    anger: Mapped[float | None] = mapped_column(Float, nullable=True)
    fear: Mapped[float | None] = mapped_column(Float, nullable=True)
    disgust: Mapped[float | None] = mapped_column(Float, nullable=True)
    post_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class SuburbNarrative(Base):
    """Narrative summary and source snippets per suburb."""

    __tablename__ = "suburb_narratives"

    suburb: Mapped[str] = mapped_column(String, primary_key=True)
    narrative: Mapped[str | None] = mapped_column(Text, nullable=True)
    sources: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)


class OsmScore(Base):
    """OSM-derived amenity counts and normalized score per suburb."""

    __tablename__ = "osm_scores"

    suburb: Mapped[str] = mapped_column(String, primary_key=True)
    osm_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    cafe: Mapped[int | None] = mapped_column(Integer, nullable=True)
    restaurant: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gym: Mapped[int | None] = mapped_column(Integer, nullable=True)
    school: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hospital: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pharmacy: Mapped[int | None] = mapped_column(Integer, nullable=True)
    library: Mapped[int | None] = mapped_column(Integer, nullable=True)
    park: Mapped[int | None] = mapped_column(Integer, nullable=True)
    playground: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sports_centre: Mapped[int | None] = mapped_column(Integer, nullable=True)


class TransportScore(Base):
    """Transport accessibility indicators and aggregate score per suburb."""

    __tablename__ = "transport_scores"

    suburb: Mapped[str] = mapped_column(String, primary_key=True)
    bus_stops: Mapped[int | None] = mapped_column(Integer, nullable=True)
    train_stations: Mapped[int | None] = mapped_column(Integer, nullable=True)
    light_rail_stops: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bike_paths_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_commute_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    transport_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_services_per_hour: Mapped[float | None] = mapped_column(Float, nullable=True)
    stop_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source: Mapped[str | None] = mapped_column(String, nullable=True)