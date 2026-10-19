/**
 * Personal AI Call Assistant — Client Application
 * Hindi call screening simulation, voice synthesis, real-time summary, and dashboard.
 */

// Application State
const state = {
  calls: [],
  activeCategory: 'all',
  searchQuery: '',
  activeCallDetail: null,
  sim: {
    stepIndex: 0,
    callerPhone: '+91 98123 45678',
    transcript: [],
    extractedState: {
      caller_name: '',
      purpose: '',
      urgency: 'Not confirmed',
      message: '',
      had_follow_up: false,
    },
    isListening: false,
    currentPresetKey: null,
    presetSteps: [],
  },
  settings: {},
};

// Preset Scenarios for Rapid Testing
const PRESET_SCENARIOS = {
  aman: {
    callerPhone: '+91 98123 45678',
    turns: [
      'मेरा नाम अमन है।',
      'मुझे कॉलेज प्रोजेक्ट और फाइनल सबमिशन पर चर्चा करनी है।',
      'जब भी समय मिले कॉल बैक कर लें, कोई जल्दी नहीं है।',
      'सबमिशन की स्लाइड्स तैयार हैं, एक बार रिव्यू करना है।',
    ],
  },
  doctor: {
    callerPhone: '+91 98450 11223',
    turns: [
      'मैं डॉ. शर्मा के क्लीनिक से बोल रहा हूँ।',
      'कल के मेडिकल टेस्ट की रिपोर्ट आ गई है, जरूरी परामर्श चाहिए।',
      'हाँ, यह बहुत ज़रूरी (emergency) है, कृपया तुरंत बात करें।',
      'रिपोर्ट ईमेल पर भेज दी गई है, कृपया डॉक्टर से तुरंत बात करें।',
    ],
  },
  spam: {
    callerPhone: '+91 140 9876543',
    turns: [
      'बैंक लोन डिपार्टमेंट।',
      'सर आपके लिए 5 लाख का प्री-अप्रूव्ड पर्सनल लोन और क्रेडिट कार्ड ऑफर है।',
      'सिर्फ आज के लिए विशेष ऑफर है, जल्दी बताएं।',
      'कार्ड एक्टिवेट कराने के लिए आधार विवरण चाहिए।',
    ],
  },
  unknown: {
    callerPhone: '+91 99000 11222',
    turns: [
      'मैं अपना नाम नहीं बताना चाहता, सीधे बात कराओ।',
      'निजी काम है, तुमसे क्या मतलब।',
      'बाद में फोन करने को बोल देना।',
      'कोई मैसेज नहीं है।',
    ],
  },
};

