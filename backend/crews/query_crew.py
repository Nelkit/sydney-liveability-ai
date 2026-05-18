"""Query crew orchestration for per-question specialist execution."""

from __future__ import annotations

import concurrent.futures
import time
from typing import Any

from crewai import Crew, Process
from sqlalchemy import select

from agents.query.comparator import comparator_agent, run as run_comparator
from agents.query.crime import crime_agent, run as run_crime
from agents.query.gis import gis_agent, run as run_gis
from agents.query.router import router_agent, run as run_router
from agents.query.sentiment import run as run_sentiment
from agents.query.sentiment import sentiment_agent
from agents.query.synthesiser import run as run_synthesiser
from agents.query.synthesiser import synthesiser_agent
from config import get_agent_llm, settings
from core.scoring import compute_liveability_scores
from db.models import Bocsar, EmotionProfile, OsmScore, SentimentScore, SuburbNarrative
from db.postgres import SessionLocal


def _llm_model_name(agent_name: str) -> str:
    llm = get_agent_llm(agent_name)
    return str(getattr(llm, "model", settings.llm_model))


def _scale_to_100(value: Any) -> float | None:
    if value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return round(numeric * 100.0, 2) if numeric <= 1.0 else round(numeric, 2)


def _load_sentiment_surface(suburbs: list[str]) -> dict[str, dict[str, Any]]:
    if not suburbs:
        return {}

    with SessionLocal() as session:
        aspect_rows = session.scalars(
            select(SentimentScore).where(SentimentScore.suburb.in_(suburbs))
        ).all()
        emotion_rows = {
            row.suburb: row
            for row in session.scalars(
                select(EmotionProfile).where(EmotionProfile.suburb.in_(suburbs))
            ).all()
        }
        narrative_rows = {
            row.suburb: row
            for row in session.scalars(
                select(SuburbNarrative).where(SuburbNarrative.suburb.in_(suburbs))
            ).all()
        }

    aspects_by_suburb: dict[str, dict[str, dict[str, Any]]] = {}
    for row in aspect_rows:
        aspects_by_suburb.setdefault(row.suburb, {})[row.aspect] = {
            "score": row.score,
            "mentions": row.mentions,
            "confidence": row.confidence,
            "coverage": row.coverage,
            "source": row.source,
        }

    surface: dict[str, dict[str, Any]] = {}
    for suburb in suburbs:
        emotion_row = emotion_rows.get(suburb)
        narrative_row = narrative_rows.get(suburb)
        surface[suburb] = {
            "aspects": aspects_by_suburb.get(suburb, {}),
            "emotions": {
                "joy": emotion_row.joy if emotion_row else None,
                "surprise": emotion_row.surprise if emotion_row else None,
                "neutral": emotion_row.neutral if emotion_row else None,
                "sadness": emotion_row.sadness if emotion_row else None,
                "anger": emotion_row.anger if emotion_row else None,
                "fear": emotion_row.fear if emotion_row else None,
                "disgust": emotion_row.disgust if emotion_row else None,
            },
            "narrative": narrative_row.narrative if narrative_row else None,
            "sources": narrative_row.sources if narrative_row and narrative_row.sources else [],
        }
    return surface


