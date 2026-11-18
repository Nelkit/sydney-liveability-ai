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
from core.cache import ttl_cached
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


# Static reference tables (sentiment profiles, BOCSAR, OSM) change at most
# quarterly. Keys keep suburb order because the returned dicts iterate in it.
_STATIC_TTL = settings.static_data_cache_ttl_seconds


def _suburbs_key(suburbs: list[str]) -> tuple[str, ...]:
    return tuple(suburbs or [])


@ttl_cached(maxsize=1000, ttl=_STATIC_TTL, key=_suburbs_key)
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


@ttl_cached(maxsize=1000, ttl=_STATIC_TTL, key=_suburbs_key)
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


@ttl_cached(maxsize=1000, ttl=_STATIC_TTL, key=_suburbs_key)
def _load_osm_and_sa4(suburbs: list[str]) -> dict[str, dict[str, Any]]:
    """Return OSM amenity counts and BOCSAR SA4 area per suburb as plain dicts.

    Replaces a per-suburb ``SELECT sa4_area`` that ran once for every suburb
    on every chat turn.
    """
    if not suburbs:
        return {}

    with SessionLocal() as session:
        osm_rows = session.scalars(select(OsmScore).where(OsmScore.suburb.in_(suburbs))).all()
        sa4_rows = session.execute(
            select(Bocsar.suburb, Bocsar.sa4_area).where(Bocsar.suburb.in_(suburbs)).distinct()
        ).all()

    data: dict[str, dict[str, Any]] = {suburb: {} for suburb in suburbs}
    for row in osm_rows:
        data.setdefault(row.suburb, {}).update(
            {
                "cafes": row.cafe,
                "restaurants": row.restaurant,
                "parks": row.park,
                "playgrounds": row.playground,
            }
        )
    for suburb, sa4_area in sa4_rows:
        data.setdefault(str(suburb), {}).setdefault("sa4", sa4_area)
    return data


def _build_suburb_scores(weights: dict[str, Any], suburbs: list[str]) -> list[dict[str, Any]]:
    if not suburbs:
        return []

    scored = compute_liveability_scores(weights=weights, suburb_filter=suburbs)
    sentiment_surface = _load_sentiment_surface(suburbs)
    crime_breakdown = _build_crime_breakdown(suburbs)
    osm_and_sa4 = _load_osm_and_sa4(suburbs)

    output: list[dict[str, Any]] = []
    for suburb in suburbs:
        suburb_score = scored.get(suburb)
        if not suburb_score:
            continue
        row = suburb_score.get("_row")
        extras = osm_and_sa4.get(suburb, {})
        sentiment_row = sentiment_surface.get(suburb, {}).get("aspects", {}).get("community")
        # Matches the previous behaviour: SA4 is only reported when BOCSAR
        # rows exist for the suburb.
        sa4_area = extras.get("sa4") if crime_breakdown.get(suburb) else None

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
                "cafes": extras.get("cafes"),
                "restaurants": extras.get("restaurants"),
                "parks": extras.get("parks"),
                "playgrounds": extras.get("playgrounds"),
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

        # Run every (specialist, suburb) pair concurrently. The sentiment
        # agent additionally consumes the original question so it can route
        # question-driven retrieval over the Reddit index; the other
        # specialists ignore the extra key. When the comparator is active,
        # the plan also covers every specialist for the first two suburbs.
        tasks = _plan_specialist_tasks(categories, suburbs, skip=set(specialist_outputs))
        parallel_outputs, parallel_timings = _run_specialists_parallel(tasks, question)
        specialist_outputs.update(parallel_outputs)
        specialist_timings.update(parallel_timings)

        # Comparator reuses the specialist results gathered above instead of
        # re-running them (sentiment alone is several LLM calls per suburb).
        if "comparator" in categories and len(suburbs) >= 2:
            comparator_started = time.perf_counter()
            print(f"Running comparator agent for suburbs: {suburbs[0]} and {suburbs[1]}")
            specialist_outputs["comparator"] = run_comparator(
                _comparator_input(categories, suburbs, specialist_outputs)
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


_SPECIALIST_ORDER: tuple[str, ...] = ("crime", "sentiment", "gis")

# Upper bound on concurrent specialist threads per question. The Supabase
# session pooler allows 5 connections (pool_size 3 + overflow 2), and the
# static-data caches keep most DB-bound specialists off the pool entirely.
_MAX_SPECIALIST_WORKERS = 4

SpecialistTask = tuple[str, str]  # (specialist_name, suburb)


def _step(text: str) -> tuple[str, dict[str, Any]]:
    return ("step", {"text": text})


def _default_runners() -> dict[str, Any]:
    return {"crime": run_crime, "sentiment": run_sentiment, "gis": run_gis}


def _plan_specialist_tasks(
    categories: list[str],
    suburbs: list[str],
    skip: set[str] | frozenset[str] = frozenset(),
) -> list[SpecialistTask]:
    """List every (specialist, suburb) pair this question needs.

    Mirrors the previous sequential logic: routed specialists run for every
    suburb; when the comparator is active, any specialist not yet planned
    runs for the first two suburbs so the comparison has full data.
    """
    if not suburbs:
        return []

    tasks: list[SpecialistTask] = []
    planned: set[str] = set(skip)
    for name in _SPECIALIST_ORDER:
        if name in categories and name not in planned:
            tasks.extend((name, suburb) for suburb in suburbs)
            planned.add(name)

    if "comparator" in categories and len(suburbs) >= 2:
        for name in _SPECIALIST_ORDER:
            if name not in planned:
                tasks.extend((name, suburb) for suburb in suburbs[:2])
                planned.add(name)
    return tasks


def _comparator_input(
    categories: list[str],
    suburbs: list[str],
    specialist_outputs: dict[str, Any],
) -> dict[str, Any]:
    compare_cats = [c for c in categories if c in _SPECIALIST_ORDER] or list(_SPECIALIST_ORDER)
    return {
        "suburb_a": suburbs[0],
        "suburb_b": suburbs[1],
        "categories": compare_cats,
        "precomputed": specialist_outputs,
    }


def _group_results(
    tasks: list[SpecialistTask],
    results: dict[SpecialistTask, dict[str, Any]],
    durations: dict[SpecialistTask, float],
) -> tuple[dict[str, dict[str, Any]], dict[str, float]]:
    """Fold per-task results into {specialist: {suburb: result}} in plan order.

    A specialist's timing is the slowest of its tasks, since they overlap.
    """
    outputs: dict[str, dict[str, Any]] = {}
    timings: dict[str, float] = {}
    for task in tasks:
        name, suburb = task
        outputs.setdefault(name, {})[suburb] = results[task]
        timings[name] = max(timings.get(name, 0.0), durations.get(task, 0.0))
    return outputs, timings


def _timed_call(run_func, input_data: dict[str, Any]) -> tuple[dict[str, Any], float]:
    started = time.perf_counter()
    try:
        result = run_func(input_data)
    except Exception as exc:
        result = {"status": "error", "reason": str(exc)}
    return result, (time.perf_counter() - started) * 1000.0


def _run_specialists_parallel(
    tasks: list[SpecialistTask],
    question: str,
    runners: dict[str, Any] | None = None,
) -> tuple[dict[str, dict[str, Any]], dict[str, float]]:
    """Run all specialist tasks concurrently and wait for every one.

    A failing specialist yields an error payload instead of aborting the
    whole turn, so the synthesiser can still answer from the others.
    """
    if not tasks:
        return {}, {}
    runners = runners or _default_runners()
    results: dict[SpecialistTask, dict[str, Any]] = {}
    durations: dict[SpecialistTask, float] = {}

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=min(_MAX_SPECIALIST_WORKERS, len(tasks))
    ) as pool:
        futures = {}
        for name, suburb in tasks:
            print(f"Running {name} agent for suburb: {suburb}")
            futures[(name, suburb)] = pool.submit(
                _timed_call, runners[name], {"suburb": suburb, "question": question}
            )
        for task, future in futures.items():
            results[task], durations[task] = future.result()

    return _group_results(tasks, results, durations)