// DOM Elements
const DOM = {
  // Metrics
  metricTotal: document.getElementById('metricTotal'),
  metricUrgent: document.getElementById('metricUrgent'),
  metricCompleted: document.getElementById('metricCompleted'),
  metricMissed: document.getElementById('metricMissed'),
  metricFlagged: document.getElementById('metricFlagged'),

  // Filters & List
  categoryFilterContainer: document.getElementById('categoryFilterContainer'),
  searchInput: document.getElementById('searchInput'),
  btnRefreshCalls: document.getElementById('btnRefreshCalls'),
  callsListContainer: document.getElementById('callsListContainer'),

  // Header Buttons
  btnStartSimulation: document.getElementById('btnStartSimulation'),
  btnOpenSettings: document.getElementById('btnOpenSettings'),
  btnOpenSetupGuide: document.getElementById('btnOpenSetupGuide'),

  // Simulation Modal
  simModalOverlay: document.getElementById('simModalOverlay'),
  btnCloseSimModal: document.getElementById('btnCloseSimModal'),
  simIncomingRingView: document.getElementById('simIncomingRingView'),
  simActiveScreeningView: document.getElementById('simActiveScreeningView'),
  simDisplayCallerNumber: document.getElementById('simDisplayCallerNumber'),
  btnSimDecline: document.getElementById('btnSimDecline'),
  btnSimAnswer: document.getElementById('btnSimAnswer'),
  simTranscriptBox: document.getElementById('simTranscriptBox'),
  simCallerInput: document.getElementById('simCallerInput'),
  btnSimSend: document.getElementById('btnSimSend'),
  btnSimMic: document.getElementById('btnSimMic'),
  btnSimEndEarly: document.getElementById('btnSimEndEarly'),
  simStepIndicator: document.getElementById('simStepIndicator'),
  aiSpeechStatus: document.getElementById('aiSpeechStatus'),
  audioWaves: document.getElementById('audioWaves'),
  chkAudioTTS: document.getElementById('chkAudioTTS'),

  // Notification Modal
  notifModalOverlay: document.getElementById('notifModalOverlay'),
  btnCloseNotifModal: document.getElementById('btnCloseNotifModal'),
  notifUrgencyBadge: document.getElementById('notifUrgencyBadge'),
  notifSummaryText: document.getElementById('notifSummaryText'),
  btnCopySummary: document.getElementById('btnCopySummary'),
  btnNotifCallBack: document.getElementById('btnNotifCallBack'),
  btnNotifDismiss: document.getElementById('btnNotifDismiss'),

  // Detail Modal
  detailModalOverlay: document.getElementById('detailModalOverlay'),
  btnCloseDetailModal: document.getElementById('btnCloseDetailModal'),
  detailCallerName: document.getElementById('detailCallerName'),
  detailCallerPhone: document.getElementById('detailCallerPhone'),
  detailCategory: document.getElementById('detailCategory'),
  detailUrgencyBadge: document.getElementById('detailUrgencyBadge'),
  detailSummaryText: document.getElementById('detailSummaryText'),
  detailTranscriptBox: document.getElementById('detailTranscriptBox'),
  btnCopyDetailSummary: document.getElementById('btnCopyDetailSummary'),
  btnDeleteCallRecord: document.getElementById('btnDeleteCallRecord'),
  detailActionButtons: document.getElementById('detailActionButtons'),

  // Settings Modal
  settingsModalOverlay: document.getElementById('settingsModalOverlay'),
  btnCloseSettingsModal: document.getElementById('btnCloseSettingsModal'),
  btnCancelSettings: document.getElementById('btnCancelSettings'),
  btnSaveSettings: document.getElementById('btnSaveSettings'),
  settingOwnerPhone: document.getElementById('settingOwnerPhone'),
  settingGreetingHi: document.getElementById('settingGreetingHi'),
  settingStrictness: document.getElementById('settingStrictness'),
  settingRetention: document.getElementById('settingRetention'),

  // Guide Modal
  guideModalOverlay: document.getElementById('guideModalOverlay'),
  btnCloseGuideModal: document.getElementById('btnCloseGuideModal'),

  // Toast
  toastContainer: document.getElementById('toastContainer'),
};

// ================= Speech Synthesis (Hindi TTS) =================
function speakHindi(text) {
  if (!DOM.chkAudioTTS.checked || !('speechSynthesis' in window)) return;

  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = 'hi-IN';
  utterance.rate = 0.95;

  // Visual audio waves while speaking
  DOM.audioWaves.style.opacity = '1';
  DOM.aiSpeechStatus.textContent = 'AI Assistant speaking in Hindi...';

  utterance.onend = () => {
    DOM.audioWaves.style.opacity = '0.3';
    DOM.aiSpeechStatus.textContent = 'AI Assistant listening...';
  };

  utterance.onerror = () => {
    DOM.audioWaves.style.opacity = '0.3';
    DOM.aiSpeechStatus.textContent = 'Ready';
  };

  window.speechSynthesis.speak(utterance);
}

