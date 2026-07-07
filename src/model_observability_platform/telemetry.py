from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .io import write_csv


FEATURES = ["age", "income", "debt_ratio", "utilization", "delinquencies"]


def generate_window(path: str | Path, *, window: str, rows: int = 500, seed: int = 42, drift: bool = False, errors: bool = False) -> Path:
    rng = random.Random(seed + (11 if drift else 0) + (19 if errors else 0))
    started = datetime(2026, 7, 7, 12, 0, tzinfo=timezone.utc)
    records = []
    for idx in range(rows):
        age = max(18, int(rng.gauss(42 if not drift else 35, 11)))
        income = max(22000, rng.gauss(76000 if not drift else 59000, 21000))
        debt_ratio = min(max(rng.gauss(0.38 if not drift else 0.62, 0.16), 0.02), 1.7)
        utilization = min(max(rng.gauss(0.44 if not drift else 0.72, 0.22), 0.0), 1.4)
        delinquencies = max(0, int(rng.gauss(0.5 if not drift else 1.5, 0.9)))
        score = min(max(0.08 + debt_ratio * 0.34 + utilization * 0.28 + delinquencies * 0.09 - income / 500000, 0), 0.99)
        if drift:
            score = min(score + 0.12, 0.99)
        status = "error" if errors and rng.random() < 0.035 else "success"
        latency = max(8.0, rng.gauss(31 if not errors else 95, 9 if not errors else 28))
        records.append(
            {
                "timestamp": (started + timedelta(seconds=idx * 8)).isoformat(),
                "window": window,
                "request_id": f"{window}_req_{idx:05d}",
                "model_version": "risk-model-2026-07-15" if not drift else "risk-model-2026-07-15",
                "status": status,
                "latency_ms": round(latency, 3),
                "prediction": 1 if score >= 0.65 else 0,
                "risk_score": round(score, 6),
                "age": age,
                "income": round(income, 2),
                "debt_ratio": round(debt_ratio, 4),
                "utilization": round(utilization, 4),
                "delinquencies": delinquencies,
            }
        )
    return write_csv(path, records)
