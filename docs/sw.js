// 특판레이더 Service Worker
// 탭이 닫혀있어도 백그라운드에서 동작

const CACHE = 'savings-radar-v1';

// ── 설치 ──────────────────────────────────────
self.addEventListener('install', e => {
  self.skipWaiting();
});

self.addEventListener('activate', e => {
  e.waitUntil(clients.claim());
});

// ── 메인 페이지에서 메시지 수신 ───────────────
self.addEventListener('message', e => {
  const { type, payload } = e.data || {};

  if (type === 'SET_CONFIG') {
    self._config = payload;
    console.log('[SW] 설정 수신:', JSON.stringify(payload));
    if (!_pollTimer) startPolling();
  }

  if (type === 'START_POLL') {
    // SET_CONFIG가 먼저 왔으면 이미 시작됨, 아니면 여기서 시작
    startPolling();
  }

  if (type === 'STOP_POLL') {
    stopPolling();
  }
});

// ── 폴링 루프 ─────────────────────────────────
let _pollTimer  = null;
let _seenAlerts = new Set();

function startPolling() {
  if (_pollTimer) return;
  console.log('[SW] 폴링 시작');
  runPoll();
  _pollTimer = setInterval(runPoll, 10 * 60 * 1000); // 10분
}

function stopPolling() {
  clearInterval(_pollTimer);
  _pollTimer = null;
  console.log('[SW] 폴링 중지');
}

// ── 신규/금리 변동 폴링 ───────────────────────
async function runPoll() {
  const cfg = self._config;
  if (!cfg || !cfg.jsonUrl) return;

  try {
    const res  = await fetch(cfg.jsonUrl + '?t=' + Date.now());
    const data = await res.json();

    // 열려있는 탭에 데이터 전달 (통계 업데이트용)
    const allClients = await clients.matchAll({ type: 'window' });
    allClients.forEach(c => c.postMessage({ type: 'POLL_DATA', payload: data }));

    // 퇴근 알림 체크
    await checkEod(data);

    // 알림 처리
    for (const alert of (data.alerts || [])) {
      const key = alert.product.id + alert.type;
      if (_seenAlerts.has(key)) continue;
      _seenAlerts.add(key);

      const p     = alert.product;
      const isNew = alert.type === 'new';
      await self.registration.showNotification(
        isNew ? '🆕 특판적금 신규 출시' : '📈 특판적금 금리 상승',
        {
          body: `${p.bank} ${p.name}\n최고 ${p.maxRate}% (세전)`,
          tag:  'savings-' + p.id,
          icon: 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><text y=".9em" font-size="90">💰</text></svg>',
          requireInteraction: true,
          data: { url: cfg.pageUrl }
        }
      );
    }
  } catch (err) {
    console.error('[SW] 폴링 실패:', err);
  }
}

// ── 퇴근 알림 (17:50 고정) ───────────────────
const EOD_HOUR   = 17;
const EOD_MINUTE = 50;
let _eodSentToday = null;

async function checkEod(data) {
  const now = new Date();

  // 평일만 (1=월 ~ 5=금)
  if (now.getDay() === 0 || now.getDay() === 6) return;

  // 17:50 체크 (폴링이 10분 단위라 17:40~17:59 사이에 한 번 실행됨)
  if (now.getHours() !== EOD_HOUR) return;
  if (now.getMinutes() < EOD_MINUTE) return;

  // 오늘 이미 보냈으면 스킵
  const todayStr = now.toISOString().slice(0, 10);
  if (_eodSentToday === todayStr) return;
  _eodSentToday = todayStr;

  const products    = (data.products || []).sort((a, b) => b.maxRate - a.maxRate);
  const todayAlerts = (data.alertLog || []).filter(a => (a.detectedAt || "").startsWith(todayStr));
  const icon = 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><text y=".9em" font-size="90">💰</text></svg>';
  const pageUrl = (self._config || {}).pageUrl || '/';

  let title, body;
  if (products.length === 0) {
    title = "📋 오늘의 특판적금";
    body  = "오늘은 조건에 맞는 특판적금이 없었어요.";
  } else if (todayAlerts.length > 0) {
    const newOnes = todayAlerts.filter(a => a.type === "new");
    const rateUps = todayAlerts.filter(a => a.type === "rate_up");
    const lines = [];
    if (newOnes.length) lines.push(`🆕 신규 ${newOnes.length}건: ${newOnes.slice(0,2).map(a=>`${a.bank} ${a.maxRate}%`).join(", ")}`);
    if (rateUps.length) lines.push(`📈 금리↑ ${rateUps.length}건: ${rateUps.slice(0,2).map(a=>`${a.bank} ${a.maxRate}%`).join(", ")}`);
    const top = products.slice(0, 2).map(p => `${p.bank} ${p.name} ${p.maxRate}%`).join("
");
    title = `📋 오늘 특판 감지 ${todayAlerts.length}건!`;
    body  = lines.join("
") + "

금리 TOP:
" + top;
  } else {
    const top3 = products.slice(0, 3).map(p => `${p.bank} ${p.name} ${p.maxRate}%`).join("
");
    const more = products.length > 3 ? `
외 ${products.length - 3}개` : "";
    title = `📋 오늘 새 소식 없음 — ${products.length}개 추적 중`;
    body  = "오늘 신규 출시나 금리 변동은 없었어요.

현재 금리 TOP:
" + top3 + more;
  }

  await self.registration.showNotification(title, {
    body, icon, tag: "eod-summary", requireInteraction: true,
    data: { url: pageUrl }
  });
  console.log("[SW] 퇴근 알림 전송:", title);
}

// ── 알림 클릭 시 탭 열기 ──────────────────────
self.addEventListener('notificationclick', e => {
  e.notification.close();
  const url = (e.notification.data || {}).url || '/';
  e.waitUntil(
    clients.matchAll({ type: 'window' }).then(list => {
      const existing = list.find(c => c.url.includes('my-savings-alert'));
      if (existing) return existing.focus();
      return clients.openWindow(url);
    })
  );
});
