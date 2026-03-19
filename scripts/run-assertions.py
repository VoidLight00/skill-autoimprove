#!/usr/bin/env python3
"""run-assertions.py — eval.json의 각 assertion을 LLM으로 채점한다.

Usage:
    python run-assertions.py <skill_name> [--eval-path <path>]
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

CONFIG_PATH = Path(__file__).parent.parent / "autoimprove.config.json"


def load_config() -> dict:
    with open(CONFIG_PATH) as f:
        return json.load(f)


def resolve_path(p: str) -> Path:
    return Path(p).expanduser().resolve()


def load_eval(eval_path: Path) -> dict:
    with open(eval_path) as f:
        return json.load(f)


def load_skill_md(skill_md_path: Path) -> str:
    with open(skill_md_path) as f:
        return f.read()


def judge_assertion(skill_content: str, assertion: str, llm_cmd: str) -> bool:
    """LLM에게 assertion의 pass/fail을 판단시킨다."""
    prompt = f"""You are a strict evaluator. Given the following SKILL.md content, determine if the assertion is TRUE or FALSE.

<SKILL_MD>
{skill_content}
</SKILL_MD>

<ASSERTION>
{assertion}
</ASSERTION>

Respond with exactly one word: PASS or FAIL. Nothing else."""

    try:
        result = subprocess.run(
            [*llm_cmd.split(), prompt],
            capture_output=True,
            text=True,
            timeout=60,
        )
        output = result.stdout.strip().upper()
        return "PASS" in output
    except subprocess.TimeoutExpired:
        print(f"  [TIMEOUT] {assertion}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"  [ERROR] {assertion}: {e}", file=sys.stderr)
        return False


def run_assertions(eval_data: dict, config: dict) -> list[dict]:
    """모든 assertion을 실행하고 결과를 반환한다."""
    skill_md_path = resolve_path(eval_data["skill_md_path"])
    if not skill_md_path.exists():
        print(f"Error: SKILL.md not found at {skill_md_path}", file=sys.stderr)
        sys.exit(1)

    skill_content = load_skill_md(skill_md_path)
    llm_cmd = config.get("llm_command", "claude -p")
    results = []

    total = sum(len(t["assertions"]) for t in eval_data["tests"])
    passed = 0
    idx = 0

    for test in eval_data["tests"]:
        test_id = test["id"]
        description = test.get("description", "")
        print(f"\n[{test_id}] {description}")

        for assertion in test["assertions"]:
            idx += 1
            result = judge_assertion(skill_content, assertion, llm_cmd)
            status = "PASS" if result else "FAIL"
            if result:
                passed += 1

            print(f"  [{idx}/{total}] {status} — {assertion}")

            results.append({
                "test_id": test_id,
                "assertion": assertion,
                "result": "pass" if result else "fail",
                "score": 1 if result else 0,
            })

    print(f"\n{'=' * 50}")
    print(f"Score: {passed}/{total} ({passed / total * 100:.1f}%)" if total > 0 else "No assertions found")

    return results


def main():
    parser = argparse.ArgumentParser(description="Run eval assertions against a SKILL.md")
    parser.add_argument("skill_name", help="Name of the skill to evaluate")
    parser.add_argument("--eval-path", help="Custom path to eval.json")
    args = parser.parse_args()

    config = load_config()
    skills_base = resolve_path(config["skills_base_dir"])

    if args.eval_path:
        eval_path = resolve_path(args.eval_path)
    else:
        eval_subdir = config.get("eval_subdir", "eval")
        eval_filename = config.get("eval_filename", "eval.json")
        eval_path = skills_base / args.skill_name / eval_subdir / eval_filename

    if not eval_path.exists():
        print(f"Error: eval.json not found at {eval_path}", file=sys.stderr)
        print("Run gen-eval.py first to generate eval.json", file=sys.stderr)
        sys.exit(1)

    eval_data = load_eval(eval_path)
    results = run_assertions(eval_data, config)

    output = {
        "skill_name": args.skill_name,
        "total": len(results),
        "passed": sum(1 for r in results if r["result"] == "pass"),
        "score": sum(r["score"] for r in results) / len(results) if results else 0,
        "results": results,
    }

    output_path = eval_path.parent / "results.json"
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\nResults saved to {output_path}")
    return output


if __name__ == "__main__":
    main()
