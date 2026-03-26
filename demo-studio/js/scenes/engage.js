// Engage Order Flow Scene - batch AI reply simulation
const EngageScene = (() => {
  let interval = null;
  let processInterval = null;
  let queue = [];
  let processed = 0;
  let total = 0;

  function buildUI() {
    const scene = document.getElementById('scene-engage');
    if (!scene || scene.children.length > 0) return;

    scene.innerHTML = `
      <div class="engage-header">
        <input class="search-box" value="#Bitcoin #AI #DeFi" readonly>
        <button class="btn-primary" id="engage-search-btn">Search & Engage</button>
      </div>
      <div class="engage-stats">
        <div class="engage-stat-item">
          <div class="engage-stat-num" id="engage-found">0</div>
          <div class="engage-stat-label">Tweets Found</div>
        </div>
        <div class="engage-stat-item">
          <div class="engage-stat-num" id="engage-processed">0</div>
          <div class="engage-stat-label">AI Processed</div>
        </div>
        <div class="engage-stat-item">
          <div class="engage-stat-num" id="engage-sent">0</div>
          <div class="engage-stat-label">Replies Sent</div>
        </div>
        <div class="engage-stat-item">
          <div class="engage-stat-num" id="engage-rate">0%</div>
          <div class="engage-stat-label">Success Rate</div>
        </div>
        <div class="engage-stat-item">
          <div class="engage-stat-num" id="engage-speed">0s</div>
          <div class="engage-stat-label">Avg Response</div>
        </div>
      </div>
      <div class="engage-progress">
        <div class="engage-progress-bar" id="engage-bar"></div>
      </div>
      <div class="engage-list" id="engage-list"></div>
    `;
  }

  function addEngageItem(status = 'pending') {
    const list = document.getElementById('engage-list');
    if (!list) return;

    const displayName = UsernameGen.genDisplayName();
    const handle = UsernameGen.genHandle();
    const tweet = TweetGen.genTweet();
    const metrics = TweetGen.genMetrics();
    const time = TweetGen.genTimestamp();

    const item = document.createElement('div');
    item.className = 'engage-item';
    item.dataset.status = status;

    item.innerHTML = `
      <div class="engage-item-header">
        <div class="notif-user">
          <div class="avatar">${UsernameGen.genAvatar(displayName)}</div>
          <div>
            <span class="username">${displayName}</span>
            <span class="handle">${handle}</span>
          </div>
        </div>
        <div style="display:flex;gap:12px;font-size:12px;color:var(--muted-fg)">
          <span>${NumberAnim.formatCompact(metrics.likes)} likes</span>
          <span>${NumberAnim.formatCompact(metrics.retweets)} RT</span>
          <span>${NumberAnim.formatCompact(metrics.views)} views</span>
        </div>
      </div>
      <div class="engage-tweet">${tweet}</div>
      <div class="engage-action-area"></div>
    `;

    list.appendChild(item);
    total++;
    NumberAnim.animateTo(document.getElementById('engage-found'), total, 400);

    // Keep max 15 visible
    while (list.children.length > 15) {
      list.removeChild(list.firstChild);
    }

    return item;
  }

  function processItem(item) {
    if (!item || item.dataset.status !== 'pending') return;
    item.dataset.status = 'processing';

    const area = item.querySelector('.engage-action-area');
    if (!area) return;

    // Show analyzing state
    area.innerHTML = `<div class="notif-status replying"><span>&#8987;</span> AI Generating Reply<span class="typing-dots"><span>.</span><span>.</span><span>.</span></span></div>`;

    const delay = 800 + Math.random() * 1500;
    setTimeout(() => {
      const success = Math.random() > 0.03;
      if (success) {
        const reply = TweetGen.genReply();
        area.innerHTML = `<div class="engage-reply">${reply}</div>
          <div class="notif-status sent" style="margin-top:6px"><span>&#10003;</span> Reply Sent</div>`;
        item.dataset.status = 'done';
        Anim.particleBurst(item, '#22c55e', 5);
      } else {
        area.innerHTML = `<div class="notif-status fail"><span>&#10007;</span> Rate Limited - Retry Queued</div>`;
        item.dataset.status = 'failed';
      }

      processed++;
      updateEngageStats();
    }, delay);
  }

  function updateEngageStats() {
    const sent = document.querySelectorAll('.engage-item[data-status="done"]').length;
    const failed = document.querySelectorAll('.engage-item[data-status="failed"]').length;
    const rate = processed > 0 ? ((sent / processed) * 100) : 0;
    const speed = (0.8 + Math.random() * 1.5).toFixed(1);

    NumberAnim.animateTo(document.getElementById('engage-processed'), processed, 400);
    NumberAnim.animateTo(document.getElementById('engage-sent'), sent, 400);
    NumberAnim.animateTo(document.getElementById('engage-rate'), rate, 400, '%');

    const speedEl = document.getElementById('engage-speed');
    if (speedEl) speedEl.textContent = speed + 's';

    const bar = document.getElementById('engage-bar');
    if (bar && total > 0) {
      bar.style.width = Math.min(100, (processed / total) * 100) + '%';
    }
  }

  function start(speed = 1) {
    buildUI();
    const addRate = 1500 / speed;
    const processRate = 2000 / speed;

    interval = setInterval(() => { addEngageItem('pending'); }, addRate);

    processInterval = setInterval(() => {
      const pending = document.querySelector('.engage-item[data-status="pending"]');
      if (pending) processItem(pending);
    }, processRate);
  }

  function stop() {
    if (interval) { clearInterval(interval); interval = null; }
    if (processInterval) { clearInterval(processInterval); processInterval = null; }
  }

  function reset() {
    stop();
    processed = 0;
    total = 0;
    const scene = document.getElementById('scene-engage');
    if (scene) scene.innerHTML = '';
  }

  function batchComplete() {
    const items = document.querySelectorAll('.engage-item[data-status="pending"]');
    items.forEach((item, i) => {
      setTimeout(() => processItem(item), i * 300);
    });
  }

  return { start, stop, reset, batchComplete, buildUI };
})();
