# Threads 브라우저 자동화 학습 노트
> 작성: 2026-03-19 | 실검증 완료 기록

---

## 환경 설정

| 항목 | 값 |
|------|-----|
| 브라우저 프로필 | `openclaw` (Threads 로그인됨, comet 프로필은 로그인 안 됨) |
| 한국어 입력 | `printf '텍스트' | pbcopy` → `browser(act, press="Meta+v")` |
| 타임아웃 | 모든 browser 호출에 `timeoutMs=1000000` 필수 |
| 프로필 페이지 | `https://www.threads.com/@voidlight00` |

---

## 1. 답글 달기 플로우 (실검증 완료 ✅)

### 기본 플로우
```
STEP 1: 프로필 페이지 열기
  browser(action="open", profile="openclaw",
    url="https://www.threads.com/@voidlight00", timeoutMs=1000000)
  → 2~3초 대기

STEP 2: snapshot으로 답글 버튼 ref 확인
  snapshot → button "답글 N" 또는 button "답글" ref 찾기

STEP 3: 답글 버튼 클릭 → dialog 열림
  browser(act, click, ref=<답글 버튼 ref>)
  → dialog[heading "답글"] 열림 확인

STEP 4: 텍스트 클립보드 준비
  exec: printf '<답글 텍스트>' | pbcopy

STEP 5: textbox 클릭 후 붙여넣기
  browser(act, click, ref=<textbox ref>)
  browser(act, press="Meta+v", ref=<textbox ref>)

STEP 6: 게시
  browser(act, click, ref=<"게시" button ref>)
```

### 특정 게시글 URL로 직접 이동
```
https://www.threads.com/@voidlight00/post/<POST_ID>
예시: DWD9ylUj3m0, DWDwFi2jyI_
```

---

## 2. Dialog 전체 구조 (실검증 완료 ✅)

```
dialog:
  button "취소"           ← 좌측 상단 (즉시 닫힘, 확인 없음)
  heading "답글"          ← 중앙 타이틀
  button "더 보기 (···)"  ← 우측 상단 → "AI 레이블 추가" 드롭다운
  
  [원본 게시글 표시]
  
  textbox [active]        ← 답글 입력 (pbcopy + Meta+v)
  
  button "미디어 첨부"    ← 클릭하면 Finder 열리며 dialog 닫힘! 사용 금지
  button "GIF 추가"       ← GIPHY 화면 (돌아가기로 복귀 가능)
  button "이모티콘 추가"  ← ⚠️ 시스템 피커 → dialog 닫힘 절대 금지
  button "설문 추가"
  button "텍스트 첨부"
  button "위치 추가"
  
  button "스레드에 추가"  ← 텍스트/이미지 있을 때 활성화 → 체인 스레드 추가
  button "게시"           ← 텍스트/이미지 있을 때 활성화
  button "답글 옵션"      ← 답글 권한 설정 (모든사람/팔로워/팔로우/언급한)
```

### ⚠️ 절대 금지
- `button "미디어 첨부"` 클릭 → Finder 열리며 dialog 닫힘
- `button "이모티콘 추가"` 클릭 → 시스템 피커 → dialog 닫힘
- Escape 키 → dialog 닫힘

---

## 3. 이미지 첨부 방법 (실검증 완료 ✅)

**확정 방법: osascript 클립보드 주입 + Cmd+V**

```bash
# STEP 1: 이미지를 클립보드에 올리기 (권한 불필요!)
osascript -e 'set the clipboard to (read (POSIX file "/절대/경로/이미지.png") as «class PNGf»)'

# PNG: «class PNGf»
# JPEG: «class JPEG»
```

```
STEP 2: dialog 열고 textbox 클릭 후 Cmd+V
  browser(act, click, ref=<textbox ref>)
  browser(act, press="Meta+v", ref=<textbox ref>)
  → 이미지 즉시 첨부됨 ✅

STEP 3: 이미지 첨부 후 dialog 버튼 변화
  before: button "미디어 첨부" (클릭 금지!)
  after:  button "삭제"           ← 이미지 삭제
          button "첨부 파일 조치" ← 이미지 편집
          button "미디어 첨부 추가" ← 추가 이미지
          button "스레드에 추가"  ← 활성화됨
```