def _build_aspect_scores(sentiment_surface: dict[str, dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    return {
        suburb: [
            {
                "aspect": aspect_name,
                "pos": aspect_data.get("score"),
                "mentions": aspect_data.get("mentions"),
            }
            for aspect_name, aspect_data in suburb_data.get("aspects", {}).items()
            if isinstance(aspect_data, dict)
        ]
        for suburb, suburb_data in sentiment_surface.items()
    }


def _build_emotion_profiles(sentiment_surface: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {suburb: suburb_data.get("emotions", {}) for suburb, suburb_data in sentiment_surface.items()}


def _build_reddit_highlights(sentiment_surface: dict[str, dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    highlights: dict[str, list[dict[str, Any]]] = {}
    for suburb, suburb_data in sentiment_surface.items():
        aspects = suburb_data.get("aspects") or {}
        sources = suburb_data.get("sources") or []
        if not isinstance(sources, list):
            sources = []

        dominant_aspect = "general"
        if isinstance(aspects, dict) and aspects:
            dominant_aspect = max(
                aspects.items(),
                key=lambda item: float(item[1].get("mentions") or 0),
            )[0]

        aspect_scores = [
            float(entry.get("score"))
            for entry in aspects.values()
            if isinstance(entry, dict) and isinstance(entry.get("score"), (int, float))
        ]
        if aspect_scores:
            avg_score = sum(aspect_scores) / len(aspect_scores)
            sentiment = "pos" if avg_score >= 0.6 else "neg" if avg_score <= 0.4 else "neu"
        else:
            sentiment = "neu"

        suburb_highlights: list[dict[str, Any]] = []
        for index, source in enumerate(sources[:5], start=1):
            if not isinstance(source, dict):
                continue
            text = str(source.get("text") or "").strip()
            if not text:
                continue
            suburb_highlights.append(
                {
                    "id": str(source.get("url") or f"{suburb.lower()}-{index}"),
                    "q": text,
                    "aspect": dominant_aspect.replace("_", " "),
                    "sentiment": sentiment,
                    "up": int(source.get("score") or 0),
                }
            )
        highlights[suburb] = suburb_highlights

    return highlights


def _build_crime_breakdown(suburbs: list[str]) -> dict[str, list[dict[str, Any]]]:
    if not suburbs:
        return {}

    with SessionLocal() as session:
        rows = session.execute(
            select(Bocsar.suburb, Bocsar.crime_type, Bocsar.year, Bocsar.incident_count, Bocsar.sa4_area)
            .where(Bocsar.suburb.in_(suburbs))
            .order_by(Bocsar.suburb, Bocsar.crime_type, Bocsar.year)
        ).all()

    grouped: dict[str, dict[str, list[tuple[int, int, str]]]] = {}
    for suburb, crime_type, year, incident_count, sa4_area in rows:
        grouped.setdefault(str(suburb), {}).setdefault(str(crime_type), []).append(
            (int(year), int(incident_count), str(sa4_area))
        )

    breakdown: dict[str, list[dict[str, Any]]] = {}
    for suburb, crime_types in grouped.items():
        suburb_rows: list[dict[str, Any]] = []
        for crime_type, series in crime_types.items():
            if not series:
                continue
            series.sort(key=lambda item: item[0])
            _, latest_count, _ = series[-1]
            prev_count = series[-2][1] if len(series) > 1 else 0
            trend = 0.0 if prev_count <= 0 else round(((latest_count - prev_count) / prev_count) * 100.0, 1)
            suburb_rows.append({"cat": crime_type, "v": latest_count, "trend": trend})
        suburb_rows.sort(key=lambda item: item["v"], reverse=True)
        breakdown[suburb] = suburb_rows

    return breakdown


def _build_suburb_scores(weights: dict[str, Any], suburbs: list[str]) -> list[dict[str, Any]]:
    if not suburbs:
        return []

    scored = compute_liveability_scores(weights=weights, suburb_filter=suburbs)
    sentiment_surface = _load_sentiment_surface(suburbs)
    crime_breakdown = _build_crime_breakdown(suburbs)

    with SessionLocal() as session:
        osm_rows = {
            row.suburb: row
            for row in session.scalars(select(OsmScore).where(OsmScore.suburb.in_(suburbs))).all()
        }

    output: list[dict[str, Any]] = []
    for suburb in suburbs:
        suburb_score = scored.get(suburb)
        if not suburb_score:
            continue
        row = suburb_score.get("_row")
        osm_row = osm_rows.get(suburb)
        sentiment_row = sentiment_surface.get(suburb, {}).get("aspects", {}).get("community")
        sa4_area = None
        crime_rows = crime_breakdown.get(suburb) or []
        if crime_rows:
            with SessionLocal() as session:
                sa4_area = session.scalar(select(Bocsar.sa4_area).where(Bocsar.suburb == suburb).limit(1))

        output.append(
            {
                "name": suburb,
                "score": round(float(suburb_score["liveability"]) * 100.0, 2),
                "transport": round(float(suburb_score["transport"]) * 100.0, 2),
                "safety": round(float(suburb_score["safety"]) * 100.0, 2),
                "lifestyle": round(float(suburb_score["lifestyle"]) * 100.0, 2),
                "affordability": round(float(suburb_score["affordability"]) * 100.0, 2),
                "proximity": round(float(suburb_score["proximity"]) * 100.0, 2),
                "facilities": _scale_to_100(getattr(row, "facilities_score", None) if row is not None else None),
                "walkability": _scale_to_100(getattr(row, "walkability_score", None) if row is not None else None),
                "crimeIdx": round((1.0 - float(suburb_score["safety"])) * 100.0, 2),
                "sentiment": _scale_to_100(sentiment_row.get("score") if isinstance(sentiment_row, dict) else None),
                "cafes": getattr(osm_row, "cafe", None) if osm_row is not None else None,
                "restaurants": getattr(osm_row, "restaurant", None) if osm_row is not None else None,
                "parks": getattr(osm_row, "park", None) if osm_row is not None else None,
                "playgrounds": getattr(osm_row, "playground", None) if osm_row is not None else None,
                "sa4": sa4_area,
            }
        )

    return output


def _build_map_state(router_output: dict[str, Any], suburb_scores: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not suburb_scores:
        return None

    categories = list(router_output.get("categories", [])) if isinstance(router_output, dict) else []
    if "crime" in categories and "gis" not in categories and "sentiment" not in categories:
        layer = "safety"
    elif "gis" in categories and "crime" not in categories:
        layer = "transport"
    elif "sentiment" in categories and "crime" not in categories and "gis" not in categories:
        layer = "lifestyle"
    else:
        layer = "liveability"

    active_suburbs = [row["name"] for row in suburb_scores if row.get("name")]
    return {
        "activeSuburbs": active_suburbs,
        "layer": layer,
        "suburb_filter": active_suburbs,
        "heatmap_weights": router_output.get("weights") if isinstance(router_output, dict) else {},
    }


def _build_evidence_trace_summary(
    router_ms: float,
    router_output: dict[str, Any],
    specialist_timings: dict[str, float],
    specialist_outputs: dict[str, Any],
) -> dict[str, Any]:
    sentiment_outputs = specialist_outputs.get("sentiment") if isinstance(specialist_outputs, dict) else None
    trace_length = 0
    by_tool: dict[str, int] = {}
    last_action: dict[str, Any] | None = None
    last_step = -1
    no_data_count = 0

    if isinstance(sentiment_outputs, dict):
        for suburb, result in sentiment_outputs.items():
            if not isinstance(result, dict):
                continue
            for entry in result.get("evidence_trace") or []:
                if not isinstance(entry, dict):
                    continue
                trace_length += 1
                tool_name = str(entry.get("tool") or "unknown")
                by_tool[tool_name] = by_tool.get(tool_name, 0) + 1
                preview = str(entry.get("result_preview") or "")
                if "no_data" in preview:
                    no_data_count += 1
                step = entry.get("step")
                if isinstance(step, int) and step > last_step:
                    last_step = step
                    args = entry.get("arguments") or {}
                    last_action = {
                        "step": step,
                        "tool": tool_name,
                        "suburb": args.get("suburb") or suburb,
                        "dimension": args.get("dimension"),
                        "result_count": entry.get("result_count"),
                    }

    specialist_trace: list[dict[str, Any]] = []
    for specialist_name in ("crime", "sentiment", "gis", "comparator"):
        if specialist_name not in specialist_timings:
            continue
        output = specialist_outputs.get(specialist_name)
        retrieved = 0
        if specialist_name == "sentiment" and isinstance(output, dict):
            for suburb_result in output.values():
                if isinstance(suburb_result, dict):
                    retrieved += len(suburb_result.get("evidence_trace") or [])
        elif specialist_name == "crime" and isinstance(output, dict):
            for suburb_result in output.values():
                if isinstance(suburb_result, dict):
                    retrieved += len(suburb_result.get("crime_summary") or {})
        elif specialist_name == "gis" and isinstance(output, dict):
            for suburb_result in output.values():
                if isinstance(suburb_result, dict):
                    retrieved += sum(1 for value in suburb_result.values() if value is not None)
        elif specialist_name == "comparator" and isinstance(output, dict):
            retrieved = len(output.get("comparison") or {})

        specialist_trace.append(
            {
                "id": specialist_name,
                "ms": round(specialist_timings[specialist_name], 2),
                "retrieved": retrieved,
                "store": "postgres+chromadb" if specialist_name == "sentiment" else "postgres",
            }
        )

    return {
        "router": {
            "ms": round(router_ms, 2),
            "model": _llm_model_name("router"),
            "note": ",".join(router_output.get("categories", [])) or "routing",
        },
        "specialists": specialist_trace,
        "totals": {
            "length": trace_length,
            "by_tool": by_tool,
            "last_action": last_action,
            "no_data_count": no_data_count,
        },
    }


def _summarise_evidence_trace(specialist_outputs: dict[str, Any]) -> dict[str, Any]:
    """Aggregate sentiment specialists' `evidence_trace` into a summary dict.

    Returns the deterministic shape promised by the `quality.evidence_trace_summary`
    contract: total length, per-tool counts, the last action across all suburbs by
    max step, and a no_data count detected by substring match on `result_preview`.
    """
    sentiment_outputs = specialist_outputs.get("sentiment") if isinstance(specialist_outputs, dict) else None
    summary: dict[str, Any] = {
        "length": 0,
        "by_tool": {},
        "last_action": None,
        "no_data_count": 0,
    }
    if not isinstance(sentiment_outputs, dict):
        return summary

    last_action: dict[str, Any] | None = None
    last_step = -1
    for suburb, result in sentiment_outputs.items():
        if not isinstance(result, dict):
            continue
        for entry in result.get("evidence_trace") or []:
            if not isinstance(entry, dict):
                continue
            summary["length"] += 1
            tool_name = str(entry.get("tool") or "unknown")
            summary["by_tool"][tool_name] = summary["by_tool"].get(tool_name, 0) + 1
            preview = str(entry.get("result_preview") or "")
            if "no_data" in preview:
                summary["no_data_count"] += 1
            step = entry.get("step")
            if isinstance(step, int) and step > last_step:
                last_step = step
                args = entry.get("arguments") or {}
                last_action = {
                    "step": step,
                    "tool": tool_name,
                    "suburb": args.get("suburb") or suburb,
                    "dimension": args.get("dimension"),
                    "result_count": entry.get("result_count"),
                }
    summary["last_action"] = last_action
    return summary


def build_query_crew() -> Crew:
    """Return all six query agents in sequential crew order."""
    return Crew(
        agents=[
            router_agent,
            crime_agent,
            sentiment_agent,
            gis_agent,
            comparator_agent,
            synthesiser_agent,
        ],
        process=Process.sequential,
        verbose=True,
    )


def run_query(question: str, weights: dict[str, Any] | None = None) -> dict[str, Any]:
    """Run router first, then activated specialists for all suburbs, and synthesiser last."""
    try:
        router_started = time.perf_counter()
        router_output = run_router({"question": question})
        router_ms = (time.perf_counter() - router_started) * 1000.0
        categories = list(router_output.get("categories", []))
        suburbs = list(router_output.get("suburbs_mentioned", []))

        if "out_of_scope" in categories:
            response = run_synthesiser(
                {
                    "question": question,
                    "router": router_output,
                    "outputs": {},
                }
            )
            response["quality"] = {
                "evidence_trace_summary": _build_evidence_trace_summary(router_ms, router_output, {}, {})
            }
            response["outputs"] = {}
            response["router"] = {
                **router_output,
                "latencyMs": round(router_ms, 2),
            }
            response["suburb_scores"] = []
            response["map_state"] = None
            return response

        specialist_outputs: dict[str, Any] = {}
        specialist_timings: dict[str, float] = {}

        # Ranking mode: no suburb was named but the question asks to rank/compare
        # all suburbs by a field (e.g. "which suburbs have the most parks").
        # Run GIS in ranking mode, then promote the top results as the working
        # suburb list so the synthesiser only loads those suburbs from the DB.
        if "ranking" in categories and not suburbs:
            ranking_started = time.perf_counter()
            print("Running GIS agent in ranking mode")
            ranking_result = run_gis({"question": question, "mode": "ranking"})
            specialist_outputs["gis"] = ranking_result
            specialist_timings["gis"] = (time.perf_counter() - ranking_started) * 1000.0
            if ranking_result.get("status") == "ok":
                suburbs = ranking_result.get("suburbs", [])[:10]

        # Run single-suburb specialists for each suburb mentioned. The
        # sentiment agent additionally consumes the original question so
        # it can route question-driven retrieval over the Reddit index;
        # the other specialists ignore the extra key.
        for specialist_name in ["crime", "sentiment", "gis"]:
            if specialist_name in categories and suburbs and specialist_name not in specialist_outputs:
                specialist_started = time.perf_counter()
                specialist_outputs[specialist_name] = {}
                run_func = {
                    "crime": run_crime,
                    "sentiment": run_sentiment,
                    "gis": run_gis,
                }[specialist_name]
                for suburb in suburbs:
                    print(f"Running {specialist_name} agent for suburb: {suburb}")
                    specialist_outputs[specialist_name][suburb] = run_func(
                        {"suburb": suburb, "question": question}
                    )
                specialist_timings[specialist_name] = (time.perf_counter() - specialist_started) * 1000.0

        # Run comparator only if 2+ suburbs are mentioned
        if "comparator" in categories and len(suburbs) >= 2:
            # Always run all specialists for both suburbs so synthesiser has full data
            comparator_started = time.perf_counter()
            for specialist_name in ["crime", "sentiment", "gis"]:
                if specialist_name not in specialist_outputs:
                    specialist_started = time.perf_counter()
                    run_func = {"crime": run_crime, "sentiment": run_sentiment, "gis": run_gis}[specialist_name]
                    specialist_outputs[specialist_name] = {}
                    for suburb in suburbs[:2]:
                        print(f"Running {specialist_name} agent for suburb: {suburb}")
                        specialist_outputs[specialist_name][suburb] = run_func(
                            {"suburb": suburb, "question": question}
                        )
                    specialist_timings[specialist_name] = (time.perf_counter() - specialist_started) * 1000.0
            print(f"Running comparator agent for suburbs: {suburbs[0]} and {suburbs[1]}")
            compare_cats = [c for c in categories if c in ("gis", "crime", "sentiment")]
            if not compare_cats:
                compare_cats = ["gis", "crime", "sentiment"]
            specialist_outputs["comparator"] = run_comparator(
                {"suburb_a": suburbs[0], "suburb_b": suburbs[1], "categories": compare_cats}
            )
            specialist_timings["comparator"] = (time.perf_counter() - comparator_started) * 1000.0

        synthesis_payload = {
            "question": question,
            "weights": weights or {},
            "router": router_output,
            "outputs": specialist_outputs,
            "suburbs": suburbs,
        }
        response = run_synthesiser(synthesis_payload)
        suburb_scores = _build_suburb_scores(weights or {}, suburbs)
        suburb_names = [row["name"] for row in suburb_scores if row.get("name")]
        sentiment_surface = _load_sentiment_surface(suburb_names or suburbs)

        response["quality"] = {
            "evidence_trace_summary": _build_evidence_trace_summary(
                router_ms,
                router_output,
                specialist_timings,
                specialist_outputs,
            )
        }
        # Expose specialist outputs and router for the offline eval script.
        # The /api/chat endpoint filters its response shape, so this leak is
        # internal to run_query callers (eval script) only.
        response["outputs"] = specialist_outputs
        response["router"] = {
            **router_output,
            "latencyMs": round(router_ms, 2),
        }
        response["suburb_scores"] = suburb_scores
        response["aspect_scores"] = _build_aspect_scores(sentiment_surface)
        response["emotion_profile"] = _build_emotion_profiles(sentiment_surface)
        response["reddit_highlights"] = _build_reddit_highlights(sentiment_surface)
        response["crime_breakdown"] = _build_crime_breakdown(suburb_names or suburbs)
        response["map_state"] = _build_map_state(router_output, suburb_scores)
        return response
    except Exception as e:
        import traceback
        print(f"ERROR in run_query: {e}")
        traceback.print_exc()
        raise


_SPECIALIST_LABELS: dict[str, str] = {
    "crime": "Analysing crime data",
    "sentiment": "Searching Reddit posts",
    "gis": "Reading GIS layers",
    "comparator": "Comparing suburbs",
}

_SPECIALIST_TIMEOUT: dict[str, int] = {
    "sentiment": 45,
    "crime": 15,
    "gis": 15,
    "comparator": 60,
}


def _step(text: str) -> tuple[str, dict[str, Any]]:
    return ("step", {"text": text})


def _run_specialist_with_heartbeat(
    run_func,
    input_data: dict[str, Any],
    specialist_name: str,
    suburb: str,
):
    """Run a specialist in a thread and yield heartbeat steps while waiting.

    Yields tuples of (event_type, data) — heartbeats are step events.
    The final item yielded is always ("result", result_dict).
    """
    timeout = _SPECIALIST_TIMEOUT.get(specialist_name, 30)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(run_func, input_data)
        deadline = time.perf_counter() + timeout
        heartbeat_interval = 8.0
        next_heartbeat = time.perf_counter() + heartbeat_interval
        label = _SPECIALIST_LABELS.get(specialist_name, specialist_name)

        while True:
            done, _ = concurrent.futures.wait([future], timeout=0.5)
            if done:
                try:
                    result = future.result()
                except Exception as exc:
                    result = {"status": "error", "reason": str(exc)}
                yield ("result", result)
                return

            now = time.perf_counter()
            if now >= deadline:
                future.cancel()
                yield ("result", {"status": "error", "reason": f"{specialist_name} timed out after {timeout}s"})
                return

            if now >= next_heartbeat:
                yield ("step", {"text": f"{label} · {suburb}…"})
                next_heartbeat = now + heartbeat_interval


def _build_final_result(
    response: dict[str, Any],
    router_ms: float,
    router_output: dict[str, Any],
    specialist_timings: dict[str, float],
    specialist_outputs: dict[str, Any],
    suburb_scores: list[dict[str, Any]],
    suburb_names: list[str],
    suburbs: list[str],
    weights: dict[str, Any],
) -> dict[str, Any]:
    sentiment_surface = _load_sentiment_surface(suburb_names or suburbs)
    response["quality"] = {
        "evidence_trace_summary": _build_evidence_trace_summary(
            router_ms, router_output, specialist_timings, specialist_outputs
        )
    }
    response["outputs"] = specialist_outputs
    response["router"] = {**router_output, "latencyMs": round(router_ms, 2)}
    response["suburb_scores"] = suburb_scores
    response["aspect_scores"] = _build_aspect_scores(sentiment_surface)
    response["emotion_profile"] = _build_emotion_profiles(sentiment_surface)
    response["reddit_highlights"] = _build_reddit_highlights(sentiment_surface)
    response["crime_breakdown"] = _build_crime_breakdown(suburb_names or suburbs)
    response["map_state"] = _build_map_state(router_output, suburb_scores)
    return response


def run_query_stream(
    question: str, weights: dict[str, Any] | None = None
):
    """Same pipeline as run_query but yields SSE events as each phase completes."""
    weights = weights or {}

    yield _step("Routing question…")
    router_started = time.perf_counter()
    router_output = run_router({"question": question})
    router_ms = (time.perf_counter() - router_started) * 1000.0
    categories = list(router_output.get("categories", []))
    suburbs = list(router_output.get("suburbs_mentioned", []))

    if "out_of_scope" in categories:
        yield _step("Synthesising answer…")
        response = run_synthesiser({"question": question, "router": router_output, "outputs": {}})
        response["quality"] = {
            "evidence_trace_summary": _build_evidence_trace_summary(router_ms, router_output, {}, {})
        }
        response["outputs"] = {}
        response["router"] = {**router_output, "latencyMs": round(router_ms, 2)}
        response["suburb_scores"] = []
        response["map_state"] = None
        yield ("done", response)
        return

    specialist_outputs: dict[str, Any] = {}
    specialist_timings: dict[str, float] = {}

    for specialist_name in ["crime", "sentiment", "gis"]:
        if specialist_name in categories and suburbs:
            label = _SPECIALIST_LABELS[specialist_name]
            run_func = {"crime": run_crime, "sentiment": run_sentiment, "gis": run_gis}[specialist_name]
            specialist_started = time.perf_counter()
            specialist_outputs[specialist_name] = {}
            for suburb in suburbs:
                yield _step(f"{label} · {suburb}")
                for event_type, data in _run_specialist_with_heartbeat(
                    run_func, {"suburb": suburb, "question": question}, specialist_name, suburb
                ):
                    if event_type == "result":
                        specialist_outputs[specialist_name][suburb] = data
                    else:
                        yield (event_type, data)
            specialist_timings[specialist_name] = (time.perf_counter() - specialist_started) * 1000.0

    if "comparator" in categories and len(suburbs) >= 2:
        comparator_started = time.perf_counter()
        for specialist_name in ["crime", "sentiment", "gis"]:
            if specialist_name not in specialist_outputs:
                label = _SPECIALIST_LABELS[specialist_name]
                for suburb in suburbs[:2]:
                    yield _step(f"{label} · {suburb}")
                specialist_started = time.perf_counter()
                run_func = {"crime": run_crime, "sentiment": run_sentiment, "gis": run_gis}[specialist_name]
                specialist_outputs[specialist_name] = {}
                for suburb in suburbs[:2]:
                    specialist_outputs[specialist_name][suburb] = run_func(
                        {"suburb": suburb, "question": question}
                    )
                specialist_timings[specialist_name] = (time.perf_counter() - specialist_started) * 1000.0
        yield _step(f"Comparing {suburbs[0]} vs {suburbs[1]}…")
        compare_cats = [c for c in categories if c in ("gis", "crime", "sentiment")] or ["gis", "crime", "sentiment"]
        specialist_outputs["comparator"] = run_comparator(
            {"suburb_a": suburbs[0], "suburb_b": suburbs[1], "categories": compare_cats}
        )
        specialist_timings["comparator"] = (time.perf_counter() - comparator_started) * 1000.0

    yield _step("Synthesising answer…")
    response = run_synthesiser({
        "question": question,
        "weights": weights,
        "router": router_output,
        "outputs": specialist_outputs,
    })

    yield _step("Computing liveability scores…")
    suburb_scores = _build_suburb_scores(weights, suburbs)
    suburb_names = [row["name"] for row in suburb_scores if row.get("name")]

    result = _build_final_result(
        response, router_ms, router_output, specialist_timings,
        specialist_outputs, suburb_scores, suburb_names, suburbs, weights,
    )
    yield ("done", result)


if __name__ == "__main__":
    print(run_query("Compare Newtown versus Glebe for amenities and safety"))
