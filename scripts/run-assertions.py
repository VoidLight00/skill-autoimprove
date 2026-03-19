#!/usr/bin/env python3
"""run-assertions.py — eval.json의 각 assertion을 LLM으로 채점한다.

Usage:
    python run-assertions.py <skill_name> [--eval-path <path>] [--verbose]
"""

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
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


def load_eval(eval_path: Path) -> dict:
    try:
        with open(eval_path) as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"오류: eval.json 파싱 실패 ({eval_path}): {e}", file=sys.stderr)
        sys.exit(1)


def load_skill_md(skill_md_path: Path) -> str:
    return skill_md_path.read_text(encoding="utf-8")


def judge_assertion(
    skill_content: str,
    assertion: str,
    llm_cmd: str,
    *,
    verbose: bool = False,
    timeout: int = 60,
) -> tuple[bool, str]:
    """LLM에게 assertion의 pass/fail을 판단시킨다.

    Returns:
        (passed, raw_output) 튜플
    """
    prompt = (
        "You are a strict evaluator. Given the following SKILL.md content, "
        "determine if the assertion is TRUE or FALSE.\n\n"
        f"<SKILL_MD>\n{skill_content}\n</SKILL_MD>\n\n"
        f"<ASSERTION>\n{assertion}\n</ASSERTION>\n\n"
        "Respond with exactly one word: PASS or FAIL. Nothing else."
    )

    max_attempts = 2  # 타임아웃 시 1회 재시도
    for attempt in range(max_attempts):
        try:
            result = subprocess.run(
                [*llm_cmd.split(), prompt],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            raw_output = result.stdout.strip()
            upper = raw_output.upper()

            if verbose:
                print(f"    {DIM}LLM 응답: {raw_output}{RESET}")

            if "PASS" in upper and "FAIL" not in upper:
                return True, raw_output
            if "FAIL" in upper:
                return False, raw_output

            # PASS/FAIL 어느 것도 명확하지 않은 경우
            print(
                f"    {YELLOW}[경고] 판단 불가 응답 → FAIL 처리: "
                f"{raw_output[:80]}{RESET}",
                file=sys.stderr,
            )
            return False, raw_output

        except subprocess.TimeoutExpired:
            if attempt < max_attempts - 1:
                print(
                    f"    {YELLOW}[타임아웃] 재시도 중... "
                    f"({attempt + 1}/{max_attempts}){RESET}"
                )
                continue
            print(f"    {RED}[타임아웃] {assertion}{RESET}", file=sys.stderr)
            return False, "[TIMEOUT]"
        except FileNotFoundError:
            print(
                f"    {RED}[오류] LLM 명령어를 찾을 수 없습니다: {llm_cmd}{RESET}",
                file=sys.stderr,
            )
            sys.exit(1)
        except Exception as e:
            print(f"    {RED}[오류] {assertion}: {e}{RESET}", file=sys.stderr)
            return False, f"[ERROR: {e}]"

    return False, "[TIMEOUT after retries]"


def run_assertions(
    eval_data: dict,
    config: dict,
    *,
    verbose: bool = False,
) -> list[dict]:
    """모든 assertion을 실행하고 결과를 반환한다."""
    skill_md_path = resolve_path(eval_data["skill_md_path"])
    if not skill_md_path.exists():
        print(
            f"오류: SKILL.md를 찾을 수 없습니다: {skill_md_path}",
            file=sys.stderr,
        )
        sys.exit(1)

    skill_content = load_skill_md(skill_md_path)
    llm_cmd: str = config.get("llm_command", "claude -p")
    results: list[dict] = []
    failed_assertions: list[str] = []

    total = sum(len(t["assertions"]) for t in eval_data["tests"])
    passed = 0
    idx = 0
    start_time = time.monotonic()

    for test in eval_data["tests"]:
        test_id: str = test["id"]
        description: str = test.get("description", "")
        print(f"\n{BOLD}[{test_id}] {description}{RESET}")

        for assertion in test["assertions"]:
            idx += 1
            assertion_start = time.monotonic()
            result, raw_output = judge_assertion(
                skill_content, assertion, llm_cmd, verbose=verbose
            )
            assertion_elapsed = time.monotonic() - assertion_start

            if result:
                passed += 1
                color = GREEN
                status = "PASS"
            else:
                color = RED
                status = "FAIL"
                failed_assertions.append(assertion)

            print(
                f"  [{idx}/{total}] {color}{status}{RESET} — {assertion}"
                f"  {DIM}({assertion_elapsed:.1f}s){RESET}"
            )

            results.append({
                "test_id": test_id,
                "assertion": assertion,
                "result": "pass" if result else "fail",
                "score": 1 if result else 0,
                "elapsed_seconds": round(assertion_elapsed, 2),
            })

    total_elapsed = time.monotonic() - start_time

    # 결과 요약
    print(f"\n{'=' * 60}")
    if total > 0:
        pct = passed / total * 100
        color = GREEN if pct == 100 else (YELLOW if pct >= 60 else RED)
        print(f"  점수: {color}{BOLD}{passed}/{total} ({pct:.1f}%){RESET}")
    else:
        print("  assertion이 없습니다.")

    print(f"  소요 시간: {total_elapsed:.1f}초")

    # 실패한 assertion 별도 출력
    if failed_assertions:
        print(f"\n{RED}{BOLD}실패한 assertions ({len(failed_assertions)}개):{RESET}")
        for i, a in enumerate(failed_assertions, 1):
            print(f"  {RED}{i}. {a}{RESET}")

    print(f"{'=' * 60}")
    return results


def main() -> dict:
    parser = argparse.ArgumentParser(
        description="eval.json의 assertion을 SKILL.md에 대해 채점합니다.",
        epilog="예시: python run-assertions.py comet-agent --verbose",
    )
    parser.add_argument("skill_name", help="평가할 스킬 이름")
    parser.add_argument("--eval-path", help="eval.json 경로 (기본: 자동 탐색)")
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="LLM 응답 원문 출력"
    )
    args = parser.parse_args()

    config = load_config()
    skills_base = resolve_path(config["skills_base_dir"])

    if args.eval_path:
        eval_path = resolve_path(args.eval_path)
    else:
        eval_subdir: str = config.get("eval_subdir", "eval")
        eval_filename: str = config.get("eval_filename", "eval.json")
        eval_path = skills_base / args.skill_name / eval_subdir / eval_filename

    if not eval_path.exists():
        print(
            f"오류: eval.json을 찾을 수 없습니다: {eval_path}\n"
            "먼저 gen-eval.py를 실행하여 eval.json을 생성하세요.",
            file=sys.stderr,
        )
        sys.exit(1)

    start_time = time.monotonic()
    eval_data = load_eval(eval_path)
    results = run_assertions(eval_data, config, verbose=args.verbose)
    total_elapsed = time.monotonic() - start_time

    output = {
        "skill_name": args.skill_name,
        "total": len(results),
        "passed": sum(1 for r in results if r["result"] == "pass"),
        "score": (
            sum(r["score"] for r in results) / len(results) if results else 0
        ),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": round(total_elapsed, 2),
        "results": results,
    }

    output_path = eval_path.parent / "results.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\n결과 저장: {output_path}")
    return output


if __name__ == "__main__":
    main()
