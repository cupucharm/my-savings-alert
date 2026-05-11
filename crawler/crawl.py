"""
특판적금 크롤러
- 금융감독원 금융상품한눈에 API
- 은행연합회 소비자포털
결과를 savings.json 으로 저장
"""

import json
import os
import hashlib
import requests
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup

KST = timezone(timedelta(hours=9))
MIN_RATE = float(os.getenv("MIN_RATE", "4.0"))   # 최소 금리 기준 (환경변수로 변경 가능)
OUT_FILE = "savings.json"

# ─────────────────────────────────────────────────────────────────────
# 1. 금융감독원 API (적립식 예금 = 적금)
# ─────────────────────────────────────────────────────────────────────
def fetch_fss() -> list[dict]:
    products = []
    for grp in ["020000", "030300"]:   # 은행권, 저축은행
        try:
            url = "https://finlife.fss.or.kr/finlifeapi/installmentSavingsProducts.json"
            params = {
                "auth":        os.getenv("FSS_API_KEY", "sample"),
                "topFinGrpNo": grp,
                "pageNo":      1,
            }
            r = requests.get(url, params=params, timeout=15)
            r.raise_for_status()
            data = r.json().get("result", {})

            # 최고금리 맵 (상품코드 → 최고우대금리)
            rate_map = {}
            for opt in data.get("optionList", []):
                code = opt.get("fin_prdt_cd", "")
                rate = float(opt.get("intr_rate2") or 0)
                if rate > rate_map.get(code, 0):
                    rate_map[code] = rate

            for item in data.get("baseList", []):
                code = item.get("fin_prdt_cd", "")
                max_rate = rate_map.get(code, 0)
                if max_rate < MIN_RATE:
                    continue
                products.append({
                    "id":       hashlib.md5(f"{item.get('kor_co_nm')}{item.get('fin_prdt_nm')}".encode()).hexdigest()[:8],
                    "name":     item.get("fin_prdt_nm", ""),
                    "bank":     item.get("kor_co_nm", ""),
                    "maxRate":  max_rate,
                    "joinWay":  item.get("join_way", ""),
                    "etcNote":  item.get("etc_note", ""),
                    "source":   "금융감독원",
                    "url":      "https://finlife.fss.or.kr",
                })
        except Exception as e:
            print(f"[FSS] 오류: {e}")
    return products


# ─────────────────────────────────────────────────────────────────────
# 2. 은행연합회 소비자포털 크롤링
# ─────────────────────────────────────────────────────────────────────
def fetch_kfb() -> list[dict]:
    products = []
    try:
        url = "https://portal.kfb.or.kr/compare/receiving_installment_3.php"
        headers = {"User-Agent": "Mozilla/5.0 (compatible; savings-bot/1.0)"}
        r = requests.get(url, headers=headers, timeout=15)
        r.encoding = "utf-8"
        soup = BeautifulSoup(r.text, "html.parser")

        for row in soup.select("table tbody tr"):
            cols = row.select("td")
            if len(cols) < 5:
                continue
            try:
                name     = cols[0].get_text(strip=True)
                bank     = cols[1].get_text(strip=True)
                period   = cols[2].get_text(strip=True)
                max_rate = float(cols[4].get_text(strip=True).replace("%", "").strip() or 0)
            except (ValueError, IndexError):
                continue

            if max_rate < MIN_RATE:
                continue

            products.append({
                "id":       hashlib.md5(f"{bank}{name}".encode()).hexdigest()[:8],
                "name":     name,
                "bank":     bank,
                "maxRate":  max_rate,
                "period":   period,
                "joinWay":  "",
                "etcNote":  "",
                "source":   "은행연합회",
                "url":      url,
            })
    except Exception as e:
        print(f"[KFB] 오류: {e}")
    return products


# ─────────────────────────────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────────────────────────────
def main():
    print(f"[{datetime.now(KST).strftime('%Y-%m-%d %H:%M')} KST] 크롤링 시작")

    # 이전 데이터 로드
    prev: dict[str, dict] = {}
    if os.path.exists(OUT_FILE):
        try:
            saved = json.loads(open(OUT_FILE, encoding="utf-8").read())
            prev = {p["id"]: p for p in saved.get("products", [])}
        except Exception:
            pass

    # 수집
    all_products = fetch_fss() + fetch_kfb()

    # 중복 제거 (같은 id → 금리 높은 것만)
    merged: dict[str, dict] = {}
    for p in all_products:
        pid = p["id"]
        if pid not in merged or p["maxRate"] > merged[pid]["maxRate"]:
            merged[pid] = p

    # 변동 감지
    alerts = []
    for pid, p in merged.items():
        if pid not in prev:
            alerts.append({"type": "new",       "product": p})
            print(f"  🆕 신규: {p['bank']} {p['name']} {p['maxRate']}%")
        elif p["maxRate"] > prev[pid]["maxRate"] + 0.1:
            alerts.append({"type": "rate_up",
                           "product": p,
                           "prevRate": prev[pid]["maxRate"]})
            print(f"  📈 금리↑: {p['bank']} {p['name']} {prev[pid]['maxRate']}% → {p['maxRate']}%")

    if not alerts:
        print("  변동 없음")

    # 저장
    output = {
        "updatedAt": datetime.now(KST).isoformat(),
        "products":  list(merged.values()),
        "alerts":    alerts,
    }
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"저장 완료 → {OUT_FILE}  ({len(merged)}개 상품, {len(alerts)}건 알림)")


if __name__ == "__main__":
    main()
