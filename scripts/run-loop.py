#!/usr/bin/env python3
"""run-loop.py — Karpathy autoresearch 스타일 자율 개선 루프.

SKILL.md를 반복적으로 개선하고, 점수가 오르면 커밋, 내리면 롤백한다.

Usage:
    python run-loop.py <skill_name> [--max-iter 20] [--timeout 3600]
"""

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

CONFIG_PATH = Path(__file__).parent.parent / "autoimprove.config.json"
SCRIPTS_DIR = Path(__file__).parent


def load_config() -> dict:
    with open(CONFIG_PATH) as f:
        return json.load(f)


def resolve_path(p: str) -> Path:
    return Path(p).expanduser().resolve()


def get_score(skill_name: str, eval_path: str | None = None) -> float:
    """run-assertions.py를 실행하여 현재 점수를 반환한다."""
    cmd = [sys.executable, str(SCRIPTS_DIR / "run-assertions.py"), skill_name]
    if eval_path:
        cmd.extend(["--eval-path", eval_path])

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)

    config = load_config()
    skills_base = resolve_path(config["skills_base_dir"])
    if eval_path:
        results_path = resolve_path(eval_path).parent / "results.json"
    else:
        eval_subdir = config.get("eval_subdir", "eval")
        results_path = skills_base / skill_name / eval_subdir / "results.json"

    if results_path.exists():
        with open(results_path) as f:
            data = json.load(f)
        return data.get("score", 0.0)
    return 0.0


def get_failed_assertions(skill_name: str, config: dict, eval_path: str | None = None) -> list[str]:
    """실패한 assertion 목록을 반환한다."""
    skills_base = resolve_path(config["skills_base_dir"])
    if eval_path:
        results_path = resolve_path(eval_path).parent / "results.json"
    else:
        eval_subdir = config.get("eval_subdir", "eval")
        results_path = skills_base / skill_name / eval_subdir / "results.json"

    if not results_path.exists():
        return []

    with open(results_path) as f:
        data = json.load(f)

    return [r["assertion"] for r in data.get("results", []) if r["result"] == "fail"]


def improve_skill(skill_md_path: Path, failed_assertions: list[str], llm_cmd: str, iteration: int) -> bool:
    """LLM을 사용하여 SKILL.md를 개선한다."""
    skill_content = skill_md_path.read_text()

    failed_list = "\n".join(f"- {a}" for a in failed_assertions)
    prompt = f"""You are an expert skill author for OpenClaw (Claude Code skill system).
The following SKILL.md needs improvement. Some assertions are failing.

<CURRENT_SKILL_MD>
{skill_content}
</CURRENT_SKILL_MD>

<FAILED_ASSERTIONS>
{failed_list}
</FAILED_ASSERTIONS>

Iteration: {iteration}

Rewrite the SKILL.md to pass all failed assertions while keeping the existing passing content intact.
Rules:
- Output ONLY the complete new SKILL.md content, nothing else
- Do not add markdown code fences
- Preserve the skill's core purpose and functionality
- Make minimal changes to fix the failing assertions
- Keep the same overall structure"""

    try:
        result = subprocess.run(
            [*llm_cmd.split(), prompt],
            capture_output=True,
            text=True,
            timeout=120,
        )
        new_content = result.stdout.strip()
        if not new_content or len(new_content) < 50:
            print("  [WARN] LLM returned insufficient content, skipping")
            return False

        skill_md_path.write_text(new_content + "\n")
        return True
    except Exception as e:
        print(f"  [ERROR] LLM improvement failed: {e}", file=sys.stderr)
        return False


def git_commit(skill_dir: Path, message: str):
    """변경 사항을 커밋한다."""
    subprocess.run(["git", "add", "."], cwd=skill_dir, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", message],
        cwd=skill_dir,
        capture_output=True,
    )


def git_reset(skill_dir: Path):
    """마지막 커밋으로 롤백한다."""
    subprocess.run(
        ["git", "checkout", "--", "."],
        cwd=skill_dir,
        capture_output=True,
    )