// ================= Speech Recognition (Hindi STT) =================
let speechRecognizer = null;
function initSpeechRecognition() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) return null;

  const recognizer = new SpeechRecognition();
  recognizer.lang = 'hi-IN';
  recognizer.interimResults = false;
  recognizer.continuous = false;

  recognizer.onstart = () => {
    DOM.btnSimMic.classList.add('listening');
    showToast('🎤 सुन रहा हूँ... बोलिए (Listening in Hindi)');
  };

  recognizer.onresult = (event) => {
    const transcript = event.results[0][0].transcript;
    DOM.simCallerInput.value = transcript;
    DOM.btnSimMic.classList.remove('listening');
    sendCallerResponse(transcript);
  };

  recognizer.onerror = () => {
    DOM.btnSimMic.classList.remove('listening');
  };

  recognizer.onend = () => {
    DOM.btnSimMic.classList.remove('listening');
  };

  return recognizer;
}

// ================= Toast Alerts =================
function showToast(message, duration = 3000) {
  const toast = document.createElement('div');
  toast.className = 'toast';
  toast.innerHTML = `<span>✨</span><span>${escapeHtml(message)}</span>`;
  DOM.toastContainer.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(10px)';
    setTimeout(() => toast.remove(), 300);
  }, duration);
}

// ================= Copy To Clipboard =================
async function copyToClipboard(text) {
  if (!text) return;
  try {
    await navigator.clipboard.writeText(text);
    showToast('✅ Summary copied to clipboard!');
  } catch (err) {
    // Fallback
    const textarea = document.createElement('textarea');
    textarea.value = text;
    document.body.appendChild(textarea);
    textarea.select();
    document.execCommand('copy');
    document.body.removeChild(textarea);
    showToast('✅ Summary copied to clipboard!');
  }
}

// ================= API Calls =================
async function fetchMetrics() {
  try {
    const res = await fetch('/api/metrics');
    if (!res.ok) return;
    const data = await res.json();
    DOM.metricTotal.textContent = data.total || 0;
    DOM.metricUrgent.textContent = data.urgent || 0;
    DOM.metricCompleted.textContent = data.completed || 0;
    DOM.metricMissed.textContent = data.missed || 0;
    DOM.metricFlagged.textContent = data.flagged || 0;
  } catch (err) {
    console.error('Error fetching metrics:', err);
  }
}

async function fetchCalls() {
  try {
    let url = '/api/calls';
    const params = new URLSearchParams();
    if (state.activeCategory !== 'all') {
      params.append('category', state.activeCategory);
    }
    if (params.toString()) {
      url += `?${params.toString()}`;
    }

    const res = await fetch(url);
    if (!res.ok) return;
    const data = await res.json();
    state.calls = data;
    renderCallsList();
  } catch (err) {
    console.error('Error fetching calls:', err);
    DOM.callsListContainer.innerHTML = `<div style="padding: 30px; text-align: center; color: var(--danger);">Failed to load call history.</div>`;
  }
}

async function fetchSettings() {
  try {
    const res = await fetch('/api/settings');
    if (res.ok) {
      state.settings = await res.json();
      if (DOM.settingOwnerPhone) DOM.settingOwnerPhone.value = state.settings.owner_phone || '+91 98765 43210';
      if (DOM.settingGreetingHi) DOM.settingGreetingHi.value = state.settings.ai_greeting_hi || '';
      if (DOM.settingStrictness) DOM.settingStrictness.value = state.settings.screening_strictness || 'balanced';
      if (DOM.settingRetention) DOM.settingRetention.value = state.settings.retention_days || '30';
    }
  } catch (err) {
    console.error('Error fetching settings:', err);
  }
}

