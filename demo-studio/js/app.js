// HAA Demo Studio - Main Controller
let _currentScene = 'monitor';
let _isPlaying = false;
let _speed = 1;
window._demoScale = 'medium';

const scenes = {
  monitor: { module: MonitorScene, title: 'Account Monitor', desc: 'Real-time monitoring of KOL accounts and AI auto-reply' },
  engage: { module: EngageScene, title: 'Smart Engage', desc: 'AI-powered batch engagement and reply automation' },
  dashboard: { module: DashboardScene, title: 'Data Overview', desc: 'Performance metrics and engagement analytics' }
};

// Scene switching
function switchScene(name) {
  if (_isPlaying) stopAll();

  // Update nav
  document.querySelectorAll('.nav-item').forEach(el => {
    el.classList.toggle('active', el.dataset.scene === name);
  });

  // Update content
  document.querySelectorAll('.scene').forEach(el => {
    el.classList.toggle('active', el.id === 'scene-' + name);
  });

  // Update header
  const s = scenes[name];
  document.getElementById('scene-title').textContent = s.title;
  document.getElementById('scene-desc').textContent = s.desc;

  _currentScene = name;

  // Build UI for non-monitor scenes
  if (name === 'engage') EngageScene.buildUI();
  if (name === 'dashboard') DashboardScene.buildUI();
}

// Playback controls
function togglePlay() {
  if (_isPlaying) {
    stopAll();
  } else {
    startCurrent();
  }
}

function startCurrent() {
  _isPlaying = true;
  document.getElementById('btn-play').textContent = 'Pause';
  document.getElementById('btn-play').classList.add('active');
  scenes[_currentScene].module.start(_speed);
}

function stopAll() {
  _isPlaying = false;
  document.getElementById('btn-play').textContent = 'Start';
  document.getElementById('btn-play').classList.remove('active');
  Object.values(scenes).forEach(s => s.module.stop());
}

function resetScene() {
  stopAll();
  scenes[_currentScene].module.reset();
}

// Speed control
function setSpeed(s) {
  _speed = s;
  document.querySelectorAll('.director-section:first-child .dir-btn').forEach(btn => {
    btn.classList.remove('active');
  });
  event.target.classList.add('active');

  if (_isPlaying) {
    scenes[_currentScene].module.stop();
    scenes[_currentScene].module.start(_speed);
  }
}

// Scale control
function setScale(scale) {
  window._demoScale = scale;
  document.querySelectorAll('.director-section:nth-child(2) .dir-btn').forEach(btn => {
    btn.classList.remove('active');
  });
  event.target.classList.add('active');
}

// Director panel toggle
function toggleDirector() {
  const panel = document.getElementById('director-panel');
  const body = document.getElementById('director-body');
  panel.classList.toggle('hidden');
  if (!panel.classList.contains('hidden')) {
    body.classList.add('open');
  } else {
    body.classList.remove('open');
  }
}

// Trigger events
function triggerSurge() {
  if (_currentScene === 'monitor') MonitorScene.surge();
}

function triggerBatchComplete() {
  if (_currentScene === 'engage') EngageScene.batchComplete();
}

// Init
document.addEventListener('DOMContentLoaded', () => {
  Particles.init();
  // Director panel starts hidden, press D to toggle
  document.getElementById('director-panel').classList.add('hidden');
});

// Keyboard shortcuts
document.addEventListener('keydown', (e) => {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
  switch(e.key.toLowerCase()) {
    case 'd': toggleDirector(); break;
    case ' ': e.preventDefault(); togglePlay(); break;
    case 's': triggerSurge(); break;
    case 'b': triggerBatchComplete(); break;
    case 'r': resetScene(); break;
    case '1': switchScene('monitor'); break;
    case '2': switchScene('engage'); break;
    case '3': switchScene('dashboard'); break;
  }
});
