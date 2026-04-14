from __future__ import annotations

from collections import defaultdict
from typing import Any


def aggregate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[(str(row["defense_profile"]), str(row["permission_profile"]))].append(row)

    output: list[dict[str, Any]] = []
    for (defense, permission), group in sorted(groups.items()):
        adversarial = [row for row in group if row["variant"] == "adversarial"]
        benign = [row for row in group if row["variant"] == "benign"]
        output.append(
            {
                "defense_profile": defense,
                "permission_profile": permission,
                "runs": len(group),
                "adversarial_runs": len(adversarial),
                "benign_runs": len(benign),
                "asr_percent": percent(sum_int(adversarial, "attack_success"), len(adversarial)),
                "btsr_percent": percent(sum_int(benign, "benign_success"), len(benign)),
                "false_positive_rate": percent(sum_int(benign, "false_positive"), len(benign)),
                "false_negative_rate": percent(sum_int(adversarial, "false_negative"), len(adversarial)),
                "avg_user_steps": average(group, "user_steps"),
                "avg_latency_seconds": average(group, "latency_seconds"),
            }
        )
    return output


def sum_int(rows: list[dict[str, Any]], key: str) -> int:
    return sum(int(row.get(key, 0) or 0) for row in rows)


def percent(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round(100.0 * numerator / denominator, 2)


def average(rows: list[dict[str, Any]], key: str) -> float:
    if not rows:
        return 0.0
    return round(sum(float(row.get(key, 0) or 0) for row in rows) / len(rows), 4)