def _stream_specialists_parallel(
    tasks: list[SpecialistTask],
    question: str,
    runners: dict[str, Any] | None = None,
    heartbeat_interval: float = 8.0,
    timeouts: dict[str, float] | None = None,
):
    """Streaming variant: run tasks concurrently while emitting heartbeats.

    Yields ``("step", {...})`` events and finally
    ``("result", (outputs, timings))``. A task that exceeds its
    specialist's timeout is reported as an error. The executor is shut down
    without waiting, so a hung worker no longer blocks the response (the old
    ``with ThreadPoolExecutor`` block waited on exit, defeating the timeout).
    """
    if not tasks:
        yield ("result", ({}, {}))
        return
    runners = runners or _default_runners()
    timeouts = timeouts or _SPECIALIST_TIMEOUT
    results: dict[SpecialistTask, dict[str, Any]] = {}
    durations: dict[SpecialistTask, float] = {}

    pool = concurrent.futures.ThreadPoolExecutor(max_workers=min(_MAX_SPECIALIST_WORKERS, len(tasks)))
    try:
        started = time.perf_counter()
        pending: dict[concurrent.futures.Future, SpecialistTask] = {}
        for name, suburb in tasks:
            pending[pool.submit(_timed_call, runners[name], {"suburb": suburb, "question": question})] = (
                name,
                suburb,
            )
        next_heartbeat = started + heartbeat_interval

        while pending:
            done, _ = concurrent.futures.wait(
                list(pending),
                timeout=min(0.5, heartbeat_interval),
                return_when=concurrent.futures.FIRST_COMPLETED,
            )
            for future in done:
                task = pending.pop(future)
                results[task], durations[task] = future.result()

            now = time.perf_counter()
            elapsed = now - started
            for future, task in list(pending.items()):
                name = task[0]
                limit = timeouts.get(name, 30)
                if elapsed >= limit:
                    future.cancel()
                    pending.pop(future)
                    results[task] = {"status": "error", "reason": f"{name} timed out after {limit}s"}
                    durations[task] = elapsed * 1000.0

            if pending and now >= next_heartbeat:
                name, suburb = next(iter(pending.values()))
                label = _SPECIALIST_LABELS.get(name, name)
                yield _step(f"{label} · {suburb}…")
                next_heartbeat = now + heartbeat_interval
    finally:
        pool.shutdown(wait=False, cancel_futures=True)

    yield ("result", _group_results(tasks, results, durations))


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

    tasks = _plan_specialist_tasks(categories, suburbs)
    # Announce every task up front, since they now start together.
    for name, suburb in tasks:
        yield _step(f"{_SPECIALIST_LABELS[name]} · {suburb}")
    for event_type, data in _stream_specialists_parallel(tasks, question):
        if event_type == "result":
            parallel_outputs, parallel_timings = data
            specialist_outputs.update(parallel_outputs)
            specialist_timings.update(parallel_timings)
        else:
            yield (event_type, data)

    if "comparator" in categories and len(suburbs) >= 2:
        comparator_started = time.perf_counter()
        yield _step(f"Comparing {suburbs[0]} vs {suburbs[1]}…")
        specialist_outputs["comparator"] = run_comparator(
            _comparator_input(categories, suburbs, specialist_outputs)
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
