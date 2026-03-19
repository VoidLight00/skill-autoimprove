# CLAUDE.md — skill-autoimprove

> Claude Code용 프로젝트 컨텍스트 파일.
> 작업 전 반드시 읽을 것.

---

## 프로젝트 개요

**skill-autoimprove**는 OpenClaw 스킬(SKILL.md)을 Karpathy autoresearch 루프 방식으로 자동 개선하는 시스템.

- `SKILL.md` → binary assertions(eval.json)로 품질 측정
- 점수 오르면 git commit 유지, 내리면 git reset 롤백
- `/autoimprove <skill-name>` 한 줄로 밤새 실행

**GitHub:** https://github.com/VoidLight00/skill-autoimprove (Public)  
**Install path:** `~/.openclaw/skills/skill-autoimprove/`  
**Python:** 3.10+

---

## 파일 구조

```
skill-autoimprove/
├── SKILL.md                   OpenClaw 트리거 정의 (/autoimprove)
├── CLAUDE.md                  이 파일
├── autoimprove.config.json    전역 설정
├── scripts/
│   ├── run-assertions.py      eval.json → LLM 채점 → results.json
│   ├── run-loop.py            Karpathy 루프 (commit/reset 포함)
│   ├── gen-eval.py            SKILL.md 분석 → eval.json 자동 생성
│   └── report.py              개선 이력 리포트 (텍스트 그래프)
└── templates/
    └── eval-template.json     eval.json 기본 구조
```

---

## 핵심 개념

### Karpathy 루프 (`run-loop.py`)

```
현재 점수 측정
    → SKILL.md 개선 (LLM)
        → 점수 재측정
            → 오르면: git commit
            → 같거나 내리면: git reset --hard HEAD
                → 반복 (max_iter 또는 100% 달성까지)
```

### eval.json 구조

```json
{
  "skill_name": "comet-agent",
  "skill_md_path": "~/.openclaw/skills/comet-agent/SKILL.md",
  "tests": [
    {
      "id": "test-001",
      "description": "트리거 명시 여부",
      "assertions": [
        "SKILL.md에 Use when 또는 Trigger 섹션이 존재한다",
        "스킬 이름이 SKILL.md에 명시되어 있다"
      ]
    }
  ]
}
```

### Assertion 판단 방식 (`run-assertions.py`)

```python
# LLM(claude -p)에게 SKILL.md + assertion을 주고 PASS/FAIL 판단
prompt = """
<SKILL_MD>{content}</SKILL_MD>
<ASSERTION>{assertion}</ASSERTION>
Respond with exactly one word: PASS or FAIL.
"""
result = subprocess.run(["claude", "-p", prompt], capture_output=True)
passed = "PASS" in result.stdout.upper()
```

---

## 설정 (`autoimprove.config.json`)

| 키 | 기본값 | 설명 |
|---|---|---|
| `skills_base_dir` | `~/.openclaw/skills` | 스킬 루트 디렉토리 |
| `max_iterations` | `20` | 루프 최대 반복 |
| `timeout_seconds` | `3600` | 전체 타임아웃 (1시간) |
| `llm_command` | `claude -p` | LLM 호출 명령어 |
| `git_auto_commit` | `true` | 점수 개선 시 자동 커밋 |
| `eval_subdir` | `eval` | eval.json 저장 서브디렉토리 |
| `assertions_per_test` | `5` | 테스트 그룹당 assertion 수 |
| `total_tests_target` | `5` | 생성할 테스트 그룹 수 |

---

## CLI 사용법

```bash
cd ~/.openclaw/skills/skill-autoimprove

# 1. eval.json 생성
python scripts/gen-eval.py comet-agent
# → ~/.openclaw/skills/comet-agent/eval/eval.json

# 2. 현재 점수 확인
python scripts/run-assertions.py comet-agent
# → ~/.openclaw/skills/comet-agent/eval/results.json

# 3. 자율 개선 루프 실행
python scripts/run-loop.py comet-agent --max-iter 20 --timeout 3600

# 4. 리포트 확인
python scripts/report.py comet-agent
```