// ================= Render Calls List =================
function renderCallsList() {
  let filtered = state.calls;

  // Search filter
  if (state.searchQuery.trim()) {
    const q = state.searchQuery.toLowerCase();
    filtered = filtered.filter(
      (c) =>
        (c.caller_name && c.caller_name.toLowerCase().includes(q)) ||
        (c.caller_number && c.caller_number.toLowerCase().includes(q)) ||
        (c.purpose && c.purpose.toLowerCase().includes(q)) ||
        (c.message && c.message.toLowerCase().includes(q)) ||
        (c.category && c.category.toLowerCase().includes(q))
    );
  }

  if (filtered.length === 0) {
    DOM.callsListContainer.innerHTML = `
      <div style="padding: 50px 20px; text-align: center; color: var(--text-dim);">
        <div style="font-size: 2.2rem; margin-bottom: 8px;">📭</div>
        <div style="font-size: 1rem; color: var(--text-muted); font-weight: 600;">No Screened Calls Found</div>
        <p style="font-size: 0.82rem; margin-top: 4px;">Click <strong>Simulate Incoming Call</strong> to test screening.</p>
      </div>
    `;
    return;
  }

  DOM.callsListContainer.innerHTML = filtered
    .map((call) => {
      const urgencyClass = (call.urgency || '').toLowerCase().replace(' ', '-');
      const timeStr = call.created_at ? formatTime(call.created_at) : 'Just now';
      const decisionBadge = getDecisionBadge(call.owner_decision);

      return `
      <div class="call-item" data-call-id="${call.id}">
        <div class="caller-identity">
          <div class="caller-avatar" aria-hidden="true">${getCategoryIcon(call.category)}</div>
          <div>
            <div class="caller-name">${escapeHtml(call.caller_name || 'Unknown')}</div>
            <div class="caller-phone">${escapeHtml(call.caller_number || '')}</div>
          </div>
        </div>

        <div class="call-summary-col">
          <div class="call-purpose">${escapeHtml(call.purpose || 'No purpose recorded')}</div>
          <div class="call-snippet">💬 ${escapeHtml(call.message || call.suggested_action || '')}</div>
          <div style="font-size: 0.72rem; color: var(--text-dim); margin-top: 2px;">🕒 ${timeStr} • ${decisionBadge}</div>
        </div>

        <div>
          <span class="badge-urgency ${urgencyClass}">${escapeHtml(call.urgency || 'Not confirmed')}</span>
        </div>

        <div>
          <span class="category-tag">${escapeHtml(call.category || 'Unknown')}</span>
        </div>

        <div class="action-cell">
          <button class="btn btn-secondary btn-sm btn-view-call" data-id="${call.id}">Details</button>
          <button class="btn btn-primary btn-sm btn-copy-card" data-summary="${escapeHtml(call.summary_text || '')}" title="Copy Summary">📋</button>
        </div>
      </div>
    `;
    })
    .join('');

  // Attach event listeners for item buttons
  DOM.callsListContainer.querySelectorAll('.btn-view-call').forEach((btn) => {
    btn.addEventListener('click', () => openCallDetails(btn.dataset.id));
  });

  DOM.callsListContainer.querySelectorAll('.btn-copy-card').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      copyToClipboard(btn.dataset.summary);
    });
  });
}

// Helpers
function getCategoryIcon(cat) {
  switch (cat) {
    case 'Important': return '🚨';
    case 'Work': return '💼';
    case 'Personal': return '🏡';
    case 'Suspected Spam': return '🛡️';
    default: return '👤';
  }
}

function getDecisionBadge(dec) {
  if (dec === 'accepted') return '<span style="color: #34d399;">Accepted</span>';
  if (dec === 'declined') return '<span style="color: #f87171;">Declined</span>';
  if (dec === 'callback_requested') return '<span style="color: #60a5fa;">Callback Requested</span>';
  return '<span style="color: #94a3b8;">Pending Review</span>';
}

function formatTime(isoStr) {
  try {
    const d = new Date(isoStr);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) + ', ' + d.toLocaleDateString([], { month: 'short', day: 'numeric' });
  } catch (e) {
    return isoStr;
  }
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

// ================= SIMULATION WORKFLOW =================
function startSimulation(phone = '+91 98123 45678') {
  state.sim.callerPhone = phone;
  state.sim.stepIndex = 0;
  state.sim.transcript = [];
  state.sim.extractedState = {
    caller_name: '',
    purpose: '',
    urgency: 'Not confirmed',
    message: '',
    had_follow_up: false,
  };
  state.sim.currentPresetKey = null;
  state.sim.presetSteps = [];

  DOM.simDisplayCallerNumber.textContent = phone;
  DOM.simIncomingRingView.style.display = 'block';
  DOM.simActiveScreeningView.style.display = 'none';
  DOM.simTranscriptBox.innerHTML = '';
  DOM.simCallerInput.value = '';

  DOM.simModalOverlay.classList.add('active');
}

