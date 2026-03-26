// Monitor Storm Scene - real-time notification flood
const MonitorScene = (() => {
  let interval = null;
  let logInterval = null;
  let stats = { accounts: 0, tweets: 0, replies: 0, success: 0 };

  const statuses = ['new', 'processing', 'done', 'done', 'done', 'failed'];
  const statusLabels = {
    new: { text: 'New Tweet Detected', cls: 'analyzing', icon: '&#9679;' },
    processing: { text: 'AI Analyzing...', cls: 'replying', icon: '&#8987;' },
    done: { text: 'Reply Sent', cls: 'sent', icon: '&#10003;' },
    failed: { text: 'Rate Limited', cls: 'fail', icon: '&#10007;' }
  };

  function createNotification() {
    const feed = document.getElementById('notification-feed');
    if (!feed) return;

    const displayName = UsernameGen.genDisplayName();
    const handle = UsernameGen.genHandle();
    const tweet = TweetGen.genTweet();
    const time = TweetGen.genTimestamp();
    const status = statuses[Math.floor(Math.random() * statuses.length)];
    const sl = statusLabels[status];

    const item = document.createElement('div');
    item.className = `notif-item ${status}`;
    item.innerHTML = `
      <div class="notif-header">
        <div class="notif-user">
          <div class="avatar">${UsernameGen.genAvatar(displayName)}</div>
          <div>
            <span class="username">${displayName}</span>
            <span class="handle">${handle}</span>
          </div>
        </div>
        <span class="notif-time">${time}</span>
      </div>
      <div class="notif-content">${tweet}</div>
      <div class="notif-status ${sl.cls}">
        <span>${sl.icon}</span> ${sl.text}
        ${status === 'processing' ? '<span class="typing-dots"><span>.</span><span>.</span><span>.</span></span>' : ''}
      </div>
    `;

    // Insert at top
    feed.insertBefore(item, feed.firstChild);

    // Keep max 20 items
    while (feed.children.length > 20) {
      feed.removeChild(feed.lastChild);
    }

    // Animate processing -> done
    if (status === 'processing') {
      setTimeout(() => evolveNotification(item), 1500 + Math.random() * 2000);
    }

    // Update stats
    if (status === 'done') {
      stats.replies++;
      updateStatValue('stat-replies', stats.replies);
    }
    stats.tweets++;
    updateStatValue('stat-tweets', stats.tweets);
    updateSuccessRate();

    return item;
  }

  function evolveNotification(item) {
    if (!item || !item.parentNode) return;
    const reply = TweetGen.genReply();
    const sl = statusLabels.done;

    item.className = 'notif-item done';
    const statusEl = item.querySelector('.notif-status');
    if (statusEl) {
      statusEl.className = 'notif-status sent';
      statusEl.innerHTML = `<span>${sl.icon}</span> ${sl.text}`;
    }

    // Add reply preview
    const replyEl = document.createElement('div');
    replyEl.className = 'engage-reply';
    replyEl.style.marginTop = '8px';
    replyEl.style.opacity = '0';
    replyEl.textContent = reply;
    item.appendChild(replyEl);

    setTimeout(() => { replyEl.style.opacity = '1'; }, 100);
    Anim.particleBurst(item, '#22c55e', 6);

    stats.replies++;
    updateStatValue('stat-replies', stats.replies);
    updateSuccessRate();
  }

  function updateStatValue(id, value) {
    const card = document.getElementById(id);
    if (!card) return;
    const el = card.querySelector('.stat-value');
    if (!el) return;
    const suffix = el.dataset.suffix || '';
    NumberAnim.animateTo(el, value, 800, suffix);
  }

  function updateSuccessRate() {
    if (stats.tweets === 0) return;
    const rate = Math.min(99.8, 95 + Math.random() * 4.5);
    const el = document.querySelector('#stat-success .stat-value');
    if (el) NumberAnim.animateTo(el, rate, 600, '%');
  }

  function addLogEntry() {
    const log = document.getElementById('activity-log');
    if (!log) return;

    const actions = [
      { text: 'New tweet detected from {user}', cls: 'log-info' },
      { text: 'AI reply generated for {user}', cls: 'log-action' },
      { text: 'Reply sent successfully to {user}', cls: 'log-action' },
      { text: 'Monitoring {user} timeline...', cls: 'log-info' },
      { text: 'Rate limit warning - cooling down', cls: 'log-warn' },
      { text: 'Retweet executed for {user}', cls: 'log-action' },
      { text: 'Sentiment analysis: Bullish (0.87)', cls: 'log-info' },
      { text: 'Quote tweet drafted for {user}', cls: 'log-action' }
    ];

    const action = actions[Math.floor(Math.random() * actions.length)];
    const handle = UsernameGen.genHandle();
    const time = new Date().toLocaleTimeString('en-US', {
      hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false
    });

    const item = document.createElement('div');
    item.className = 'log-item';
    item.innerHTML = `<span class="log-time">[${time}]</span> <span class="${action.cls}">${action.text.replace('{user}', handle)}</span>`;

    log.insertBefore(item, log.firstChild);
    while (log.children.length > 50) log.removeChild(log.lastChild);

    const countEl = document.getElementById('log-count');
    if (countEl) countEl.textContent = log.children.length + ' events';
  }

  function start(speed = 1) {
    // Init stats
    stats = { accounts: 0, tweets: 0, replies: 0, success: 0 };
    const scale = window._demoScale || 'medium';
    const targets = {
      small: { accounts: 52, tweets: 0, replies: 0 },
      medium: { accounts: 523, tweets: 0, replies: 0 },
      large: { accounts: 2847, tweets: 0, replies: 0 }
    };
    const t = targets[scale];
    stats.accounts = t.accounts;
    updateStatValue('stat-accounts', t.accounts);

    const baseInterval = 2000 / speed;
    interval = setInterval(createNotification, baseInterval);
    logInterval = setInterval(addLogEntry, baseInterval * 0.6);
  }

  function stop() {
    if (interval) { clearInterval(interval); interval = null; }
    if (logInterval) { clearInterval(logInterval); logInterval = null; }
  }

  function reset() {
    stop();
    const feed = document.getElementById('notification-feed');
    const log = document.getElementById('activity-log');
    if (feed) feed.innerHTML = '';
    if (log) log.innerHTML = '';
    stats = { accounts: 0, tweets: 0, replies: 0, success: 0 };
    document.querySelectorAll('#scene-monitor .stat-value').forEach(el => {
      el.textContent = '0' + (el.dataset.suffix || '');
    });
  }

  // Surge: rapid burst of notifications
  function surge() {
    for (let i = 0; i < 5; i++) {
      setTimeout(createNotification, i * 200);
    }
  }

  return { start, stop, reset, surge };
})();
