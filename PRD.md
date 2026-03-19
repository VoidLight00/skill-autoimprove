# PRD: skill-autoimprove — OpenClaw 스킬 자동개선 시스템

## 프로젝트 개요

OpenClaw 스킬(SKILL.md)을 Karpathy autoresearch 루프 방식으로 밤새 자동 개선하는 시스템.
`/autoimprove <skill-name>` 명령 한 줄로 실행 → 아침에 더 나은 스킬로 깨어나기.
완성 후 GitHub 오픈소스 + clawhub.com 배포 목표.

---

## 핵심 개념

### Karpathy autoresearch 루프 (원본)
```
1. 학습 대상(train.py) 읽기
2. 값 하나 변경
3. 테스트 실행
4. 점수 확인 → 개선됐으면 커밋 유지, 나빠졌으면 롤백
5. 절대 멈추지 말고 반복
```

### 우리 적용 방식
- `train.py` → `SKILL.md` (스킬 지시문)
- 수치 메트릭 → **Binary assertions** 패스율 (25개 참/거짓 테스트)
- git commit/reset 동일하게 유지

---

## 기능 요구사항

### 1. eval.json 자동 생성 (`gen-eval`)
- 기존 `SKILL.md` 파일을 읽어서 binary assertions 자동 제안
- assertions 유형:
  - 포맷 규칙 (글자 수, 특정 패턴 포함/미포함)
  - 구조 규칙 (첫 줄 독립 문장, 마지막 줄 형태 등)
  - 필수 포함 요소 (링크, 해시태그, 숫자/통계 등)
- 출력: `skills/<skill-name>/eval/eval.json`
- 사용자가 assertions 검토 후 확정

### 2. 자율 개선 루프 (`run-loop`)
```
WHILE 완벽하지 않거나 중단 신호 없을 때:
  1. 현재 SKILL.md 읽기
  2. eval.json의 테스트 케이스 실행
  3. 각 assertion 패스/실패 확인
  4. 점수 계산 (패스 수 / 전체 수)
  5. 점수 개선됐으면 → git commit
     점수 동일하거나 하락했으면 → git reset + 다른 변경 시도
  6. 변경 이력 + 점수 로그 기록
  7. 반복
```

### 3. 개선 리포트 (`report`)
- 루프 종료 후 개선 이력 요약
- 변경된 항목, 점수 변화 그래프(텍스트), 최종 점수
- 텔레그램으로 리포트 전송

### 4. 패시브 모드 (크론 연동)
- 주기적 자동 실행 (예: 매주 일요일 새벽 3시)
- 등록된 모든 스킬 순차 실행
- 완료 후 텔레그램 요약 리포트

---

## 기술 스택

- **언어**: Python 3.10+
- **Git 조작**: `subprocess` + git CLI (commit/reset/log)
- **스킬 실행**: OpenClaw MCP 또는 Claude Code CLI (`claude -p`)
- **설정**: `autoimprove.config.json` (스킬 경로, 크론 주기, 텔레그램 토큰 등)
- **패키징**: OpenClaw SKILL.md 형식

---

## 파일 구조

```
~/.openclaw/skills/skill-autoimprove/
├── SKILL.md                    ← 트리거: /autoimprove <skill-name>
├── README.md
├── scripts/
│   ├── gen-eval.py             ← eval.json 자동 생성
│   ├── run-loop.py             ← 자율 개선 루프
│   ├── run-assertions.py       ← 개별 assertion 실행 + 채점
│   └── report.py               ← 개선 이력 리포트 생성
├── templates/
│   └── eval-template.json      ← eval.json 기본 템플릿
└── autoimprove.config.json     ← 설정 파일
```

### eval.json 구조
```json
{
  "skill_name": "comet-agent",
  "skill_md_path": "~/.openclaw/skills/comet-agent/SKILL.md",
  "tests": [
    {
      "id": "test-001",
      "prompt": "사용자가 /comet 이라고 입력했을 때 스킬이 활성화되는가",
      "assertions": [
        "SKILL.md에 trigger: /comet 명시되어 있음",
        "workflow 섹션에 최소 5단계가 존재함",
        "CDP profile 설정이 명시되어 있음",
        "한국어 입력 방식이 기술되어 있음"
      ]
    }
  ]
}
```

---

## 사용 시나리오

### 시나리오 1: 단일 스킬 개선
```
# 사용자 → OpenClaw
/autoimprove comet-agent

# OpenClaw 동작:
1. ~/.openclaw/skills/comet-agent/SKILL.md 읽기
2. eval.json 없으면 자동 생성 + 사용자 확인
3. 루프 시작
4. (밤새 자동 실행)
5. 아침: 텔레그램 "comet-agent 개선 완료: 18/25 → 25/25"
```

### 시나리오 2: 전체 스킬 일괄 개선 (패시브)
```
# 크론: 매주 일요일 새벽 3시
/autoimprove --all

# 순차 실행: comet-agent → youtube-summary → ...
# 완료: 텔레그램 주간 스킬 개선 리포트
```

### 시나리오 3: eval.json만 생성
```
/autoimprove comet-agent --gen-eval-only

# SKILL.md 분석 → assertions 제안 → eval.json 저장
# 루프는 실행하지 않음 (사용자가 검토 후 수동 실행)
```

---

## 제약 및 한계

- **Binary assertions만 자동화 가능**: 구조, 포맷, 단어 수, 금지 패턴
- **자동화 불가 항목**: 톤, 창의성, 참조 파일 활용도 → 별도 수동 검토
- **스킬 실행 환경**: Claude Code CLI 또는 OpenClaw 에이전트 실행 필요
- **git 필수**: 롤백을 위해 스킬 디렉터리가 git 관리 하에 있어야 함

---

## 배포 계획

1. **v0.1**: comet-agent에 수동 적용 + 검증
2. **v0.2**: gen-eval + run-loop 스크립트 완성
3. **v0.3**: SKILL.md 패키징 + /autoimprove 명령 연동
4. **v1.0**: GitHub 오픈소스 배포 (`VoidLight00/skill-autoimprove`)
5. **v1.1**: clawhub.com 등록 + 문서화
6. **v2.0**: 패시브 크론 모드 + 멀티 스킬 배치 지원

---

## 성공 지표

- [ ] comet-agent assertions 25/25 달성
- [ ] 루프 1회 실행에 평균 소요 시간 < 5분
- [ ] GitHub 스타 50+ (배포 후 1개월)
- [ ] clawhub.com 등록 완료

---

## 개발 우선순위

1. `run-assertions.py` — 가장 핵심, 먼저 완성
2. `run-loop.py` — assertions 위에서 작동
3. `gen-eval.py` — LLM으로 assertions 자동 생성
4. `SKILL.md` — 트리거 + 워크플로우 정의
5. `report.py` + 크론 연동 — 마지막

---

*작성: 2026-03-19 | 담당: 현님 + 크라켄*
