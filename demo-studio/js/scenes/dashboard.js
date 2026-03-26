// Dashboard Data Overview Scene - big numbers + charts
const DashboardScene = (() => {
  let interval = null;

  function buildUI() {
    const scene = document.getElementById('scene-dashboard');
    if (!scene || scene.children.length > 0) return;

    scene.innerHTML = `
      <div class="dash-big-stats">
        <div class="big-stat">
          <div class="big-stat-value" id="dash-interactions">0</div>
          <div class="big-stat-label">Total Interactions</div>
        </div>
        <div class="big-stat">
          <div class="big-stat-value" id="dash-reach">0</div>
          <div class="big-stat-label">Users Reached</div>
        </div>
        <div class="big-stat">
          <div class="big-stat-value" id="dash-ai-replies">0</div>
          <div class="big-stat-label">AI Replies Generated</div>
        </div>
      </div>
      <div class="stats-grid" style="margin-bottom:20px">
        <div class="stat-card">
          <div class="stat-label">Accounts Monitored</div>
          <div class="stat-value" id="dash-accounts">0</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Avg Response Time</div>
          <div class="stat-value" id="dash-response">0s</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Success Rate</div>
          <div class="stat-value" id="dash-rate">0%</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Active Campaigns</div>
          <div class="stat-value" id="dash-campaigns">0</div>
        </div>
      </div>
      <div class="dash-grid">
        <div class="dash-chart-card">
          <h3>Daily Interactions (7d)</h3>
          <div class="chart-area">
            <div class="chart-bar-group" id="chart-bars"></div>
          </div>
        </div>
        <div class="dash-chart-card">
          <h3>Engagement Growth</h3>
          <div class="chart-area">
            <div class="chart-line-area" id="chart-line"></div>
          </div>
        </div>
      </div>
    `;

    buildBarChart();
    buildLineChart();
  }

  function buildBarChart() {
    const container = document.getElementById('chart-bars');
    if (!container) return;
    const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
    container.innerHTML = '';
    days.forEach(day => {
      const bar = document.createElement('div');
      bar.className = 'chart-bar';
      bar.style.height = '4px';
      bar.title = day;
      container.appendChild(bar);
    });
  }

  function animateBars() {
    const bars = document.querySelectorAll('#chart-bars .chart-bar');
    bars.forEach((bar, i) => {
      const height = 30 + Math.random() * 65;
      setTimeout(() => {
        bar.style.height = height + '%';
      }, i * 150);
    });
  }

  function buildLineChart() {
    const container = document.getElementById('chart-line');
    if (!container) return;

    const w = 500, h = 180;
    const points = 14;
    let path = '';
    let fillPath = `M 0 ${h} `;
    const coords = [];

    for (let i = 0; i < points; i++) {
      const x = (i / (points - 1)) * w;
      const base = h * 0.7 - (i / points) * h * 0.5;
      const y = base + (Math.random() - 0.5) * 40;
      coords.push({ x, y: Math.max(10, Math.min(h - 10, y)) });
    }

    coords.forEach((p, i) => {
      path += (i === 0 ? 'M' : 'L') + ` ${p.x} ${p.y} `;
      fillPath += `L ${p.x} ${p.y} `;
    });
    fillPath += `L ${w} ${h} Z`;

    container.innerHTML = `
      <svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none">
        <defs>
          <linearGradient id="gradient-green" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="#22c55e" stop-opacity="0.3"/>
            <stop offset="100%" stop-color="#22c55e" stop-opacity="0"/>
          </linearGradient>
        </defs>
        <path class="chart-fill" d="${fillPath}"/>
        <path class="chart-line" d="${path}"
          stroke-dasharray="1000" stroke-dashoffset="1000"
          style="animation: draw-line 2s ease-out forwards"/>
      </svg>
    `;
  }

  function start(speed = 1) {
    buildUI();
    const scale = window._demoScale || 'medium';
    const targets = {
      small: { interactions: 1247, reach: 8420, ai: 892, accounts: 52, campaigns: 3 },
      medium: { interactions: 12847, reach: 84200, ai: 8923, accounts: 523, campaigns: 12 },
      large: { interactions: 128470, reach: 842000, ai: 89230, accounts: 2847, campaigns: 47 }
    };
    const t = targets[scale];

    // Animate big numbers
    setTimeout(() => NumberAnim.animateTo(document.getElementById('dash-interactions'), t.interactions, 2000), 200);
    setTimeout(() => NumberAnim.animateTo(document.getElementById('dash-reach'), t.reach, 2000), 400);
    setTimeout(() => NumberAnim.animateTo(document.getElementById('dash-ai-replies'), t.ai, 2000), 600);

    // Animate small stats
    setTimeout(() => NumberAnim.animateTo(document.getElementById('dash-accounts'), t.accounts, 1500), 800);
    setTimeout(() => {
      const el = document.getElementById('dash-response');
      if (el) el.textContent = '1.3s';
    }, 1000);
    setTimeout(() => {
      const el = document.getElementById('dash-rate');
      if (el) el.textContent = '99.2%';
    }, 1200);
    setTimeout(() => NumberAnim.animateTo(document.getElementById('dash-campaigns'), t.campaigns, 1000), 1400);

    // Animate charts
    setTimeout(animateBars, 1000);

    // Periodic updates
    interval = setInterval(() => {
      const el = document.getElementById('dash-interactions');
      if (el) NumberAnim.increment(el, 5, 30);
    }, 3000 / speed);
  }

  function stop() {
    if (interval) { clearInterval(interval); interval = null; }
  }

  function reset() {
    stop();
    const scene = document.getElementById('scene-dashboard');
    if (scene) scene.innerHTML = '';
  }

  return { start, stop, reset, buildUI };
})();
