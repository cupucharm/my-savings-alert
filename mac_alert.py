#!/usr/bin/env python3
"""
특판적금 Mac 알림 스크립트
- savings.json을 읽어서 신규/금리변동 감지
- osascript로 Mac 네이티브 알림 전송
- cron으로 매시간 자동 실행
"""

import json
import os
import subprocess
import urllib.request
from datetime import datetime, timezone, timedelta

# ── 설정 ──────────────────────────────────────
SAVINGS_URL  = "https://cupucharm.github.io/my-savings-alert/savings.json"
SETTINGS_URL = "https://cupucharm.github.io/my-savings-alert/settings.json"
STATE_FILE   = os.path.expanduser("~/.savings_alert_state.json")
KST          = timezone(timedelta(hours=9))

# 웹앱에서 settings.json으로 설정을 받아옴
# 없으면 아래 기본값 사용
DEFAULT_SETTINGS = {
    "notiMode": "mac",   # chrome / mac / both / none
    "eod": {
        "enabled": True,
        "mode":    "mac",   # chrome / mac / both
        "time":    "17:30",
        "days":    [1, 2, 3, 4, 5]  # 1=월 ~ 5=금 (JS 요일 기준)
    }
}

def load_settings():
    try:
        req = urllib.request.Request(
            SETTINGS_URL + "?t=" + str(int(datetime.now().timestamp())),
            headers={"User-Agent": "savings-alert-mac/1.0"}
        )
        with urllib.request.urlopen(req, timeout=10) as res:
            s = json.loads(res.read().decode())
            print(f"[설정] 웹앱 settings.json 로드 완료")
            return s
    except Exception:
        print(f"[설정] settings.json 없음 → 기본값 사용")
        return DEFAULT_SETTINGS

# ── Mac 알림 전송 ──────────────────────────────
def notify(title, message, subtitle=""):
    # subtitle이 있으면 포함
    if subtitle:
        script = f'display notification "{message}" with title "{title}" subtitle "{subtitle}"'
    else:
        script = f'display notification "{message}" with title "{title}"'
    subprocess.run(["osascript", "-e", script], capture_output=True)

# ── savings.json 가져오기 ──────────────────────
def fetch_savings():
    try:
        req = urllib.request.Request(
            SAVINGS_URL + "?t=" + str(int(datetime.now().timestamp())),
            headers={"User-Agent": "savings-alert-mac/1.0"}
        )
        with urllib.request.urlopen(req, timeout=15) as res:
            return json.loads(res.read().decode())
    except Exception as e:
        print(f"[오류] savings.json 로드 실패: {e}")
        return None

# ── 이전 상태 로드/저장 ────────────────────────
def load_state():
    if not os.path.exists(STATE_FILE):
        return {"seen": [], "eod_sent": ""}
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except Exception:
        return {"seen": [], "eod_sent": ""}

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

# ── 신규/금리변동 알림 ─────────────────────────
def check_alerts(data, state, mode="mac"):
    seen  = set(state.get("seen", []))
    fired = False

    for alert in data.get("alerts", []):
        p   = alert["product"]
        key = p["id"] + alert["type"]
        if key in seen:
            continue
        seen.add(key)
        fired = True

        if alert["type"] == "new":
            notify(
                "🆕 특판적금 신규 출시",
                f"최고 {p['maxRate']}% (세전)",
                f"{p['bank']} {p['name']}"
            )
            print(f"[신규] {p['bank']} {p['name']} {p['maxRate']}%")
        else:
            prev = alert.get("prevRate", "?")
            notify(
                "📈 특판적금 금리 상승",
                f"{prev}% → {p['maxRate']}% (세전)",
                f"{p['bank']} {p['name']}"
            )
            print(f"[금리↑] {p['bank']} {p['name']} {prev}% → {p['maxRate']}%")

    if not fired:
        print("[확인] 변동 없음")

    state["seen"] = list(seen)

# ── 퇴근 요약 알림 ────────────────────────────
def check_eod(data, state, cfg=None):
    if cfg is None:
        cfg = DEFAULT_SETTINGS["eod"]
    if not cfg.get("enabled", True):
        print("[퇴근알림] 꺼짐")
        return

    now = datetime.now(KST)
    eod_time = cfg.get("time", "17:30")
    eod_h, eod_m = map(int, eod_time.split(":"))
    # JS 요일(1=월~5=금) → Python weekday(0=월~4=금) 변환
    js_days = cfg.get("days", [1,2,3,4,5])
    py_days = [(d - 1) % 7 for d in js_days]

    # 요일 체크
    if now.weekday() not in py_days:
        return
    # 시각 체크
    if now.hour != eod_h or now.minute != eod_m:
        return
    # 오늘 이미 보냈으면 스킵
    today = now.strftime("%Y-%m-%d")
    if state.get("eod_sent") == today:
        return

    state["eod_sent"] = today
    products    = sorted(data.get("products", []), key=lambda p: -p["maxRate"])
    today_alerts = [
        a for a in data.get("alertLog", [])
        if a.get("detectedAt", "").startswith(today)
    ]

    if len(products) == 0:
        notify("📋 오늘의 특판적금", "오늘은 조건에 맞는 특판적금이 없었어요.")

    elif today_alerts:
        new_ones = [a for a in today_alerts if a["type"] == "new"]
        rate_ups = [a for a in today_alerts if a["type"] == "rate_up"]
        lines = []
        if new_ones:
            lines.append(f"🆕 신규 {len(new_ones)}건")
        if rate_ups:
            lines.append(f"📈 금리↑ {len(rate_ups)}건")
        top = products[0]
        notify(
            f"📋 오늘 특판 감지 {len(today_alerts)}건!",
            ", ".join(lines) + f" | TOP: {top['bank']} {top['maxRate']}%"
        )

    else:
        top3 = " / ".join(f"{p['bank']} {p['maxRate']}%" for p in products[:3])
        notify(
            f"📋 오늘 새 소식 없음 — {len(products)}개 추적 중",
            "금리 TOP: " + top3
        )

    print(f"[퇴근알림] 전송 완료")

# ── 메인 ──────────────────────────────────────
def main():
    now = datetime.now(KST)
    print(f"[{now.strftime('%Y-%m-%d %H:%M')} KST] 실행 시작")

    # 웹앱 설정 로드
    settings = load_settings()
    noti_mode = settings.get("notiMode", "mac")
    eod_cfg   = settings.get("eod", DEFAULT_SETTINGS["eod"])

    # notiMode가 none이면 신규/금리 알림 건너뜀
    if noti_mode == "none":
        print("[설정] 신규·금리 알림 꺼짐")

    data = fetch_savings()
    if not data:
        return

    state = load_state()

    if noti_mode != "none":
        check_alerts(data, state, noti_mode)

    check_eod(data, state, eod_cfg)
    save_state(state)
    print("완료")

if __name__ == "__main__":
    main()