**지원 포맷:** PNG, JPEG, WEBP, AVIF, MP4, MOV, WEBM

**주의:**
- 이미지 첨부 상태에서 취소하면 "스레드를 삭제하시겠어요?" 팝업 → "취소" 눌러야 dialog 유지
- 이미지+텍스트 순서: 이미지 먼저 Cmd+V → 텍스트 pbcopy+Meta+v

---

## 4. 취소 플로우 (실검증 완료 ✅)

```
browser(act, click, ref=<"취소" button ref>)
→ dialog 즉시 닫힘
→ 확인 팝업 없음 (이미지 없을 때)
→ 이미지 있을 때: "스레드를 삭제하시겠어요?" 팝업
  - button "삭제" → 완전 종료
  - button "취소" → dialog 유지
```

---

## 5. GIF 선택 화면

```
dialog:
  button "돌아가기"       ← 답글 dialog로 복귀
  heading "GIF 선택"
  textbox "GIPHY 검색"
  button [썸네일 목록]   ← 클릭 시 삽입 후 답글 화면 복귀
```

---

## 6. 스레드에 추가 (체인 기능)

```
텍스트/이미지 있을 때 활성화됨
클릭 → 새 입력창 추가 (3번째 스레드)

추가된 스레드 구조:
  textbox [ref=e17]       ← 1번 답글
  textbox [ref=e25]       ← 2번 추가 스레드
  button "닫기" [ref=e24] ← 각 스레드 개별 삭제
  button "게시"           ← 전체 게시 (스레드 체인으로 올라감)
```

---

## 7. 시도했지만 실패한 방법들

| 방법 | 결과 | 이유 |
|------|------|------|
| `browser.upload` action | ❌ React 미반응 | React SPA가 native change 이벤트 무시 |
| JS DataTransfer 주입 | ❌ 파일 주입 안 됨 | Object.defineProperty로 files 변경 불가 |
| `osascript keystroke` | ❌ 권한 오류 | 손쉬운 사용(Accessibility) 권한 필요 |
| `osascript window 제어` | ❌ 권한 오류 | 손쉬운 사용(Accessibility) 권한 필요 |
| `미디어 첨부 버튼 클릭` | ❌ dialog 닫힘 | Finder 피커가 dialog 외부로 처리됨 |
| Playwright waitForEvent | ❌ OpenClaw 미지원 | OpenClaw browser 툴이 해당 이벤트 미지원 |

---

## 8. 최신 게시글 감지 (JavaScript)

```javascript
// dialog 없는 상태에서 evaluate로 실행
function getLatestPosts() {
  var links = Array.from(document.querySelectorAll('a[href*="/post/"]'));
  var urls = [...new Set(links.map(a => a.pathname).filter(p => p.includes('/post/')))];
  return urls.slice(0, 5); // 최근 5개 POST_ID 포함 경로
}
```

---

## 9. 전체 이미지+텍스트 답글 자동화 예시

```python
# 1. 이미지 클립보드에 올리기
exec('osascript -e \'set the clipboard to (read (POSIX file "/path/to/image.png") as «class PNGf»)\'')

# 2. 프로필 열기
browser(action="open", profile="openclaw",
  url="https://www.threads.com/@voidlight00/post/<POST_ID>",
  timeoutMs=1000000)

# 3. 2초 대기
sleep(2)

# 4. snapshot → 답글 버튼 ref 확인
snapshot → 답글_ref

# 5. 답글 클릭 → dialog
browser(act, click, ref=답글_ref)

# 6. textbox에 이미지 붙여넣기
browser(act, click, ref=textbox_ref)
browser(act, press="Meta+v", ref=textbox_ref)

# 7. 텍스트 준비 후 붙여넣기
exec('printf "답글 텍스트 🙌" | pbcopy')
browser(act, press="Meta+v", ref=textbox_ref)

# 8. 게시
browser(act, click, ref=게시_ref)
```
