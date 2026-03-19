#!/usr/bin/env python3
"""report.py — 개선 루프 종료 후 이력 요약 리포트를 생성한다.

히스토리 파일(.jsonl)을 읽어 텍스트 히스토그램, 최고 점수 시점,
LLM 호출 추정, 최근 커밋 메시지를 출력한다.

Usage:
    python report.py <skill_name> [--log-path <path>]
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

CONFIG_PATH = Path(__file__).parent.parent / "autoimprove.config.json"

# ANSI 컬러 코드
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        print(f"오류: 설정 파일을 찾을 수 없습니다: {CONFIG_PATH}", file=sys.stderr)
        sys.exit(1)
    with open(CONFIG_PATH) as f:
        return json.load(f)


def resolve_path(p: str) -> Path:
    return Path(p).expanduser().resolve()


def find_latest_log(log_dir: Path, skill_name: str) -> Path | None:
    """가장 최근 히스토리 파일을 찾는다. .jsonl 우선, .json 폴백."""
    # JSONL 파일 검색 (신규 형식)
    jsonl_logs = sorted(log_dir.glob(f"{skill_name}-history.jsonl"), reverse=True)
    if jsonl_logs:
        return jsonl_logs[0]

    # JSON 파일 검색 (구 형식 호환)
    json_logs = sorted(log_dir.glob(f"{skill_name}_*.json"), reverse=True)
    return json_logs[0] if json_logs else None


def load_history(log_path: Path) -> list[dict]:
    """히스토리 파일을 로드한다. JSONL과 JSON 모두 지원."""
    if log_path.suffix == ".jsonl":
        entries: list[dict] = []
        with open(log_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
        return entries

    # 구 형식 JSON (배열)
    with open(log_path, encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else []


def render_histogram(history: list[dict], width: int = 40) -> str:
    """텍스트 히스토그램으로 점수 변화를 시각화한다."""
    if not history:
        return "  (히스토리 없음)"

    lines: list[str] = []
    lines.append(f"\n{BOLD}점수 변화 히스토그램{RESET}")
    lines.append(f"{'─' * (width + 25)}")

    # 최고 점수 시점 찾기
    best_score = 0.0
    best_iteration = 0
    for entry in history:
        score = entry.get("best_score", entry.get("score", 0))
        if score > best_score:
            best_score = score
            best_iteration = entry.get("iteration", 0)

    for entry in history:
        iteration = entry.get("iteration", 0)
        score = entry.get("score", 0)
        action = entry.get("action", "")

        bar_len = int(score * width)
        bar = "█" * bar_len + "░" * (width - bar_len)
        pct = f"{score:.0%}".rjust(4)

        # 액션별 아이콘
        icon_map: dict[str, str] = {
            "initial": f"{CYAN}->",
            "commit": f"{GREEN}OK",
            "rollback": f"{RED}RB",
            "skip_llm_fail": f"{YELLOW}SK",
        }
        icon = icon_map.get(action, "  ")

        # 최고 점수 시점 표시
        best_marker = ""
        if iteration == best_iteration and action != "initial":
            best_marker = f" {YELLOW}<-- 최고{RESET}"

        # 점수에 따른 바 색상
        if score >= 1.0:
            bar_color = GREEN
        elif score >= 0.6:
            bar_color = YELLOW
        else:
            bar_color = RED

        lines.append(
            f"  {icon}{RESET} iter {iteration:>3} "
            f"|{bar_color}{bar}{RESET}| {pct}{best_marker}"
        )

    lines.append(f"{'─' * (width + 25)}")
    return "\n".join(lines)


def estimate_llm_calls(history: list[dict]) -> int:
    """LLM 호출 횟수를 추정한다.

    각 반복마다:
    - assertion 채점: 1회 이상 (보통 assertion 수만큼, 하지만 여기선 반복당 ~25회로 추정)
    - SKILL.md 개선: 1회 (skip_llm_fail 제외)
    - 재채점: 1회 이상

    단순화: initial + skip_llm_fail = assertion만, 나머지 = assertion + improve + assertion
    """
    calls = 0
    for entry in history:
        action = entry.get("action", "")
        if action == "initial":
            calls += 25  # 초기 채점 (assertion 수 추정)
        elif action == "skip_llm_fail":
            calls += 26  # 채점 + 개선 시도 1회
        elif action in ("commit", "rollback"):
            calls += 51  # 채점 + 개선 + 재채점
    return calls


def get_recent_commits(skill_dir: Path, count: int = 5) -> list[str]:
    """최근 커밋 메시지를 반환한다."""
    try:
        result = subprocess.run(
            ["git", "log", f"--max-count={count}", "--oneline"],
            cwd=str(skill_dir),
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip().split("\n")
    except Exception:
        pass
    return []


def generate_report(
    skill_name: str,
    history: list[dict],
    skill_dir: Path | None = None,
) -> str:
    """텍스트 리포트를 생성한다."""
    if not history:
        return f"  {skill_name}에 대한 히스토리가 없습니다."

    initial = history[0]
    final = history[-1]
    initial_score: float = initial.get("score", 0)
    final_score: float = final.get("best_score", final.get("score", 0))

    commits = sum(1 for h in history if h.get("action") == "commit")
    rollbacks = sum(1 for h in history if h.get("action") == "rollback")
    skips = sum(1 for h in history if h.get("action") == "skip_llm_fail")
    total_iters = len(history) - 1  # initial 제외

    # 최고 점수 시점
    best_score = 0.0
    best_iteration = 0
    for entry in history:
        score = entry.get("best_score", entry.get("score", 0))
        if score > best_score:
            best_score = score
            best_iteration = entry.get("iteration", 0)

    llm_calls = estimate_llm_calls(history)

    lines: list[str] = [
        f"\n{'=' * 60}",
        f"  {BOLD}AutoImprove Report: {skill_name}{RESET}",
        f"{'=' * 60}",
        "",
        f"  초기 점수   : {initial_score:.0%}",
        f"  최종 점수   : {BOLD}{final_score:.0%}{RESET}",
        f"  개선 폭     : {'+' if final_score > initial_score else ''}{final_score - initial_score:.0%}",
        f"  최고 점수   : {best_score:.0%} (iter {best_iteration})",
        "",
        f"  총 반복     : {total_iters}",
        f"  커밋 (개선) : {GREEN}{commits}{RESET}",
        f"  롤백        : {RED}{rollbacks}{RESET}",
        f"  건너뜀      : {YELLOW}{skips}{RESET}",
        f"  추정 LLM 호출 : ~{llm_calls}회",
        "",
        render_histogram(history),
        "",
    ]

    # 커밋 이력 요약
    commit_entries = [h for h in history if h.get("action") == "commit"]
    if commit_entries:
        lines.append(f"{BOLD}개선 이력{RESET}")
        lines.append("─" * 40)
        for entry in commit_entries:
            i = entry.get("iteration", "?")
            s = entry.get("score", 0)
            bs = entry.get("best_score", s)
            ts = entry.get("timestamp", "")
            time_str = ts[11:19] if len(ts) >= 19 else ""
            lines.append(
                f"  iter {i:>3}: {GREEN}{bs:.0%}{RESET}"
                f"  {DIM}{time_str}{RESET}"
            )
        lines.append("")

    # 최근 git 커밋 메시지
    if skill_dir and skill_dir.exists():
        recent = get_recent_commits(skill_dir, count=5)
        if recent:
            lines.append(f"{BOLD}최근 커밋 (최대 5개){RESET}")
            lines.append("─" * 40)
            for msg in recent:
                lines.append(f"  {DIM}{msg}{RESET}")
            lines.append("")

    # 최종 메시지
    if final_score >= 1.0:
        lines.append(f"  {GREEN}{BOLD}100% 달성! 완벽한 스킬입니다!{RESET}")
    elif final_score > initial_score:
        delta = final_score - initial_score
        lines.append(f"  {GREEN}점수가 {delta:.0%} 개선되었습니다.{RESET}")
    else:
        lines.append(f"  {YELLOW}이번 루프에서 개선이 없었습니다.{RESET}")

    lines.append(f"{'=' * 60}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="AutoImprove 개선 이력 리포트를 생성합니다.",
        epilog="예시: python report.py comet-agent",
    )
    parser.add_argument("skill_name", help="스킬 이름")
    parser.add_argument("--log-path", help="특정 로그 파일 경로 (기본: 최신 파일 자동 탐색)")
    args = parser.parse_args()

    config = load_config()
    log_dir = resolve_path(
        config.get("log_dir", "~/.openclaw/skills/skill-autoimprove/logs")
    )
    skills_base = resolve_path(config["skills_base_dir"])
    skill_dir = skills_base / args.skill_name

    if args.log_path:
        log_path: Path | None = resolve_path(args.log_path)
    else:
        log_path = find_latest_log(log_dir, args.skill_name)

    if not log_path or not log_path.exists():
        print(
            f"오류: {args.skill_name}에 대한 로그를 찾을 수 없습니다.\n"
            f"검색 경로: {log_dir}",
            file=sys.stderr,
        )
        sys.exit(1)

    history = load_history(log_path)
    report = generate_report(args.skill_name, history, skill_dir)
    print(report)

    # 리포트 파일 저장
    log_dir.mkdir(parents=True, exist_ok=True)
    report_path = log_dir / f"{args.skill_name}_report.txt"

    # ANSI 코드 제거하여 파일 저장
    import re

    clean_report = re.sub(r"\033\[[0-9;]*m", "", report)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(clean_report)
    print(f"\n{DIM}리포트 저장: {report_path}{RESET}")


if __name__ == "__main__":
    main()
