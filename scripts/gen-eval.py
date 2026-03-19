#!/usr/bin/env python3
"""gen-eval.py — SKILL.md를 분석하여 binary assertions를 자동 생성한다.

Usage:
    python gen-eval.py <skill_name>
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

CONFIG_PATH = Path(__file__).parent.parent / "autoimprove.config.json"
TEMPLATE_PATH = Path(__file__).parent.parent / "templates" / "eval-template.json"


def load_config() -> dict:
    with open(CONFIG_PATH) as f:
        return json.load(f)


def resolve_path(p: str) -> Path:
    return Path(p).expanduser().resolve()


def generate_assertions(skill_content: str, skill_name: str, llm_cmd: str, config: dict) -> dict:
    """LLM을 사용하여 SKILL.md에 대한 assertions를 생성한다."""
    tests_target = config.get("total_tests_target", 5)
    assertions_per = config.get("assertions_per_test", 5)

    prompt = f"""You are an expert evaluator for OpenClaw skills (Claude Code skill system).
Analyze the following SKILL.md and generate binary assertions (TRUE/FALSE) to evaluate its quality.

<SKILL_MD>
{skill_content}
</SKILL_MD>

Generate exactly {tests_target} test groups with up to {assertions_per} assertions each.

Test categories to cover:
1. Trigger & activation — does SKILL.md clearly define when it should be used?
2. Workflow & steps — is there a clear workflow or step-by-step process?
3. Scope definition — are "When to Use" and "NOT for" sections present?
4. Content quality — are instructions specific, actionable, and complete?
5. Format & structure — is the document well-structured with proper headings?

Output ONLY valid JSON in this exact format (no markdown fences, no extra text):
{{
  "skill_name": "{skill_name}",
  "skill_md_path": "~/.openclaw/skills/{skill_name}/SKILL.md",
  "tests": [
    {{
      "id": "test-001",
      "description": "Test group description",
      "assertions": [
        "Assertion text 1",
        "Assertion text 2"
      ]
    }}
  ]
}}"""

    try:
        result = subprocess.run(
            [*llm_cmd.split(), prompt],
            capture_output=True,
            text=True,
            timeout=120,
        )
        output = result.stdout.strip()

        # JSON 파싱 시도 — 코드 블록 제거
        if output.startswith("```"):
            lines = output.split("\n")
            output = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])

        return json.loads(output)
    except json.JSONDecodeError as e:
        print(f"Error: LLM output is not valid JSON: {e}", file=sys.stderr)
        print(f"Raw output:\n{result.stdout[:500]}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Generate eval.json from SKILL.md")
    parser.add_argument("skill_name", help="Name of the skill")
    args = parser.parse_args()

    config = load_config()
    skills_base = resolve_path(config["skills_base_dir"])
    skill_dir = skills_base / args.skill_name
    skill_md_path = skill_dir / "SKILL.md"

    if not skill_md_path.exists():
        print(f"Error: {skill_md_path} not found", file=sys.stderr)
        sys.exit(1)

    skill_content = skill_md_path.read_text()
    llm_cmd = config.get("llm_command", "claude -p")

    print(f"Generating eval.json for: {args.skill_name}")
    print(f"SKILL.md path: {skill_md_path}")
    print(f"Reading SKILL.md ({len(skill_content)} chars)...")

    eval_data = generate_assertions(skill_content, args.skill_name, llm_cmd, config)

    # 출력 디렉토리 생성
    eval_subdir = config.get("eval_subdir", "eval")
    eval_dir = skill_dir / eval_subdir
    eval_dir.mkdir(parents=True, exist_ok=True)

    eval_filename = config.get("eval_filename", "eval.json")
    eval_path = eval_dir / eval_filename

    with open(eval_path, "w") as f:
        json.dump(eval_data, f, indent=2, ensure_ascii=False)

    total_assertions = sum(len(t["assertions"]) for t in eval_data["tests"])
    print(f"\nGenerated: {eval_path}")
    print(f"Tests: {len(eval_data['tests'])}")
    print(f"Total assertions: {total_assertions}")
    print("\nReview the eval.json before running the improvement loop.")


if __name__ == "__main__":
    main()
