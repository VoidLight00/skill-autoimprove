# skill-autoimprove

OpenClaw 스킬(SKILL.md)을 Karpathy autoresearch 루프 방식으로 자동 개선하는 시스템.
`/autoimprove <skill-name>` 명령으로 실행하면 binary assertions 기반으로 스킬을 반복 개선한다.

## Trigger

`/autoimprove <skill-name>` — 특정 스킬의 SKILL.md를 자동 개선
`/autoimprove <skill-name> --gen-eval-only` — eval.json만 생성 (루프 미실행)

## When to Use

- 스킬의 SKILL.md 품질을 체계적으로 개선하고 싶을 때
- 스킬에 트리거, 워크플로우, 사용 범위 등 필수 요소가 빠져있을 때
- 밤새 자동으로 스킬을 개선하고 아침에 결과를 확인하고 싶을 때
- eval.json이 없는 스킬에 대해 평가 기준을 자동 생성하고 싶을 때

## NOT for

- SKILL.md가 아닌 일반 코드 파일의 품질 개선
- 스킬의 비즈니스 로직이나 실행 코드 수정
- 톤, 창의성, 주관적 품질 평가 (binary assertion으로 판단 불가)
- git 관리되지 않는 디렉토리의 파일

## Workflow

### 1. eval.json 확인/생성
```bash
# eval.json이 없으면 자동 생성
python ~/.openclaw/skills/skill-autoimprove/scripts/gen-eval.py <skill-name>
```
- `~/.openclaw/skills/<skill-name>/eval/eval.json` 에 저장
- 생성 후 사용자에게 assertions 검토 요청

### 2. 개선 루프 실행
```bash
python ~/.openclaw/skills/skill-autoimprove/scripts/run-loop.py <skill-name> --max-iter 20 --timeout 3600
```
- 현재 SKILL.md 채점 → LLM으로 개선 → 재채점
- 점수 상승 시 git commit, 하락/동일 시 git reset
- 만점(100%) 달성 또는 max-iter/timeout 도달 시 종료

### 3. 리포트 생성
```bash
python ~/.openclaw/skills/skill-autoimprove/scripts/report.py <skill-name>
```
- 점수 변화 텍스트 그래프
- 커밋 이력 요약
- 최종 점수 표시

## Configuration

`~/.openclaw/skills/skill-autoimprove/autoimprove.config.json`:

| 키 | 기본값 | 설명 |
|---|---|---|
| `skills_base_dir` | `~/.openclaw/skills` | 스킬 루트 디렉토리 |
| `max_iterations` | `20` | 최대 반복 횟수 |
| `timeout_seconds` | `3600` | 타임아웃 (초) |
| `llm_command` | `claude -p` | LLM 호출 명령어 |
| `total_tests_target` | `5` | 생성할 테스트 그룹 수 |
| `assertions_per_test` | `5` | 그룹당 assertion 수 |

## eval.json Format

```json
{
  "skill_name": "comet-agent",
  "skill_md_path": "~/.openclaw/skills/comet-agent/SKILL.md",
  "tests": [
    {
      "id": "test-001",
      "description": "트리거 명시 여부",
      "assertions": [
        "SKILL.md에 trigger 또는 Use when 섹션이 존재한다",
        "스킬 이름이 SKILL.md 첫 줄에 명시되어 있다"
      ]
    }
  ]
}
```

## Scripts

| 스크립트 | 용도 | CLI |
|---|---|---|
| `run-assertions.py` | assertion 실행 + 채점 | `python run-assertions.py <skill> [--eval-path <path>]` |
| `run-loop.py` | 자율 개선 루프 | `python run-loop.py <skill> [--max-iter N] [--timeout S]` |
| `gen-eval.py` | eval.json 자동 생성 | `python gen-eval.py <skill>` |
| `report.py` | 개선 리포트 생성 | `python report.py <skill>` |

## Requirements

- Python 3.10+
- `claude` CLI (LLM 호출용)
- git (커밋/롤백용)
- 대상 스킬 디렉토리가 git 저장소 내에 있어야 함
