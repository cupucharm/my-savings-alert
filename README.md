# 특판적금 알림 — GitHub Actions + Pages

서버 없이 무료로 특판적금 신규 출시·금리 상승을 크롬으로 알림받는 시스템입니다.

---

## 10분 셋업 가이드

### 1단계 — GitHub 레포 만들기

1. https://github.com → New repository
2. 이름: `my-savings-alert` (아무 이름이나 가능)
3. **Public** 으로 생성 (Pages 무료 사용 조건)
4. 이 폴더 전체를 레포에 올리기:
   ```bash
   git init
   git add .
   git commit -m "init"
   git remote add origin https://github.com/[USERNAME]/my-savings-alert.git
   git push -u origin main
   ```

### 2단계 — GitHub Pages 활성화

1. 레포 → Settings → Pages
2. Source: `Deploy from a branch`
3. Branch: `main` / Folder: `/docs`
4. Save
5. 잠시 후 `https://[USERNAME].github.io/my-savings-alert` 로 접속 가능

### 3단계 — 웹앱 URL 수정

`docs/index.html` 파일 열고 아래 줄 수정:

```js
const JSON_URL = "https://[YOUR-USERNAME].github.io/[YOUR-REPO]/savings.json";
//                         ↑ 본인 GitHub 유저명          ↑ 레포 이름
```

예시:
```js
const JSON_URL = "https://john.github.io/my-savings-alert/savings.json";
```

수정 후 `git push`.

### 4단계 — Actions 권한 설정

1. 레포 → Settings → Actions → General
2. `Workflow permissions` → **Read and write permissions** 체크
3. Save

(크롤러가 `savings.json`을 레포에 자동 커밋하기 위해 필요)

### 5단계 — 사용

1. `https://[USERNAME].github.io/my-savings-alert` 접속
2. "알림 허용" 클릭
3. "알림 시작" 클릭

끝! Actions가 평일 9–18시 매시간 자동 크롤링하고, 새 상품이 생기면 크롬 알림이 뜹니다.

> **처음 한 번은 수동 실행 필요**  
> push 직후엔 스케줄이 아직 안 돌았으므로 Actions 탭 → `특판적금 크롤러` → `Run workflow`로 한 번 실행해주세요.  
> 이후엔 자동으로 돌아갑니다.

---

## 크롬 알림 설정

알림이 안 보일 경우 아래 두 가지를 확인하세요.

### 1. 크롬 알림 허용 확인

크롬 주소창에 입력:
```
chrome://settings/content/notifications
```
`[USERNAME].github.io` 가 **허용** 목록에 있는지 확인.  
없으면 `추가` 버튼으로 직접 추가.

### 2. Mac 시스템 알림 허용 확인

시스템 설정 → 알림 → **Google Chrome** → 알림 허용 **켜기**

### 3. 테스트 알림으로 확인

웹앱에서 **"테스트 알림"** 버튼을 누르면 크롬 화면 오른쪽 아래에 팝업이 떠요.  
팝업이 보이면 실제 알림도 정상 작동합니다.

---

## 알림 로그

`savings.json` 안의 `alertLog` 배열에 알림 이력이 누적됩니다 (최대 100건).

```json
{
  "alertLog": [
    {
      "detectedAt": "2026-05-12T10:00:00+09:00",
      "type": "new",
      "bank": "하나은행",
      "name": "달려라 하나 적금",
      "maxRate": 6.0,
      "prevRate": null
    }
  ]
}
```

- `type`: `new` (신규 출시) / `rate_up` (금리 상승)
- `prevRate`: 금리 상승 시 이전 금리, 신규 출시면 `null`
- 로그는 GitHub 레포에서 직접 확인 가능: `savings.json` 파일 클릭

---

## 설정 변경

### 최소 금리 기준 변경
`.github/workflows/crawl.yml` 에서:
```yaml
- name: 크롤러 실행
  run: python crawler/crawl.py
  env:
    MIN_RATE: "5.0"   # 원하는 기준으로 수정
```

### 실행 시간 변경
`crawl.yml`의 cron 수정 (UTC 기준):
```yaml
# 평일 9–18시 KST = UTC 0–9시
- cron: '0 0-9 * * 1-5'
```

### 수동 실행
Actions 탭 → `특판적금 크롤러` → `Run workflow`

---

## 파일 구조

```
my-savings-alert/
├── .github/
│   └── workflows/
│       └── crawl.yml       # 스케줄러 (건드릴 필요 없음)
├── crawler/
│   └── crawl.py            # 크롤러 (건드릴 필요 없음)
├── docs/
│   └── index.html          # 웹앱 (JSON_URL만 수정)
├── savings.json            # 결과 (자동 생성)
└── README.md
```