def run_loop(skill_name: str, max_iter: int, timeout: int, eval_path: str | None = None):
    """메인 개선 루프."""
    config = load_config()
    skills_base = resolve_path(config["skills_base_dir"])
    skill_dir = skills_base / skill_name
    skill_md_path = skill_dir / "SKILL.md"
    llm_cmd = config.get("llm_command", "claude -p")

    if not skill_md_path.exists():
        print(f"Error: {skill_md_path} not found", file=sys.stderr)
        sys.exit(1)

    log_dir = resolve_path(config.get("log_dir", "~/.openclaw/skills/skill-autoimprove/logs"))
    log_dir.mkdir(parents=True, exist_ok=True)

    history = []
    start_time = time.time()

    print(f"{'=' * 60}")
    print(f"AutoImprove Loop: {skill_name}")
    print(f"Max iterations: {max_iter} | Timeout: {timeout}s")
    print(f"{'=' * 60}")

    # 초기 점수
    print("\n[Initial] Scoring...")
    best_score = get_score(skill_name, eval_path)
    print(f"Initial score: {best_score:.2%}")

    history.append({
        "iteration": 0,
        "score": best_score,
        "action": "initial",
        "timestamp": datetime.now().isoformat(),
    })

    if best_score >= 1.0:
        print("\nAll assertions pass! Nothing to improve.")
        save_history(log_dir, skill_name, history)
        return history

    for i in range(1, max_iter + 1):
        elapsed = time.time() - start_time
        if elapsed > timeout:
            print(f"\n[Timeout] {elapsed:.0f}s elapsed, stopping.")
            break

        print(f"\n{'─' * 60}")
        print(f"[Iteration {i}/{max_iter}] elapsed: {elapsed:.0f}s")

        # 실패한 assertion 확인
        failed = get_failed_assertions(skill_name, config, eval_path)
        if not failed:
            print("All assertions pass!")
            break

        print(f"  Failed assertions: {len(failed)}")

        # LLM으로 개선 시도
        print("  Improving SKILL.md...")
        improved = improve_skill(skill_md_path, failed, llm_cmd, i)
        if not improved:
            history.append({
                "iteration": i,
                "score": best_score,
                "action": "skip_llm_fail",
                "timestamp": datetime.now().isoformat(),
            })
            continue

        # 새 점수 확인
        print("  Re-scoring...")
        new_score = get_score(skill_name, eval_path)

        if new_score > best_score:
            print(f"  IMPROVED: {best_score:.2%} → {new_score:.2%}")
            git_commit(skill_dir, f"autoimprove: {skill_name} {best_score:.2%} → {new_score:.2%} (iter {i})")
            best_score = new_score
            action = "commit"
        else:
            print(f"  NO IMPROVEMENT: {best_score:.2%} → {new_score:.2%}, rolling back")
            git_reset(skill_dir)
            action = "rollback"

        history.append({
            "iteration": i,
            "score": new_score,
            "best_score": best_score,
            "action": action,
            "failed_count": len(failed),
            "timestamp": datetime.now().isoformat(),
        })

        if best_score >= 1.0:
            print("\nPerfect score achieved!")
            break

    print(f"\n{'=' * 60}")
    print(f"Final score: {best_score:.2%}")
    print(f"Total iterations: {len(history) - 1}")
    print(f"Elapsed: {time.time() - start_time:.0f}s")

    save_history(log_dir, skill_name, history)
    return history


def save_history(log_dir: Path, skill_name: str, history: list[dict]):
    """개선 이력을 저장한다."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = log_dir / f"{skill_name}_{timestamp}.json"
    with open(log_path, "w") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)
    print(f"History saved to {log_path}")


def main():
    parser = argparse.ArgumentParser(description="Autoimprove loop for SKILL.md")
    parser.add_argument("skill_name", help="Name of the skill to improve")
    parser.add_argument("--max-iter", type=int, default=None, help="Max iterations")
    parser.add_argument("--timeout", type=int, default=None, help="Timeout in seconds")
    parser.add_argument("--eval-path", help="Custom path to eval.json")
    args = parser.parse_args()

    config = load_config()
    max_iter = args.max_iter or config.get("max_iterations", 20)
    timeout = args.timeout or config.get("timeout_seconds", 3600)

    run_loop(args.skill_name, max_iter, timeout, args.eval_path)


if __name__ == "__main__":
    main()
