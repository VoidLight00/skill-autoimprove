#!/usr/bin/env python3
"""report.py — 개선 루프 종료 후 이력 요약 리포트를 생성한다.

Usage:
    python report.py <skill_name>
"""

import argparse
import json
import sys
from pathlib import Path

CONFIG_PATH = Path(__file__).parent.parent / "autoimprove.config.json"


def load_config() -> dict:
    with open(CONFIG_PATH) as f:
        return json.load(f)


def resolve_path(p: str) -> Path:
    return Path(p).expanduser().resolve()


def find_latest_log(log_dir: Path, skill_name: str) -> Path | None:
    """가장 최근 로그 파일을 찾는다."""
    logs = sorted(log_dir.glob(f"{skill_name}_*.json"), reverse=True)
    return logs[0] if logs else None


def render_score_graph(history: list[dict], width: int = 40) -> str:
    """텍스트 기반 점수 변화 그래프를 렌더링한다."""
    lines = []
    lines.append("Score Progress")
    lines.append("─" * (width + 20))

    for entry in history:
        iteration = entry.get("iteration", 0)
        score = entry.get("score", 0)
        action = entry.get("action", "")

        bar_len = int(score * width)
        bar = "█" * bar_len + "░" * (width - bar_len)
        pct = f"{score:.0%}".rjust(4)

        icon = {
            "initial": "🔵",
            "commit": "✅",
            "rollback": "❌",
            "skip_llm_fail": "⚠️",
        }.get(action, "  ")

        lines.append(f"  {icon} iter {iteration:>3} |{bar}| {pct}")

    lines.append("─" * (width + 20))
    return "\n".join(lines)


def generate_report(skill_name: str, history: list[dict]) -> str:
    """텍스트 리포트를 생성한다."""
    if not history:
        return f"No history found for {skill_name}"

    initial = history[0]
    final = history[-1]
    initial_score = initial.get("score", 0)
    final_score = final.get("best_score", final.get("score", 0))

    commits = sum(1 for h in history if h.get("action") == "commit")
    rollbacks = sum(1 for h in history if h.get("action") == "rollback")
    total_iters = len(history) - 1  # initial 제외

    report_lines = [
        f"{'=' * 60}",
        f"  AutoImprove Report: {skill_name}",
        f"{'=' * 60}",
        "",
        f"  Initial score : {initial_score:.0%}",
        f"  Final score   : {final_score:.0%}",
        f"  Improvement   : {final_score - initial_score:+.0%}",
        "",
        f"  Total iterations : {total_iters}",
        f"  Commits (improved) : {commits}",
        f"  Rollbacks          : {rollbacks}",
        "",
        render_score_graph(history),
        "",
    ]

    # 커밋 이력 요약
    commit_entries = [h for h in history if h.get("action") == "commit"]
    if commit_entries:
        report_lines.append("Commit History")
        report_lines.append("─" * 40)
        for entry in commit_entries:
            i = entry.get("iteration", "?")
            s = entry.get("score", 0)
            bs = entry.get("best_score", s)
            report_lines.append(f"  iter {i}: score → {bs:.0%}")
        report_lines.append("")

    if final_score >= 1.0:
        report_lines.append("  ✨ Perfect score achieved!")
    elif final_score > initial_score:
        report_lines.append(f"  📈 Score improved by {final_score - initial_score:.0%}")
    else:
        report_lines.append("  📊 No improvement achieved")

    report_lines.append(f"{'=' * 60}")
    return "\n".join(report_lines)


def main():
    parser = argparse.ArgumentParser(description="Generate autoimprove report")
    parser.add_argument("skill_name", help="Name of the skill")
    parser.add_argument("--log-path", help="Specific log file path")
    args = parser.parse_args()

    config = load_config()
    log_dir = resolve_path(config.get("log_dir", "~/.openclaw/skills/skill-autoimprove/logs"))

    if args.log_path:
        log_path = resolve_path(args.log_path)
    else:
        log_path = find_latest_log(log_dir, args.skill_name)

    if not log_path or not log_path.exists():
        print(f"No logs found for {args.skill_name}", file=sys.stderr)
        print(f"Searched in: {log_dir}", file=sys.stderr)
        sys.exit(1)

    with open(log_path) as f:
        history = json.load(f)

    report = generate_report(args.skill_name, history)
    print(report)

    # 리포트 파일 저장
    report_path = log_dir / f"{args.skill_name}_report.txt"
    with open(report_path, "w") as f:
        f.write(report)
    print(f"\nReport saved to {report_path}")


if __name__ == "__main__":
    main()
