# skill-autoimprove

> **OpenClaw skill auto-improvement using Karpathy autoresearch loop**

Claude Code / OpenClaw 스킬(SKILL.md)을 밤새 자동으로 개선하는 시스템.  
binary assertion 기반으로 점수가 오르면 커밋, 내리면 롤백 — 사람이 멈출 때까지 반복합니다.

---

## How it works

```
eval.json (25 assertions) → score → LLM improve → re-score
    ↑ commit if better                   ↓ rollback if worse
    └──────────────────────────────────────┘ repeat
```

1. `eval.json`에 스킬에 대한 **참/거짓 테스트 25개** 작성
2. 루프 실행 → 점수 상승 시 git commit, 하락 시 git reset
3. "사람이 멈출 때까지 절대 멈추지 마라" 한 줄 프롬프트

실제로 마케팅 카피 스킬을 돌렸더니 **두 번 만에 만점** 달성.

---

## Quick start

```bash
# 1. eval.json 자동 생성
python scripts/gen-eval.py <skill-name>

# 2. 개선 루프 실행 (밤새 돌려도 OK)
python scripts/run-loop.py <skill-name> --max-iter 20 --timeout 3600
```

**OpenClaw slash command:**
```
/autoimprove <skill-name>
/autoimprove <skill-name> --gen-eval-only  # eval.json만 생성
```

---

## eval.json 예시

```json
[
  {"assertion": "SKILL.md has a clear trigger section", "expected": true},
  {"assertion": "SKILL.md specifies what it is NOT for", "expected": true},
  {"assertion": "SKILL.md has step-by-step workflow", "expected": true},
  {"assertion": "Each step has a concrete command or action", "expected": true},
  {"assertion": "SKILL.md is under 100 lines", "expected": true}
]
```

---

## What gets improved (auto)
- Trigger conditions
- Workflow steps & formatting
- Word count & structure rules
- Missing required sections

## What stays human
- Tone & creativity judgments
- Business logic decisions
- Subjective quality calls

---

## Setup

```bash
git clone https://github.com/VoidLight00/skill-autoimprove
cp -r skill-autoimprove ~/.openclaw/skills/skill-autoimprove
```

Requires: OpenClaw + Python 3.10+

---

## Inspired by
[Karpathy's autoresearch loop](https://x.com/karpathy) — the same idea that makes AI self-improve, applied to skill documentation.

---

*Built for [OpenClaw](https://openclaw.ai) — the personal AI assistant framework*
