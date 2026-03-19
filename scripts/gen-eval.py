#!/usr/bin/env python3
"""gen-eval.py — SKILL.md를 분석하여 binary assertions를 자동 생성한다.

5개 테스트 그룹을 생성한다:
  1. 구조 (트리거, 섹션 존재 여부)
  2. 포맷 (단어 수, 패턴 포함/미포함)
  3. 필수 요소 (When to Use, NOT for, 예시)
  4. 명확성 (첫 줄 독립 문장, 모호한 표현 없음)
  5. 완성도 (설정 참조, 링크, 코드 블록)

Usage:
    python gen-eval.py <skill_name>
"""

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

CONFIG_PATH = Path(__file__).parent.parent / "autoimprove.config.json"

# ANSI 컬러 코드
GREEN = "\033[92m"
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


def backup_existing_eval(eval_path: Path) -> Path | None:
    """기존 eval.json이 있으면 .bak으로 백업한다."""
    if not eval_path.exists():
        return None
    bak_path = eval_path.with_suffix(".json.bak")
    shutil.copy2(eval_path, bak_path)
    print(f"  {YELLOW}기존 eval.json 백업 → {bak_path.name}{RESET}")
    return bak_path


def generate_assertions(
    skill_content: str,
    skill_name: str,
    llm_cmd: str,
    config: dict,
) -> dict:
    """LLM을 사용하여 SKILL.md에 대한 assertions를 생성한다."""
    tests_target: int = config.get("total_tests_target", 5)
    assertions_per: int = config.get("assertions_per_test", 5)

    prompt = f"""You are an expert evaluator for OpenClaw skills (Claude Code skill system).
Analyze the following SKILL.md and generate binary assertions (TRUE/FALSE) to evaluate its quality.

<SKILL_MD>
{skill_content}
</SKILL_MD>

Generate exactly {tests_target} test groups with exactly {assertions_per} assertions each.

The 5 test groups MUST be these categories in this order:
1. "구조" (Structure) — trigger definition, section existence, heading hierarchy
2. "포맷" (Format) — word count, specific patterns present/absent, markdown formatting
3. "필수 요소" (Required Elements) — "When to Use" section, "NOT for" section, examples
4. "명확성" (Clarity) — first line is standalone sentence, no vague phrases like "등", specific actionable instructions
5. "완성도" (Completeness) — config references, links, code blocks, edge cases covered

Each assertion must be a clear TRUE/FALSE statement that can be verified by reading SKILL.md.

Output ONLY valid JSON in this exact format (no markdown fences, no extra text):
{{
  "skill_name": "{skill_name}",
  "skill_md_path": "~/.openclaw/skills/{skill_name}/SKILL.md",
  "generated_at": "{datetime.now(timezone.utc).isoformat()}",
  "tests": [
    {{
      "id": "test-001",
      "description": "구조 — 트리거 및 섹션 존재 여부",
      "assertions": [
        "Assertion text 1",
        "Assertion text 2",
        "Assertion text 3",
        "Assertion text 4",
        "Assertion text 5"
      ]
    }},
    {{
      "id": "test-002",
      "description": "포맷 — 단어 수, 패턴 포함/미포함",
      "assertions": ["..."]
    }},
    {{
      "id": "test-003",
      "description": "필수 요소 — When to Use, NOT for, 예시",
      "assertions": ["..."]
    }},
    {{
      "id": "test-004",
      "description": "명확성 — 첫 줄 독립 문장, 모호한 표현 없음",
      "assertions": ["..."]
    }},
    {{
      "id": "test-005",
      "description": "완성도 — 설정 참조, 링크, 코드 블록",
      "assertions": ["..."]
    }}
  ]
}}"""

    max_attempts = 2
    for attempt in range(max_attempts):
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
                end_idx = len(lines)
                for i in range(len(lines) - 1, 0, -1):
                    if lines[i].startswith("```"):
                        end_idx = i
                        break
                output = "\n".join(lines[1:end_idx])

            data = json.loads(output)

            # 기본 검증
            if "tests" not in data or not isinstance(data["tests"], list):
                raise ValueError("tests 필드가 없거나 올바르지 않습니다")
            if len(data["tests"]) == 0:
                raise ValueError("테스트 그룹이 비어 있습니다")

            # skill_name, skill_md_path 보정
            data["skill_name"] = skill_name
            data["skill_md_path"] = f"~/.openclaw/skills/{skill_name}/SKILL.md"
            data["generated_at"] = datetime.now(timezone.utc).isoformat()

            return data

        except json.JSONDecodeError as e:
            if attempt < max_attempts - 1:
                print(
                    f"  {YELLOW}JSON 파싱 실패, 재시도 중... ({attempt + 1}/{max_attempts}){RESET}"
                )
                continue
            print(
                f"오류: LLM 출력이 유효한 JSON이 아닙니다: {e}",
                file=sys.stderr,
            )
            print(f"원본 출력 (첫 500자):\n{result.stdout[:500]}", file=sys.stderr)
            sys.exit(1)
        except subprocess.TimeoutExpired:
            if attempt < max_attempts - 1:
                print(f"  {YELLOW}타임아웃, 재시도 중...{RESET}")
                continue
            print("오류: LLM 호출 타임아웃 (120초 초과)", file=sys.stderr)
            sys.exit(1)
        except FileNotFoundError:
            print(
                f"오류: LLM 명령어를 찾을 수 없습니다: {llm_cmd}",
                file=sys.stderr,
            )
            sys.exit(1)
        except ValueError as e:
            if attempt < max_attempts - 1:
                print(f"  {YELLOW}검증 실패 ({e}), 재시도 중...{RESET}")
                continue
            print(f"오류: {e}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"오류: {e}", file=sys.stderr)
            sys.exit(1)

    # 도달 불가이지만 타입 안전을 위해
    sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="SKILL.md를 분석하여 eval.json을 자동 생성합니다.",
        epilog="예시: python gen-eval.py comet-agent",
    )
    parser.add_argument("skill_name", help="대상 스킬 이름")
    args = parser.parse_args()

    config = load_config()
    skills_base = resolve_path(config["skills_base_dir"])
    skill_dir = skills_base / args.skill_name
    skill_md_path = skill_dir / "SKILL.md"

    if not skill_md_path.exists():
        print(
            f"오류: SKILL.md를 찾을 수 없습니다: {skill_md_path}",
            file=sys.stderr,
        )
        sys.exit(1)

    skill_content = skill_md_path.read_text(encoding="utf-8")
    llm_cmd: str = config.get("llm_command", "claude -p")

    print(f"{BOLD}eval.json 생성: {args.skill_name}{RESET}")
    print(f"  SKILL.md: {skill_md_path}")
    print(f"  크기: {len(skill_content):,}자")

    # 출력 경로 결정
    eval_subdir: str = config.get("eval_subdir", "eval")
    eval_dir = skill_dir / eval_subdir
    eval_dir.mkdir(parents=True, exist_ok=True)

    eval_filename: str = config.get("eval_filename", "eval.json")
    eval_path = eval_dir / eval_filename

    # 기존 eval.json 백업
    backup_existing_eval(eval_path)

    print(f"\n  {CYAN}LLM으로 assertions 생성 중...{RESET}")
    eval_data = generate_assertions(skill_content, args.skill_name, llm_cmd, config)

    with open(eval_path, "w", encoding="utf-8") as f:
        json.dump(eval_data, f, indent=2, ensure_ascii=False)

    total_assertions = sum(len(t["assertions"]) for t in eval_data["tests"])
    test_count = len(eval_data["tests"])

    print(f"\n{GREEN}{BOLD}생성 완료!{RESET}")
    print(f"  파일: {eval_path}")
    print(f"  테스트 그룹: {test_count}개")
    print(f"  전체 assertions: {total_assertions}개")

    # 생성된 테스트 그룹 요약
    print(f"\n{BOLD}테스트 그룹:{RESET}")
    for test in eval_data["tests"]:
        count = len(test["assertions"])
        print(f"  [{test['id']}] {test.get('description', '')} ({count}개)")

    print(f"\n{DIM}개선 루프 실행 전에 eval.json을 검토하세요.{RESET}")


if __name__ == "__main__":
    main()