async function answerSimulatedCall() {
  DOM.simIncomingRingView.style.display = 'none';
  DOM.simActiveScreeningView.style.display = 'flex';

  // Request Step 0 (Greeting + Name Question)
  try {
    const res = await fetch('/api/simulate/step', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        caller_phone: state.sim.callerPhone,
        step_index: 0,
        caller_text: null,
        transcript: [],
        extracted_state: state.sim.extractedState,
      }),
    });

    const data = await res.json();
    state.sim.stepIndex = data.step_index;
    state.sim.extractedState = data.extracted_state;

    appendTranscriptBubble('ai', data.next_question);
    speakHindi(data.next_question);
    updateStepIndicator();
  } catch (err) {
    console.error('Error starting screening turn:', err);
    showToast('Failed to connect with AI screener engine');
  }
}

async function sendCallerResponse(text) {
  const callerText = (text || DOM.simCallerInput.value || '').trim();
  if (!callerText) return;

  DOM.simCallerInput.value = '';
  appendTranscriptBubble('caller', callerText);

  // Send to backend
  try {
    DOM.aiSpeechStatus.textContent = 'AI Assistant thinking...';
    DOM.audioWaves.style.opacity = '0.7';

    const res = await fetch('/api/simulate/step', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        caller_phone: state.sim.callerPhone,
        step_index: state.sim.stepIndex,
        caller_text: callerText,
        transcript: state.sim.transcript,
        extracted_state: state.sim.extractedState,
      }),
    });

    const data = await res.json();
    state.sim.stepIndex = data.step_index;
    state.sim.extractedState = data.extracted_state;

    // Show AI response
    appendTranscriptBubble('ai', data.next_question);
    speakHindi(data.next_question);
    updateStepIndicator(data.is_follow_up);

    // If finished
    if (data.is_finished) {
      setTimeout(() => {
        finalizeSimulation(false);
      }, 1500);
    }
  } catch (err) {
    console.error('Error in simulation step:', err);
    showToast('Error processing response');
  }
}

async function finalizeSimulation(isFailed = false) {
  try {
    const res = await fetch('/api/simulate/complete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        caller_phone: state.sim.callerPhone,
        extracted_state: state.sim.extractedState,
        transcript: state.sim.transcript,
        duration_sec: 45,
        is_failed: isFailed,
      }),
    });

    const data = await res.json();
    DOM.simModalOverlay.classList.remove('active');

    // Show Notification Preview Modal
    openNotificationPreview(data);

    // Refresh dashboard
    fetchMetrics();
    fetchCalls();
  } catch (err) {
    console.error('Error completing simulation:', err);
  }
}

function appendTranscriptBubble(speaker, text) {
  state.sim.transcript.push({ speaker, text });

  const bubble = document.createElement('div');
  bubble.className = `chat-bubble ${speaker}`;
  const speakerLabel = speaker === 'ai' ? '🤖 AI Assistant' : '👤 Caller';
  bubble.innerHTML = `
    <div class="speaker-lbl">${speakerLabel}</div>
    <div>${escapeHtml(text)}</div>
  `;
  DOM.simTranscriptBox.appendChild(bubble);
  DOM.simTranscriptBox.scrollTop = DOM.simTranscriptBox.scrollHeight;
}

function updateStepIndicator(isFollowUp = false) {
  let label = '';
  switch (state.sim.stepIndex) {
    case 1:
      label = isFollowUp ? 'Follow-up on Name & Caller Identity' : 'Step 1 of 4: Name Question';
      break;
    case 2:
      label = isFollowUp ? 'Follow-up on Purpose Details' : 'Step 2 of 4: Purpose of Call';
      break;
    case 3:
      label = isFollowUp ? 'Follow-up on Urgency & Assistance' : 'Step 3 of 4: Urgency Assessment';
      break;
    case 4:
      label = 'Step 4 of 4: Message for Owner';
      break;
    default:
      label = 'Call Screening Complete';
  }
  DOM.simStepIndicator.textContent = label;
}

