import { loadConfig, STARTER_WEEKLY_ITEMS } from './configLoader.js';
import {
  SCHOOL_DAYS,
  getTodayIso,
  getQuickDateChips,
  formatDueBadge,
  evaluateHomeworkForDate,
  normalizeWeekday
} from './evaluator.js';
import {
  resolveScriptUrl,
  saveScriptUrlOverride,
  loadCachedItems,
  saveCachedItems,
  fetchHomeworkFromSheets,
  syncHomeworkToSheets
} from './sheetsSync.js';

const state = {
  config: null,
  items: [],
  selectedKid: 'Isaac',
  form: {
    className: '',
    type: 'upcoming', // 'upcoming' | 'weekly'
    title: '',
    notes: '',
    dueDate: '',
    dueWeekday: 'Friday'
  },
  editingId: null,
  showExpired: false,
  showSettingsModal: false,
  previewDate: '',
  syncStatus: 'idle', // 'idle' | 'pulling' | 'saving' | 'synced' | 'error' | 'unconfigured'
  syncMessage: '',
  pendingSaveTimer: null,
  isSavingInFlight: false,
  lastPullTimestamp: 0
};

function generateId() {
  return `hw-${Date.now()}-${Math.floor(Math.random() * 10000)}`;
}

function escapeHtml(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function getKidNames() {
  const kids = state.config?.kids ? Object.keys(state.config.kids) : ['Isaac', 'Asher'];
  return kids.length > 0 ? kids : ['Isaac', 'Asher'];
}

function getClassesForKid(kidName) {
  return state.config?.kids?.[kidName]?.classes || [];
}

function getThemeForKid(kidName) {
  return state.config?.kids?.[kidName]?.color || (kidName === 'Asher' ? 'green' : 'blue');
}

function ensureFormDefaults() {
  const classes = getClassesForKid(state.selectedKid);
  if (!state.form.className || !classes.includes(state.form.className)) {
    state.form.className = classes[0] || '';
  }
  const todayIso = getTodayIso(state.config?.settings?.timezone);
  if (!state.previewDate) {
    state.previewDate = todayIso;
  }
  if (!state.form.dueDate) {
    const chips = getQuickDateChips(todayIso);
    state.form.dueDate = chips[0]?.date || todayIso;
  }
}

/**
 * Pull latest rows from Google Sheets (called automatically on open and on window focus).
 */
async function pullFromSheet({ force = false } = {}) {
  // Never overwrite local state while a user edit is waiting to save or currently saving
  if (state.pendingSaveTimer || state.isSavingInFlight) {
    return;
  }

  // Throttle automatic focus pulls to at most once every 3 seconds unless forced
  const now = Date.now();
  if (!force && now - state.lastPullTimestamp < 3000) {
    return;
  }

  const scriptUrl = resolveScriptUrl(state.config);
  if (!scriptUrl) {
    state.syncStatus = 'unconfigured';
    state.syncMessage = 'Connect Sheet';
    renderApp();
    return;
  }

  state.syncStatus = 'pulling';
  state.syncMessage = 'Pulling...';
  renderSyncPillOnly();

  const sheetName = state.config?.google_sheets?.sheet_name || 'Homework';
  const result = await fetchHomeworkFromSheets(scriptUrl, null, sheetName);
  state.lastPullTimestamp = Date.now();

  // Re-check that user didn't start editing while the GET request was in flight
  if (state.pendingSaveTimer || state.isSavingInFlight) {
    return;
  }

  if (result.success) {
    state.items = result.items;
    saveCachedItems(state.items);
    state.syncStatus = 'synced';
    state.syncMessage = '✓ Synced';
  } else {
    state.syncStatus = 'error';
    state.syncMessage = '⚠ Sync Error';
    console.warn('Sheet pull failed:', result.error);
  }
  renderApp();
}

/**
 * Debounced background push to Google Sheets after any UI edit.
 */
function schedulePushToSheet() {
  saveCachedItems(state.items);

  const scriptUrl = resolveScriptUrl(state.config);
  if (!scriptUrl) {
    state.syncStatus = 'unconfigured';
    state.syncMessage = 'Connect Sheet';
    renderSyncPillOnly();
    return;
  }

  state.syncStatus = 'saving';
  state.syncMessage = 'Saving...';
  renderSyncPillOnly();

  if (state.pendingSaveTimer) {
    clearTimeout(state.pendingSaveTimer);
  }

  state.pendingSaveTimer = setTimeout(async () => {
    state.pendingSaveTimer = null;
    state.isSavingInFlight = true;
    const sheetName = state.config?.google_sheets?.sheet_name || 'Homework';
    const snapshot = [...state.items];

    const res = await syncHomeworkToSheets(scriptUrl, snapshot, null, sheetName);
    state.isSavingInFlight = false;

    if (res.success) {
      state.syncStatus = 'synced';
      state.syncMessage = '✓ Synced';
    } else {
      state.syncStatus = 'error';
      state.syncMessage = '⚠ Save Failed';
      console.error('Failed to save to Google Sheet:', res.error);
    }
    renderSyncPillOnly();
  }, 450);
}

function renderSyncPillOnly() {
  const pill = document.getElementById('sync-status-pill');
  if (!pill) return;
  pill.className = `sync-pill ${state.syncStatus}`;
  pill.textContent = state.syncMessage || '✓ Synced';
}

function renderApp() {
  const container = document.getElementById('app');
  if (!container || !state.config) return;

  ensureFormDefaults();
  const theme = getThemeForKid(state.selectedKid);
  document.documentElement.setAttribute('data-theme', theme);

  const todayIso = getTodayIso(state.config?.settings?.timezone);
  const quickChips = getQuickDateChips(todayIso);
  const kidNames = getKidNames();
  const kidClasses = getClassesForKid(state.selectedKid);

  // Partition items for the selected kid
  const kidItems = state.items.filter(
    item => String(item.kid || '').toLowerCase() === state.selectedKid.toLowerCase()
  );

  const activeUpcoming = kidItems
    .filter(i => i.type !== 'weekly' && (!i.due || i.due >= todayIso))
    .sort((a, b) => String(a.due || '9999').localeCompare(String(b.due || '9999')));

  const expiredUpcoming = kidItems
    .filter(i => i.type !== 'weekly' && i.due && i.due < todayIso)
    .sort((a, b) => String(b.due || '').localeCompare(String(a.due || '')));

  const weeklyItems = kidItems
    .filter(i => i.type === 'weekly')
    .sort((a, b) => {
      const idxA = SCHOOL_DAYS.indexOf(normalizeWeekday(a.due) || 'Monday');
      const idxB = SCHOOL_DAYS.indexOf(normalizeWeekday(b.due) || 'Monday');
      if (idxA !== idxB) return idxA - idxB;
      return String(a.class || '').localeCompare(String(b.class || ''));
    });

  // Screamsheet preview evaluation
  const previewEval = evaluateHomeworkForDate(state.items, state.previewDate || todayIso, state.config);
  const scriptUrlConfigured = Boolean(resolveScriptUrl(state.config));

  container.innerHTML = `
    <div class="app-shell">
      <!-- Top Bar -->
      <header class="top-bar">
        <div class="kid-switcher">
          ${kidNames.map(kid => {
            const count = state.items.filter(
              i => String(i.kid).toLowerCase() === kid.toLowerCase() &&
                   i.active !== false &&
                   (i.type === 'weekly' || !i.due || i.due >= todayIso)
            ).length;
            return `
              <button type="button" class="kid-tab ${state.selectedKid === kid ? 'active' : ''}" data-action="select-kid" data-kid="${escapeHtml(kid)}">
                <span>${escapeHtml(kid)}</span>
                <span class="kid-count-badge">${count}</span>
              </button>
            `;
          }).join('')}
        </div>

        <div class="sync-controls">
          <span id="sync-status-pill" class="sync-pill ${state.syncStatus}" data-action="${state.syncStatus === 'unconfigured' || state.syncStatus === 'error' ? 'open-settings' : ''}">
            ${escapeHtml(state.syncMessage || '✓ Synced')}
          </span>
          <button type="button" class="icon-btn" title="Refresh from Google Sheet" data-action="manual-refresh">↻</button>
          <button type="button" class="icon-btn" title="Google Sheet Settings" data-action="open-settings">⚙️</button>
        </div>
      </header>

      ${!scriptUrlConfigured ? `
        <div class="setup-banner">
          <div>
            <strong>Google Sheet not linked yet.</strong> Paste your Apps Script URL in Settings (or <code>config.yaml</code>) to enable live sync.
          </div>
          <button type="button" data-action="open-settings">Connect Sheet</button>
        </div>
      ` : ''}

      <!-- Quick Add Card -->
      <section class="quick-add-card">
        <div class="quick-add-header">
          <span class="quick-add-title">+ Add ${escapeHtml(state.selectedKid)} Homework</span>
          <div class="type-toggle">
            <button type="button" class="type-btn ${state.form.type === 'upcoming' ? 'active' : ''}" data-action="select-type" data-type="upcoming">
              📌 Upcoming
            </button>
            <button type="button" class="type-btn ${state.form.type === 'weekly' ? 'active' : ''}" data-action="select-type" data-type="weekly">
              🔁 Weekly
            </button>
          </div>
        </div>

        <!-- 1-Tap Class Pill Bar -->
        <div class="class-pill-bar">
          ${kidClasses.map(cls => `
            <button type="button" class="class-pill ${state.form.className === cls ? 'selected' : ''}" data-action="select-class" data-class="${escapeHtml(cls)}">
              ${escapeHtml(cls)}
            </button>
          `).join('')}
        </div>

        <!-- Assignment Title & Optional Notes -->
        <form id="quick-add-form">
          <div class="input-row">
            <input
              type="text"
              id="add-title-input"
              class="title-input"
              placeholder="${state.form.type === 'weekly' ? 'Weekly habit (e.g. Spelling Workbook)...' : 'What assignment or test is coming up?'}"
              value="${escapeHtml(state.form.title)}"
              autocomplete="off"
              required
            />
            <input
              type="text"
              id="add-notes-input"
              class="notes-input"
              placeholder="Optional notes (e.g. Pages 12-15, chapters 1-3)..."
              value="${escapeHtml(state.form.notes)}"
              autocomplete="off"
            />
          </div>

          <div class="due-row">
            ${state.form.type === 'upcoming' ? `
              <div class="due-chips">
                ${quickChips.map(chip => `
                  <button type="button" class="due-chip ${state.form.dueDate === chip.date ? 'selected' : ''}" data-action="select-due-date" data-date="${chip.date}">
                    <span>${escapeHtml(chip.label)}</span>
                    <span class="chip-sub">${escapeHtml(chip.sublabel)}</span>
                  </button>
                `).join('')}
                <input
                  type="date"
                  id="custom-date-picker"
                  class="date-picker-input ${!quickChips.some(c => c.date === state.form.dueDate) ? 'selected' : ''}"
                  value="${escapeHtml(state.form.dueDate)}"
                  title="Pick any calendar date"
                />
              </div>
            ` : `
              <div class="due-chips">
                ${SCHOOL_DAYS.map(day => `
                  <button type="button" class="due-chip ${state.form.dueWeekday === day ? 'selected' : ''}" data-action="select-due-weekday" data-weekday="${day}">
                    <span>Every ${day.slice(0, 3)}</span>
                  </button>
                `).join('')}
              </div>
            `}

            <button type="submit" class="btn-submit-add">Add</button>
          </div>
        </form>
      </section>

      <!-- Section 1: Upcoming (Dated) -->
      <section class="homework-section">
        <div class="section-header">
          <div class="section-title-group">
            <h2 class="section-title">📌 Upcoming</h2>
            <span class="section-subtitle">Shows on Screamsheet 3 days in advance</span>
          </div>
          <span class="section-count">${activeUpcoming.length}</span>
        </div>

        ${activeUpcoming.length === 0 ? `
          <div class="empty-state">No upcoming dated assignments for ${escapeHtml(state.selectedKid)}.</div>
        ` : `
          <div class="task-list">
            ${activeUpcoming.map(item => renderTaskRow(item, todayIso, kidClasses)).join('')}
          </div>
        `}

        ${expiredUpcoming.length > 0 ? `
          <div class="collapsible-bar">
            <button type="button" class="link-btn" data-action="toggle-expired">
              ${state.showExpired ? '▾ Hide' : '▸ Show'} ${expiredUpcoming.length} past-due / completed item(s)
            </button>
            ${state.showExpired ? `
              <button type="button" class="link-btn" style="color: var(--danger);" data-action="clear-expired">
                Purge Past Items
              </button>
            ` : ''}
          </div>
          ${state.showExpired ? `
            <div class="task-list" style="margin-top: 8px; opacity: 0.72;">
              ${expiredUpcoming.map(item => renderTaskRow(item, todayIso, kidClasses, true)).join('')}
            </div>
          ` : ''}
        ` : ''}
      </section>

      <!-- Section 2: Weekly (Recurring) -->
      <section class="homework-section">
        <div class="section-header">
          <div class="section-title-group">
            <h2 class="section-title">🔁 Weekly</h2>
            <span class="section-subtitle">Automatic weekly rhythm (Mon–Fri)</span>
          </div>
          <span class="section-count">${weeklyItems.length}</span>
        </div>

        ${weeklyItems.length === 0 ? `
          <div class="empty-state">
            <p style="margin-bottom: 8px;">No weekly assignments configured for ${escapeHtml(state.selectedKid)} yet.</p>
            <button type="button" class="btn-secondary" data-action="seed-starter">Load Starter Weekly Schedule</button>
          </div>
        ` : `
          <div class="task-list">
            ${weeklyItems.map(item => renderTaskRow(item, todayIso, kidClasses)).join('')}
          </div>
        `}
      </section>

      <!-- Morning Screamsheet Radar Preview -->
      <section class="preview-card">
        <div class="preview-header">
          <span class="preview-title">📰 Screamsheet Output Preview (${escapeHtml(previewEval.weekday)})</span>
          <input
            type="date"
            id="preview-date-picker"
            class="preview-date-input"
            value="${escapeHtml(state.previewDate || todayIso)}"
          />
        </div>
        <div class="preview-list">
          ${previewEval.tasks.length === 0 ? `
            <div style="font-size: 12.5px; color: #94a3b8; padding: 6px 0;">
              Nothing due for this morning briefing window.
            </div>
          ` : previewEval.tasks.map(t => `
            <div class="preview-item">
              <div style="display: flex; align-items: center; gap: 8px; min-width: 0;">
                <span class="preview-kid-tag ${escapeHtml(t.cover_color)}">${escapeHtml(t.kid)}</span>
                <span style="font-weight: 600; overflow: hidden; text-overflow: ellipsis;">${escapeHtml(t.title)}</span>
              </div>
              <span class="preview-due-tag">${escapeHtml(t.due_label)}</span>
            </div>
          `).join('')}
        </div>
      </section>

      ${state.showSettingsModal ? renderSettingsModal() : ''}
    </div>
  `;
}

function renderTaskRow(item, todayIso, kidClasses, isExpired = false) {
  if (state.editingId === item.id) {
    return `
      <div class="task-row" data-id="${escapeHtml(item.id)}">
        <div class="inline-edit-box">
          <div class="inline-edit-grid">
            <select id="edit-class-${escapeHtml(item.id)}">
              ${kidClasses.map(cls => `
                <option value="${escapeHtml(cls)}" ${item.class === cls ? 'selected' : ''}>${escapeHtml(cls)}</option>
              `).join('')}
              ${item.class && !kidClasses.includes(item.class) ? `
                <option value="${escapeHtml(item.class)}" selected>${escapeHtml(item.class)}</option>
              ` : ''}
            </select>

            ${item.type === 'weekly' ? `
              <select id="edit-due-${escapeHtml(item.id)}">
                ${SCHOOL_DAYS.map(day => `
                  <option value="${day}" ${normalizeWeekday(item.due) === day ? 'selected' : ''}>Every ${day}</option>
                `).join('')}
              </select>
            ` : `
              <input type="date" id="edit-due-${escapeHtml(item.id)}" value="${escapeHtml(String(item.due || '').slice(0, 10))}" />
            `}
          </div>
          <input type="text" id="edit-title-${escapeHtml(item.id)}" value="${escapeHtml(item.title)}" placeholder="Assignment title" />
          <input type="text" id="edit-notes-${escapeHtml(item.id)}" value="${escapeHtml(item.notes || '')}" placeholder="Optional notes" />
          <div class="inline-edit-actions">
            <button type="button" class="btn-cancel-inline" data-action="cancel-edit">Cancel</button>
            <button type="button" class="btn-save-inline" data-action="save-edit" data-id="${escapeHtml(item.id)}">Save</button>
          </div>
        </div>
      </div>
    `;
  }

  let dueBadgeText = '';
  let dueClass = '';
  if (item.type === 'weekly') {
    dueBadgeText = `Every ${normalizeWeekday(item.due) || item.due}`;
  } else {
    dueBadgeText = isExpired ? `Past (${item.due})` : formatDueBadge(item.due, todayIso);
    if (item.due === todayIso) dueClass = 'today';
    else if (!isExpired) dueClass = 'urgent';
  }

  const isActive = item.active !== false;

  return `
    <div class="task-row ${!isActive ? 'paused' : ''}" data-id="${escapeHtml(item.id)}">
      <div class="task-main" data-action="start-edit" data-id="${escapeHtml(item.id)}">
        <div class="task-top-line">
          <span class="task-class-badge">${escapeHtml(item.class || 'General')}</span>
          <span class="task-due-badge ${dueClass}">${escapeHtml(dueBadgeText)}</span>
        </div>
        <div class="task-title">${escapeHtml(item.title)}</div>
        ${item.notes ? `<div class="task-notes">${escapeHtml(item.notes)}</div>` : ''}
      </div>

      <div class="task-actions">
        ${item.type === 'weekly' ? `
          <button
            type="button"
            class="toggle-active-btn ${isActive ? 'is-active' : ''}"
            data-action="toggle-active"
            data-id="${escapeHtml(item.id)}"
            title="Pause or resume this weekly item"
          >
            ${isActive ? 'Active' : 'Paused'}
          </button>
        ` : ''}
        <button type="button" class="btn-edit-task" title="Edit" data-action="start-edit" data-id="${escapeHtml(item.id)}">✎</button>
        <button type="button" class="btn-delete-task" title="Delete" data-action="delete-item" data-id="${escapeHtml(item.id)}">✕</button>
      </div>
    </div>
  `;
}

function renderSettingsModal() {
  const currentUrl = resolveScriptUrl(state.config);
  return `
    <div class="modal-backdrop" data-action="close-settings-backdrop">
      <div class="modal-card">
        <h2>Google Sheet Connection</h2>
        <p>
          Paste your deployed Google Apps Script Web App URL (ending in <code>/exec</code>).
          Changes automatically sync both ways whenever you open the app or edit items.
        </p>
        <input
          type="url"
          id="settings-script-url-input"
          placeholder="https://script.google.com/macros/s/.../exec"
          value="${escapeHtml(currentUrl)}"
        />
        <div class="modal-actions">
          <button type="button" class="btn-secondary" data-action="seed-starter">
            Seed Starter Weekly Items
          </button>
          <div style="display: flex; gap: 8px;">
            <button type="button" class="btn-cancel-inline" data-action="close-settings">Cancel</button>
            <button type="button" class="btn-save-inline" data-action="save-settings">Save URL</button>
          </div>
        </div>
      </div>
    </div>
  `;
}

function bindEvents() {
  const container = document.getElementById('app');
  if (!container) return;

  // Input listeners to preserve draft text across button clicks
  container.addEventListener('input', (e) => {
    if (e.target.id === 'add-title-input') {
      state.form.title = e.target.value;
    } else if (e.target.id === 'add-notes-input') {
      state.form.notes = e.target.value;
    } else if (e.target.id === 'custom-date-picker') {
      state.form.dueDate = e.target.value;
      renderApp();
    } else if (e.target.id === 'preview-date-picker') {
      state.previewDate = e.target.value;
      renderApp();
    }
  });

  // Form submit for Quick-Add
  container.addEventListener('submit', (e) => {
    if (e.target.id === 'quick-add-form') {
      e.preventDefault();
      const title = state.form.title.trim();
      if (!title) return;

      const newItem = {
        id: generateId(),
        kid: state.selectedKid,
        class: state.form.className || getClassesForKid(state.selectedKid)[0] || 'General',
        type: state.form.type,
        title,
        due: state.form.type === 'weekly' ? state.form.dueWeekday : state.form.dueDate,
        notes: state.form.notes.trim(),
        active: true,
        updatedAt: new Date().toISOString()
      };

      state.items.push(newItem);
      state.form.title = '';
      state.form.notes = '';
      renderApp();
      schedulePushToSheet();
    }
  });

  // Delegated click handlers
  container.addEventListener('click', (e) => {
    const actionEl = e.target.closest('[data-action]');
    if (!actionEl) return;

    const action = actionEl.dataset.action;

    if (action === 'select-kid') {
      state.selectedKid = actionEl.dataset.kid;
      state.editingId = null;
      ensureFormDefaults();
      renderApp();
      return;
    }

    if (action === 'select-type') {
      state.form.type = actionEl.dataset.type;
      renderApp();
      return;
    }

    if (action === 'select-class') {
      state.form.className = actionEl.dataset.class;
      renderApp();
      return;
    }

    if (action === 'select-due-date') {
      state.form.dueDate = actionEl.dataset.date;
      renderApp();
      return;
    }

    if (action === 'select-due-weekday') {
      state.form.dueWeekday = actionEl.dataset.weekday;
      renderApp();
      return;
    }

    if (action === 'delete-item') {
      const id = actionEl.dataset.id;
      state.items = state.items.filter(i => i.id !== id);
      if (state.editingId === id) state.editingId = null;
      renderApp();
      schedulePushToSheet();
      return;
    }

    if (action === 'toggle-active') {
      const id = actionEl.dataset.id;
      const item = state.items.find(i => i.id === id);
      if (item) {
        item.active = item.active === false ? true : false;
        item.updatedAt = new Date().toISOString();
        renderApp();
        schedulePushToSheet();
      }
      return;
    }

    if (action === 'start-edit') {
      const id = actionEl.dataset.id;
      state.editingId = id;
      renderApp();
      return;
    }

    if (action === 'cancel-edit') {
      state.editingId = null;
      renderApp();
      return;
    }

    if (action === 'save-edit') {
      const id = actionEl.dataset.id;
      const item = state.items.find(i => i.id === id);
      if (item) {
        const clsEl = document.getElementById(`edit-class-${id}`);
        const dueEl = document.getElementById(`edit-due-${id}`);
        const titleEl = document.getElementById(`edit-title-${id}`);
        const notesEl = document.getElementById(`edit-notes-${id}`);

        if (clsEl) item.class = clsEl.value.trim();
        if (dueEl) item.due = dueEl.value.trim();
        if (titleEl && titleEl.value.trim()) item.title = titleEl.value.trim();
        if (notesEl) item.notes = notesEl.value.trim();
        item.updatedAt = new Date().toISOString();
      }
      state.editingId = null;
      renderApp();
      schedulePushToSheet();
      return;
    }

    if (action === 'toggle-expired') {
      state.showExpired = !state.showExpired;
      renderApp();
      return;
    }

    if (action === 'clear-expired') {
      const todayIso = getTodayIso(state.config?.settings?.timezone);
      state.items = state.items.filter(
        i => !(String(i.kid).toLowerCase() === state.selectedKid.toLowerCase() &&
               i.type !== 'weekly' &&
               i.due &&
               i.due < todayIso)
      );
      state.showExpired = false;
      renderApp();
      schedulePushToSheet();
      return;
    }

    if (action === 'manual-refresh') {
      pullFromSheet({ force: true });
      return;
    }

    if (action === 'open-settings') {
      state.showSettingsModal = true;
      renderApp();
      return;
    }

    if (action === 'close-settings' || (action === 'close-settings-backdrop' && e.target === actionEl)) {
      state.showSettingsModal = false;
      renderApp();
      return;
    }

    if (action === 'save-settings') {
      const input = document.getElementById('settings-script-url-input');
      if (input) {
        saveScriptUrlOverride(input.value);
      }
      state.showSettingsModal = false;
      renderApp();
      pullFromSheet({ force: true });
      return;
    }

    if (action === 'seed-starter') {
      const existingTitles = new Set(state.items.map(i => `${i.kid}|${i.class}|${i.title}`.toLowerCase()));
      for (const seed of STARTER_WEEKLY_ITEMS) {
        const key = `${seed.kid}|${seed.class}|${seed.title}`.toLowerCase();
        if (!existingTitles.has(key)) {
          state.items.push({ ...seed, updatedAt: new Date().toISOString() });
        }
      }
      state.showSettingsModal = false;
      renderApp();
      schedulePushToSheet();
      return;
    }
  });
}

document.addEventListener('DOMContentLoaded', async () => {
  state.items = loadCachedItems();
  state.config = await loadConfig('config.yaml');
  const kids = getKidNames();
  state.selectedKid = kids[0] || 'Isaac';
  ensureFormDefaults();

  renderApp();
  bindEvents();

  // Initial pull from Google Sheets
  await pullFromSheet({ force: true });

  // Continuous Sync: Auto-pull whenever window/tab regains focus
  window.addEventListener('focus', () => {
    pullFromSheet({ force: false });
  });

  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') {
      pullFromSheet({ force: false });
    }
  });
});
