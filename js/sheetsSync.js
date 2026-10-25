/**
 * Google Sheets Sync Client for Homework Tracker
 * Uses text/plain POST payloads to avoid CORS preflight issues with Google Apps Script.
 */

const STORAGE_URL_KEY = 'homework_tracker_script_url';
const STORAGE_CACHE_KEY = 'homework_tracker_items_cache';

/**
 * Resolve the active Google Apps Script URL (checks localStorage override first, then config.yaml).
 * @param {Object} config Parsed config.yaml
 * @returns {string}
 */
export function resolveScriptUrl(config) {
  if (typeof localStorage !== 'undefined') {
    const saved = localStorage.getItem(STORAGE_URL_KEY);
    if (saved && saved.trim()) {
      return saved.trim();
    }
  }
  return String(config?.google_sheets?.script_url || '').trim();
}

export function saveScriptUrlOverride(url) {
  if (typeof localStorage !== 'undefined') {
    if (url && url.trim()) {
      localStorage.setItem(STORAGE_URL_KEY, url.trim());
    } else {
      localStorage.removeItem(STORAGE_URL_KEY);
    }
  }
}

export function loadCachedItems() {
  if (typeof localStorage === 'undefined') return [];
  try {
    const raw = localStorage.getItem(STORAGE_CACHE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch (_) {
    return [];
  }
}

export function saveCachedItems(items) {
  if (typeof localStorage === 'undefined') return;
  try {
    localStorage.setItem(STORAGE_CACHE_KEY, JSON.stringify(items || []));
  } catch (_) {
    // Ignore quota errors
  }
}

/**
 * Fetch all homework rows from the Google Apps Script Web App.
 * @param {string} webAppUrl
 * @param {Function} [fetchFn]
 * @param {string} [sheetName='Homework']
 * @returns {Promise<{success: boolean, items: Array, error?: string}>}
 */
export async function fetchHomeworkFromSheets(webAppUrl, fetchFn = null, sheetName = 'Homework') {
  const customFetch = fetchFn || (typeof fetch !== 'undefined' ? fetch.bind(globalThis) : null);

  if (!webAppUrl || typeof webAppUrl !== 'string' || !webAppUrl.trim()) {
    return { success: false, error: 'Google Apps Script URL not configured', items: [] };
  }
  if (!customFetch) {
    return { success: false, error: 'Fetch API not available', items: [] };
  }

  try {
    let targetUrl = webAppUrl.trim();
    if (sheetName && sheetName.trim()) {
      const sep = targetUrl.includes('?') ? '&' : '?';
      targetUrl += `${sep}sheet=${encodeURIComponent(sheetName.trim())}&_t=${Date.now()}`;
    }

    const response = await customFetch(targetUrl, {
      method: 'GET',
      redirect: 'follow'
    });

    if (!response.ok) {
      return { success: false, error: `HTTP ${response.status}: ${response.statusText}`, items: [] };
    }

    const data = await response.json();
    if (data && data.status === 'error') {
      return { success: false, error: data.message || 'Apps Script error', items: [] };
    }

    let items = [];
    if (Array.isArray(data)) {
      items = data;
    } else if (data && Array.isArray(data.items)) {
      items = data.items;
    } else if (data && Array.isArray(data.data)) {
      items = data.data;
    }

    return { success: true, items };
  } catch (err) {
    return { success: false, error: err.message || 'Network error', items: [] };
  }
}

/**
 * Save homework rows to the Google Apps Script Web App via HTTP POST.
 * @param {string} webAppUrl
 * @param {Array} items
 * @param {Function} [fetchFn]
 * @param {string} [sheetName='Homework']
 * @returns {Promise<{success: boolean, count?: number, error?: string}>}
 */
export async function syncHomeworkToSheets(webAppUrl, items, fetchFn = null, sheetName = 'Homework') {
  const customFetch = fetchFn || (typeof fetch !== 'undefined' ? fetch.bind(globalThis) : null);

  if (!webAppUrl || typeof webAppUrl !== 'string' || !webAppUrl.trim()) {
    return { success: false, error: 'Google Apps Script URL not configured' };
  }
  if (!customFetch) {
    return { success: false, error: 'Fetch API not available' };
  }

  try {
    let targetUrl = webAppUrl.trim();
    if (sheetName && sheetName.trim()) {
      const sep = targetUrl.includes('?') ? '&' : '?';
      targetUrl += `${sep}sheet=${encodeURIComponent(sheetName.trim())}`;
    }

    const response = await customFetch(targetUrl, {
      method: 'POST',
      body: JSON.stringify(items || []),
      headers: {
        'Content-Type': 'text/plain;charset=utf-8'
      },
      redirect: 'follow'
    });

    if (!response.ok) {
      return { success: false, error: `HTTP ${response.status}: ${response.statusText}` };
    }

    const data = await response.json();
    if (data && data.status === 'error') {
      return { success: false, error: data.message || 'Apps Script write error' };
    }

    return { success: true, count: data?.count ?? (items ? items.length : 0) };
  } catch (err) {
    return { success: false, error: err.message || 'Network error' };
  }
}