// Preset Handler
function applyPreset(presetKey) {
  if (presetKey === 'silent') {
    // End as silent/empty call
    appendTranscriptBubble('caller', '(Silence / No answer from caller)');
    finalizeSimulation(true);
    return;
  }

  const preset = PRESET_SCENARIOS[presetKey];
  if (!preset) return;

  state.sim.currentPresetKey = presetKey;
  state.sim.presetSteps = [...preset.turns];

  // Pick the next answer matching current step
  const answer = state.sim.presetSteps[state.sim.stepIndex - 1] || preset.turns[0];
  DOM.simCallerInput.value = answer;
  sendCallerResponse(answer);
}

// ================= NOTIFICATION PREVIEW MODAL =================
function openNotificationPreview(data) {
  DOM.notifSummaryText.textContent = data.summary;
  DOM.notifUrgencyBadge.textContent = data.urgency || 'Not confirmed';
  DOM.notifUrgencyBadge.className = `badge-urgency ${(data.urgency || '').toLowerCase().replace(' ', '-')}`;

  DOM.btnCopySummary.onclick = () => copyToClipboard(data.summary);
  DOM.btnNotifCallBack.onclick = async () => {
    if (data.call_id) {
      await fetch(`/api/calls/${data.call_id}/decision`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ decision: 'callback_requested' }),
      });
      fetchCalls();
    }
    DOM.notifModalOverlay.classList.remove('active');
    showToast('📞 Callback initiated / marked for follow-up');
  };

  DOM.notifModalOverlay.classList.add('active');
}

// ================= CALL DETAILS DRAWER =================
async function openCallDetails(callId) {
  try {
    const res = await fetch(`/api/calls/${callId}`);
    if (!res.ok) return;
    const call = await res.json();
    state.activeCallDetail = call;

    DOM.detailCallerName.textContent = call.caller_name || 'Unknown';
    DOM.detailCallerPhone.textContent = call.caller_number || '+91 ...';
    DOM.detailCategory.textContent = call.category || 'Unknown';
    DOM.detailSummaryText.textContent = call.summary_text || 'No summary available';

    const urgencyClass = (call.urgency || '').toLowerCase().replace(' ', '-');
    DOM.detailUrgencyBadge.innerHTML = `<span class="badge-urgency ${urgencyClass}">${escapeHtml(call.urgency || 'Not confirmed')}</span>`;

    // Copy button
    DOM.btnCopyDetailSummary.onclick = () => copyToClipboard(call.summary_text);

    // Render transcript bubbles
    DOM.detailTranscriptBox.innerHTML = (call.transcript || [])
      .map(
        (t) => `
        <div class="chat-bubble ${t.speaker}">
          <div class="speaker-lbl">${t.speaker === 'ai' ? '🤖 AI Assistant' : '👤 Caller'}</div>
          <div>${escapeHtml(t.text)}</div>
        </div>
      `
      )
      .join('');

    // Actions
    DOM.detailActionButtons.querySelectorAll('button').forEach((b) => {
      b.onclick = async () => {
        await fetch(`/api/calls/${call.id}/decision`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ decision: b.dataset.action }),
        });
        showToast(`Action recorded: ${b.dataset.action}`);
        fetchCalls();
        DOM.detailModalOverlay.classList.remove('active');
      };
    });

    // Delete
    DOM.btnDeleteCallRecord.onclick = async () => {
      if (!confirm('Are you sure you want to delete this call record for privacy?')) return;
      await fetch(`/api/calls/${call.id}`, { method: 'DELETE' });
      showToast('Call record permanently deleted');
      fetchMetrics();
      fetchCalls();
      DOM.detailModalOverlay.classList.remove('active');
    };

    DOM.detailModalOverlay.classList.add('active');
  } catch (err) {
    console.error('Error opening call details:', err);
  }
}