---

## 데이터 흐름

```
gen-eval.py
  reads:   ~/.openclaw/skills/<name>/SKILL.md
  writes:  ~/.openclaw/skills/<name>/eval/eval.json

run-assertions.py
  reads:   eval.json + SKILL.md
  calls:   claude -p "<assertion prompt>"
  writes:  ~/.openclaw/skills/<name>/eval/results.json

run-loop.py
  calls:   run-assertions.py (점수 측정)
  calls:   claude -p (SKILL.md 개선)
  runs:    git commit / git reset
  writes:  logs/<name>-history.json

report.py
  reads:   logs/<name>-history.json
  prints:  텍스트 점수 그래프 + 커밋 이력
```

---

## 코딩 규칙

### 1. LLM 호출은 항상 `subprocess` + `claude -p`

```python
# ✅ CORRECT
result = subprocess.run(
    ["claude", "-p", prompt],
    capture_output=True, text=True, timeout=60
)
output = result.stdout.strip()

# ❌ WRONG — anthropic SDK 직접 사용 금지 (환경 의존성 증가)
import anthropic
client = anthropic.Anthropic()
```

### 2. git 조작은 subprocess + 반드시 디렉토리 확인

```python
# ✅ CORRECT — 스킬 디렉토리에서 실행
subprocess.run(
    ["git", "add", "SKILL.md"],
    cwd=str(skill_dir),     # ← 반드시 cwd 명시
    check=True
)

# ❌ WRONG — cwd 없으면 현재 프로세스 위치에서 실행됨
subprocess.run(["git", "add", "SKILL.md"])
```

### 3. 점수 동일할 때는 롤백 (개선 없으면 커밋 X)

```python
# ✅ CORRECT
if new_score > current_score:
    git_commit(f"iter {n}: {current_score:.0%} → {new_score:.0%}")
else:
    git_reset()  # 동일 점수도 롤백

# ❌ WRONG — 점수 같을 때 커밋하면 불필요한 커밋 쌓임
if new_score >= current_score:
    git_commit(...)
```

### 4. 경로는 항상 `Path.expanduser().resolve()`

```python
# ✅ CORRECT — ~ 확장 + 절대경로 변환
skill_dir = Path("~/.openclaw/skills/comet-agent").expanduser().resolve()

# ❌ WRONG — ~ 미확장 시 파일 못 찾음
skill_dir = Path("~/.openclaw/skills/comet-agent")
```

---

## 테스트 실행

```bash
# 실제 스킬로 end-to-end 테스트
python scripts/gen-eval.py comet-agent
python scripts/run-assertions.py comet-agent
python scripts/report.py comet-agent

# 단위 테스트 (있는 경우)
pytest tests/ -v
```

---

## Git 워크플로

```bash
# 커밋 규칙
git commit -m "fix: <설명>"    # 버그 수정
git commit -m "feat: <설명>"   # 새 기능
git commit -m "docs: <설명>"   # 문서

# 버전 (pyproject.toml 없으면 SKILL.md 버전 코멘트로 관리)
# v0.1 - 초기 개발
# v0.2 - gen-eval + run-loop 완성
# v1.0 - 오픈소스 배포 (clawhub.com 등록 목표)
```

---

## 배포 계획 (Roadmap)

- [x] v0.1 — scripts 4종 + SKILL.md 완성
- [ ] v0.2 — comet-agent 스킬로 실제 테스트 + 검증
- [ ] v0.3 — 에러 핸들링 강화 + 로그 개선
- [ ] v1.0 — GitHub 오픈소스 + clawhub.com 등록

---

## Do NOT

- ❌ git reset 없이 점수 하락 커밋
- ❌ cwd 없이 git 명령 실행
- ❌ LLM 응답이 PASS/FAIL 이외일 때 PASS로 간주
- ❌ eval.json 없는 상태에서 run-loop 실행
- ❌ 대상 스킬 디렉토리가 git repo가 아닌 경우 실행

---

*Maintained by Hyeon · Powered by Kraken 🐙*
