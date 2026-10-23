"""Evalúa el pipeline Azure de PluriOne contra etiquetas humanas en un CSV.

No persiste comentarios en PostgreSQL. Sanitiza el texto antes de enviarlo a
Azure y guarda en el reporte solo IDs, etiquetas, métricas y tiempos.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from app.services.ai_engine import analyze_sentiment_with_ai
from app.services.sanitization import sanitize_text

SENTIMENT_LABELS = {"positivo": "Positivo", "neutral": "Neutral", "neutro": "Neutral", "negativo": "Negativo"}
REQUIRED_COLUMNS = {"text_content", "expected_sentiment", "expected_red_flag"}
MINIMUM_SAMPLE_SIZE = 200


def parse_bool(value: str, row_number: int) -> bool:
    normalized = value.strip().casefold()
    if normalized in {"true", "1", "yes", "si", "sí", "verdadero"}:
        return True
    if normalized in {"false", "0", "no", "falso"}:
        return False
    raise ValueError(f"Fila {row_number}: expected_red_flag debe ser true/false, sí/no o 1/0.")


def load_cases(csv_path: Path) -> list[dict[str, Any]]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        columns = set(reader.fieldnames or [])
        missing = REQUIRED_COLUMNS - columns
        if missing:
            raise ValueError(f"Faltan columnas obligatorias: {', '.join(sorted(missing))}.")

        cases = []
        seen_ids = set()
        for row_number, row in enumerate(reader, start=2):
            text = (row.get("text_content") or "").strip()
            if not text:
                raise ValueError(f"Fila {row_number}: text_content está vacío.")

            raw_sentiment = (row.get("expected_sentiment") or "").strip().casefold()
            expected_sentiment = SENTIMENT_LABELS.get(raw_sentiment)
            if expected_sentiment is None:
                raise ValueError(
                    f"Fila {row_number}: expected_sentiment debe ser Positivo, Neutral o Negativo."
                )

            case_id = (row.get("case_id") or str(row_number - 1)).strip()
            if not case_id or case_id in seen_ids:
                raise ValueError(f"Fila {row_number}: case_id está vacío o duplicado.")
            seen_ids.add(case_id)

            cases.append({
                "case_id": case_id,
                "text_content": text,
                "expected_sentiment": expected_sentiment,
                "expected_red_flag": parse_bool(row["expected_red_flag"], row_number),
            })

    if not cases:
        raise ValueError("El CSV no contiene casos de evaluación.")
    return cases


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, math.ceil(fraction * len(ordered)) - 1)
    return ordered[index]


def evaluate(cases: list[dict[str, Any]], delay_seconds: float) -> dict[str, Any]:
    details = []
    latencies = []

    for index, case in enumerate(cases, start=1):
        started = time.perf_counter()
        predicted_sentiment = None
        predicted_red_flag = False
        error_type = None
        unavailable_reason = None

        try:
            safe_text = sanitize_text(case["text_content"])
            result = analyze_sentiment_with_ai(safe_text)
            sentiment = result.get("sentiment_label")
            if sentiment in {"Positivo", "Neutral", "Negativo"}:
                predicted_sentiment = sentiment
            metadata = result.get("metadata_ai") or {}
            predicted_red_flag = bool(metadata.get("risk_burnout", False))
            if predicted_sentiment is None:
                unavailable_reason = (
                    metadata.get("error_type")
                    or metadata.get("error_detail")
                    or "analysis_unavailable_without_reason"
                )
        except Exception as exc:  # continúa para medir cobertura y fallos del lote
            error_type = type(exc).__name__
            unavailable_reason = error_type

        elapsed_seconds = time.perf_counter() - started
        latencies.append(elapsed_seconds)
        details.append({
            "case_id": case["case_id"],
            "expected_sentiment": case["expected_sentiment"],
            "predicted_sentiment": predicted_sentiment,
            "expected_red_flag": case["expected_red_flag"],
            "predicted_red_flag": predicted_red_flag,
            "analysis_available": predicted_sentiment is not None,
            "latency_seconds": round(elapsed_seconds, 4),
            "error_type": error_type,
            "unavailable_reason": unavailable_reason,
        })

        if index % 10 == 0 or index == len(cases):
            print(f"Evaluados {index}/{len(cases)} casos.")
        if delay_seconds and index < len(cases):
            time.sleep(delay_seconds)

    total = len(details)
    available = sum(item["analysis_available"] for item in details)
    correct = sum(
        item["predicted_sentiment"] == item["expected_sentiment"]
        for item in details
    )
    red_flag_positives = sum(item["expected_red_flag"] for item in details)
    true_positives = sum(
        item["expected_red_flag"] and item["predicted_red_flag"]
        for item in details
    )
    false_negatives = red_flag_positives - true_positives
    false_positives = sum(
        not item["expected_red_flag"] and item["predicted_red_flag"]
        for item in details
    )

    confusion = {
        expected: {
            predicted: sum(
                item["expected_sentiment"] == expected
                and (item["predicted_sentiment"] or "NO_DISPONIBLE") == predicted
                for item in details
            )
            for predicted in ["Positivo", "Neutral", "Negativo", "NO_DISPONIBLE"]
        }
        for expected in ["Positivo", "Neutral", "Negativo"]
    }

    return {
        "sample_size": total,
        "analysis_available": available,
        "unavailable_or_failed": total - available,
        "coverage": round(available / total, 4),
        # Los análisis no disponibles cuentan como incorrectos en accuracy.
        "sentiment_accuracy": round(correct / total, 4),
        "sentiment_correct": correct,
        "sentiment_confusion_matrix": confusion,
        "red_flag": {
            "expected_positive_cases": red_flag_positives,
            "true_positives": true_positives,
            "false_negatives": false_negatives,
            "false_positives": false_positives,
            "recall": round(true_positives / red_flag_positives, 4) if red_flag_positives else None,
        },
        "latency_seconds": {
            "mean": round(sum(latencies) / total, 4),
            "p50": round(percentile(latencies, 0.50) or 0, 4),
            "p95": round(percentile(latencies, 0.95) or 0, 4),
            "min": round(min(latencies), 4),
            "max": round(max(latencies), 4),
        },
        "expected_sentiment_distribution": dict(Counter(item["expected_sentiment"] for item in details)),
        "per_case": details,
    }


def validate_azure_configuration() -> None:
    required = [
        "AZURE_LANGUAGE_ENDPOINT",
        "AZURE_LANGUAGE_KEY",
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_API_KEY",
    ]
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise ValueError(
            "Faltan variables para ejecutar el pipeline real de Azure: " + ", ".join(missing)
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", required=True, type=Path, help="CSV con las etiquetas esperadas por humanos.")
    parser.add_argument(
        "--output", type=Path,
        help="Ruta JSON de resultados. Por defecto, se crea un archivo con fecha dentro de documentos/.",
    )
    parser.add_argument(
        "--delay-seconds", type=float, default=1.0,
        help="Pausa entre casos para espaciar solicitudes a Azure (predeterminado: 1 segundo).",
    )
    parser.add_argument(
        "--min-samples", type=int, default=MINIMUM_SAMPLE_SIZE,
        help="Tamaño mínimo requerido (200 para reportar el criterio del MVP; predeterminado: 200).",
    )
    parser.add_argument(
        "--target-latency-seconds", type=float, default=3.0,
        help="Objetivo del MVP para inferencia IA; solo se reporta como referencia.",
    )
    args = parser.parse_args()

    try:
        if args.delay_seconds < 0 or args.min_samples < 1 or args.target_latency_seconds <= 0:
            raise ValueError("delay-seconds debe ser >= 0; min-samples y target-latency-seconds deben ser > 0.")
        if not args.csv.is_file():
            raise ValueError(f"No existe el archivo CSV: {args.csv}")
        validate_azure_configuration()
        cases = load_cases(args.csv)
        if len(cases) < args.min_samples:
            raise ValueError(
                f"El conjunto tiene {len(cases)} casos; se requieren al menos {args.min_samples}."
            )

        print(
            f"Iniciando evaluación de {len(cases)} casos con el deployment "
            f"{os.getenv('AZURE_OPENAI_DEPLOYMENT_NAME', 'gpt-4.1-mini-1')}. "
            "El script no guarda los comentarios en PostgreSQL."
        )
        metrics = evaluate(cases, args.delay_seconds)
        scored_metrics = {
            **{key: value for key, value in metrics.items() if key != "per_case"},
            "targets": {
                "sentiment_accuracy_minimum": 0.85,
                "red_flag_recall_minimum": 0.95,
                "latency_p95_seconds_maximum": args.target_latency_seconds,
                "accuracy_pass": metrics["sentiment_accuracy"] >= 0.85,
                "recall_pass": (
                    metrics["red_flag"]["recall"] is not None
                    and metrics["red_flag"]["recall"] >= 0.95
                ),
                "latency_p95_pass": metrics["latency_seconds"]["p95"] < args.target_latency_seconds,
            },
        }
        report = {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "dataset": args.csv.name,
            "deployment_name": os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4.1-mini-1"),
            "pipeline": "Azure AI Language (polaridad) + Azure OpenAI/LangChain (riesgo cualitativo)",
            "latency_scope": "Sanitización local más el pipeline dual de IA; excluye HTTP, UI y escritura en PostgreSQL.",
            "metrics": scored_metrics,
            "per_case": metrics["per_case"],
        }
        output_path = args.output or (
            ROOT / "documentos" / f"evaluacion_modelo_{datetime.now(timezone.utc):%Y%m%d_%H%M%S}Z.json"
        )
        output_path = output_path.resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

        print(f"Accuracy de polaridad: {metrics['sentiment_accuracy']:.1%} ({metrics['sentiment_correct']}/{metrics['sample_size']}).")
        recall = metrics["red_flag"]["recall"]
        print(
            "Recall de banderas rojas: "
            + (f"{recall:.1%}" if recall is not None else "no calculable: el conjunto no tiene positivos esperados")
            + f" ({metrics['red_flag']['true_positives']}/{metrics['red_flag']['expected_positive_cases']})."
        )
        print(
            f"Latencia del pipeline IA: media {metrics['latency_seconds']['mean']:.2f}s, "
            f"p95 {metrics['latency_seconds']['p95']:.2f}s (objetivo <{args.target_latency_seconds:.2f}s)."
        )
        print(f"Cobertura: {metrics['coverage']:.1%}; reporte: {output_path}")
        return 0
    except (OSError, ValueError, csv.Error) as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