// ================= EVENT LISTENERS =================
function setupEventListeners() {
  // Category Pills
  DOM.categoryFilterContainer.querySelectorAll('.pill').forEach((pill) => {
    pill.addEventListener('click', () => {
      DOM.categoryFilterContainer.querySelectorAll('.pill').forEach((p) => p.classList.remove('active'));
      pill.classList.add('active');
      state.activeCategory = pill.dataset.cat;
      fetchCalls();
    });
  });

  // Search input
  DOM.searchInput.addEventListener('input', (e) => {
    state.searchQuery = e.target.value;
    renderCallsList();
  });

  // Refresh
  DOM.btnRefreshCalls.addEventListener('click', () => {
    fetchMetrics();
    fetchCalls();
    showToast('Call history refreshed');
  });

  // Modal triggers
  DOM.btnStartSimulation.addEventListener('click', () => startSimulation('+91 98123 45678'));
  DOM.btnOpenSettings.addEventListener('click', () => {
    fetchSettings();
    DOM.settingsModalOverlay.classList.add('active');
  });
  DOM.btnOpenSetupGuide.addEventListener('click', () => DOM.guideModalOverlay.classList.add('active'));

  // Close Modals
  DOM.btnCloseSimModal.addEventListener('click', () => DOM.simModalOverlay.classList.remove('active'));
  DOM.btnCloseNotifModal.addEventListener('click', () => DOM.notifModalOverlay.classList.remove('active'));
  DOM.btnNotifDismiss.addEventListener('click', () => DOM.notifModalOverlay.classList.remove('active'));
  DOM.btnCloseDetailModal.addEventListener('click', () => DOM.detailModalOverlay.classList.remove('active'));
  DOM.btnCloseSettingsModal.addEventListener('click', () => DOM.settingsModalOverlay.classList.remove('active'));
  DOM.btnCancelSettings.addEventListener('click', () => DOM.settingsModalOverlay.classList.remove('active'));
  DOM.btnCloseGuideModal.addEventListener('click', () => DOM.guideModalOverlay.classList.remove('active'));

  // Close on outside overlay click
  [
    DOM.simModalOverlay,
    DOM.notifModalOverlay,
    DOM.detailModalOverlay,
    DOM.settingsModalOverlay,
    DOM.guideModalOverlay,
  ].forEach((overlay) => {
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) overlay.classList.remove('active');
    });
  });

  // Simulation controls
  DOM.btnSimAnswer.addEventListener('click', answerSimulatedCall);
  DOM.btnSimDecline.addEventListener('click', () => {
    DOM.simModalOverlay.classList.remove('active');
    showToast('Call ignored');
  });
  DOM.btnSimSend.addEventListener('click', () => sendCallerResponse());
  DOM.simCallerInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') sendCallerResponse();
  });
  DOM.btnSimEndEarly.addEventListener('click', () => finalizeSimulation(false));

  // Speech Recognition (STT)
  speechRecognizer = initSpeechRecognition();
  DOM.btnSimMic.addEventListener('click', () => {
    if (!speechRecognizer) {
      showToast('Speech Recognition not supported in this browser. Please type.');
      return;
    }
    try {
      speechRecognizer.start();
    } catch (err) {
      speechRecognizer.stop();
    }
  });

  // Presets
  document.querySelectorAll('.preset-chip').forEach((chip) => {
    chip.addEventListener('click', () => applyPreset(chip.dataset.test));
  });

  // Save Settings
  DOM.btnSaveSettings.addEventListener('click', async () => {
    const payload = {
      settings: {
        owner_phone: DOM.settingOwnerPhone.value,
        ai_greeting_hi: DOM.settingGreetingHi.value,
        screening_strictness: DOM.settingStrictness.value,
        retention_days: DOM.settingRetention.value,
      },
    };

    await fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    DOM.settingsModalOverlay.classList.remove('active');
    showToast('Settings saved successfully');
  });
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
  setupEventListeners();
  fetchMetrics();
  fetchCalls();
  fetchSettings();
});
