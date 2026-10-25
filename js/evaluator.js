/**
 * Core Date & Homework Evaluation Logic
 *
 * Rules:
 * 1. Weekly assignments:
 *    - Mon-Thu: Include items due Today and Tomorrow.
 *    - Friday: Ignore Sat/Sun; include items due Friday (Today) and Monday (refDate + 3 days).
 *    - Saturday: Ignore Sat/Sun; include items due Monday (refDate + 2 days).
 *    - Sunday: Ignore Sat/Sun; include items due Monday (refDate + 1 day).
 * 2. Upcoming (dated) assignments:
 *    - Include active items where refDate <= dueDate <= max(nextSchoolDay, refDate + lookaheadDays).
 *    - Past-due items (dueDate < refDate) automatically drop off.
 */

export const WEEKDAYS = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
export const SCHOOL_DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'];
export const SHORT_DAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
export const SHORT_MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

/**
 * Parse a YYYY-MM-DD string into a UTC-noon Date object so timezone offsets never shift the calendar day.
 * @param {string} dateStr YYYY-MM-DD
 * @returns {Date|null}
 */
export function parseIsoDate(dateStr) {
  if (!dateStr || typeof dateStr !== 'string') return null;
  const clean = dateStr.trim().slice(0, 10);
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(clean);
  if (!match) return null;
  const year = Number(match[1]);
  const month = Number(match[2]) - 1;
  const day = Number(match[3]);
  const dt = new Date(Date.UTC(year, month, day, 12, 0, 0));
  if (isNaN(dt.getTime())) return null;
  return dt;
}

/**
 * Format a UTC Date object into YYYY-MM-DD.
 * @param {Date} dt
 * @returns {string}
 */
export function formatIsoDate(dt) {
  const y = dt.getUTCFullYear();
  const m = String(dt.getUTCMonth() + 1).padStart(2, '0');
  const d = String(dt.getUTCDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

/**
 * Add N calendar days to a YYYY-MM-DD string and return YYYY-MM-DD.
 * @param {string} dateStr
 * @param {number} days
 * @returns {string}
 */
export function addDays(dateStr, days) {
  const dt = parseIsoDate(dateStr);
  if (!dt) return dateStr;
  dt.setUTCDate(dt.getUTCDate() + days);
  return formatIsoDate(dt);
}

/**
 * Get today's YYYY-MM-DD in the configured timezone (default America/New_York).
 * @param {string} [timezone='America/New_York']
 * @returns {string}
 */
export function getTodayIso(timezone = 'America/New_York') {
  try {
    const parts = new Intl.DateTimeFormat('en-CA', {
      timeZone: timezone,
      year: 'numeric',
      month: '2-digit',
      day: '2-digit'
    }).formatToParts(new Date());
    const y = parts.find(p => p.type === 'year')?.value;
    const m = parts.find(p => p.type === 'month')?.value;
    const d = parts.find(p => p.type === 'day')?.value;
    if (y && m && d) return `${y}-${m}-${d}`;
  } catch (_) {
    // Fallback to local date
  }
  const now = new Date();
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, '0');
  const d = String(now.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

/**
 * Normalize a weekday string (e.g. "fri", "Friday") to canonical "Monday".."Friday".
 * @param {string} rawDay
 * @returns {string|null}
 */
export function normalizeWeekday(rawDay) {
  if (!rawDay || typeof rawDay !== 'string') return null;
  const clean = rawDay.trim().toLowerCase();
  for (const day of SCHOOL_DAYS) {
    if (day.toLowerCase() === clean || day.slice(0, 3).toLowerCase() === clean.slice(0, 3)) {
      return day;
    }
  }
  return null;
}

/**
 * Compute the active school-day targets and lookahead horizon for a given reference date.
 * @param {string} refDateStr YYYY-MM-DD
 * @param {number} [lookaheadDays=3]
 * @returns {{
 *   refDate: string,
 *   refWeekday: string,
 *   weeklyTargetDates: Array<{ date: string, weekday: string, isToday: boolean }>,
 *   upcomingStartDate: string,
 *   upcomingEndDate: string,
 *   nextSchoolDay: string
 * }}
 */
export function getEvaluationHorizon(refDateStr, lookaheadDays = 3) {
  const dt = parseIsoDate(refDateStr);
  if (!dt) {
    throw new Error(`Invalid reference date: ${refDateStr}`);
  }

  const dow = dt.getUTCDay(); // 0=Sun, 1=Mon, ..., 5=Fri, 6=Sat
  const refWeekday = WEEKDAYS[dow];
  const weeklyTargetDates = [];
  let nextSchoolDay = refDateStr;

  if (dow >= 1 && dow <= 4) {
    // Monday through Thursday: Today + Tomorrow
    const tomorrowStr = addDays(refDateStr, 1);
    const tomorrowDow = (dow + 1) % 7;
    nextSchoolDay = tomorrowStr;
    weeklyTargetDates.push(
      { date: refDateStr, weekday: refWeekday, isToday: true },
      { date: tomorrowStr, weekday: WEEKDAYS[tomorrowDow], isToday: false }
    );
  } else if (dow === 5) {
    // Friday: Friday (Today) + Monday (+3 days)
    const mondayStr = addDays(refDateStr, 3);
    nextSchoolDay = mondayStr;
    weeklyTargetDates.push(
      { date: refDateStr, weekday: 'Friday', isToday: true },
      { date: mondayStr, weekday: 'Monday', isToday: false }
    );
  } else if (dow === 6) {
    // Saturday: only Monday (+2 days)
    const mondayStr = addDays(refDateStr, 2);
    nextSchoolDay = mondayStr;
    weeklyTargetDates.push({ date: mondayStr, weekday: 'Monday', isToday: false });
  } else {
    // Sunday (dow === 0): only Monday (+1 day)
    const mondayStr = addDays(refDateStr, 1);
    nextSchoolDay = mondayStr;
    weeklyTargetDates.push({ date: mondayStr, weekday: 'Monday', isToday: false });
  }

  const plusN = addDays(refDateStr, Math.max(1, Number(lookaheadDays) || 3));
  const upcomingEndDate = plusN > nextSchoolDay ? plusN : nextSchoolDay;

  return {
    refDate: refDateStr,
    refWeekday,
    weeklyTargetDates,
    upcomingStartDate: refDateStr,
    upcomingEndDate,
    nextSchoolDay
  };
}

/**
 * Format a human-friendly due badge relative to refDateStr (e.g. "DUE TODAY", "DUE TOMORROW", "DUE MON", "DUE OCT 29").
 * @param {string} dueDateStr YYYY-MM-DD
 * @param {string} refDateStr YYYY-MM-DD
 * @returns {string}
 */
export function formatDueBadge(dueDateStr, refDateStr) {
  if (dueDateStr === refDateStr) {
    return 'DUE TODAY';
  }
  if (dueDateStr === addDays(refDateStr, 1)) {
    return 'DUE TOMORROW';
  }
  const dueDt = parseIsoDate(dueDateStr);
  const refDt = parseIsoDate(refDateStr);
  if (!dueDt || !refDt) return `DUE ${dueDateStr}`;

  const diffDays = Math.round((dueDt.getTime() - refDt.getTime()) / (1000 * 60 * 60 * 24));
  const shortDay = SHORT_DAYS[dueDt.getUTCDay()].toUpperCase();
  const shortMonth = SHORT_MONTHS[dueDt.getUTCMonth()].toUpperCase();
  const dayNum = dueDt.getUTCDate();

  if (diffDays > 0 && diffDays <= 4) {
    return `DUE ${shortDay}`;
  }
  return `DUE ${shortDay}, ${shortMonth} ${dayNum}`;
}

/**
 * Evaluate all homework rows for a specific target date.
 * @param {Array} items Raw homework items from Google Sheet
 * @param {string} refDateStr YYYY-MM-DD
 * @param {Object} [config] Parsed config.yaml
 * @returns {{
 *   date: string,
 *   weekday: string,
 *   next_school_day: string,
 *   upcoming_lookahead_end: string,
 *   tasks: Array
 * }}
 */
export function evaluateHomeworkForDate(items, refDateStr, config = {}) {
  const lookaheadDays = config?.settings?.upcoming_lookahead_days ?? 3;
  const horizon = getEvaluationHorizon(refDateStr, lookaheadDays);
  const kidsConfig = config?.kids || {};

  const curatedTasks = [];

  for (const item of items || []) {
    if (!item || item.active === false) continue;
    const title = String(item.title || '').trim();
    if (!title) continue;

    const kid = String(item.kid || 'Isaac').trim();
    const cls = String(item.class || '').trim();
    const type = String(item.type || 'upcoming').trim().toLowerCase();
    const kidColor = kidsConfig[kid]?.color || (kid.toLowerCase() === 'asher' ? 'green' : 'blue');
    const formattedTitle = cls ? `[${cls}] ${title}` : title;

    if (type === 'weekly') {
      const targetWeekday = normalizeWeekday(item.due);
      if (!targetWeekday) continue;

      const matchedSlot = horizon.weeklyTargetDates.find(slot => slot.weekday === targetWeekday);
      if (matchedSlot) {
        const dueLabel = formatDueBadge(matchedSlot.date, refDateStr);
        curatedTasks.push({
          id: String(item.id || `hw-${kid}-${cls}-${title}`),
          kid,
          assignee: kid,
          class: cls,
          type: 'weekly',
          title: formattedTitle,
          raw_title: title,
          due: matchedSlot.date,
          due_day: targetWeekday,
          due_label: dueLabel,
          accessory: dueLabel,
          priority: matchedSlot.isToday ? 'high' : 'medium',
          cover_color: kidColor,
          notes: String(item.notes || '').trim()
        });
      }
    } else {
      // 'upcoming' (dated) item
      const dueIso = String(item.due || '').trim().slice(0, 10);
      if (!parseIsoDate(dueIso)) continue;

      if (dueIso >= horizon.upcomingStartDate && dueIso <= horizon.upcomingEndDate) {
        const dueLabel = formatDueBadge(dueIso, refDateStr);
        const isImmediate = dueIso === refDateStr || dueIso === horizon.nextSchoolDay;
        curatedTasks.push({
          id: String(item.id || `hw-${kid}-${cls}-${title}`),
          kid,
          assignee: kid,
          class: cls,
          type: 'upcoming',
          title: formattedTitle,
          raw_title: title,
          due: dueIso,
          due_label: dueLabel,
          accessory: dueLabel,
          priority: isImmediate ? 'high' : 'medium',
          cover_color: kidColor,
          notes: String(item.notes || '').trim()
        });
      }
    }
  }

  // Sort by due date ascending, then by kid order in config, then by class
  const kidOrder = Object.keys(kidsConfig);
  curatedTasks.sort((a, b) => {
    if (a.due !== b.due) return a.due.localeCompare(b.due);
    const kA = kidOrder.indexOf(a.kid);
    const kB = kidOrder.indexOf(b.kid);
    if (kA !== kB) return (kA === -1 ? 99 : kA) - (kB === -1 ? 99 : kB);
    if (a.class !== b.class) return a.class.localeCompare(b.class);
    return a.raw_title.localeCompare(b.raw_title);
  });

  return {
    date: horizon.refDate,
    weekday: horizon.refWeekday,
    next_school_day: horizon.nextSchoolDay,
    upcoming_lookahead_end: horizon.upcomingEndDate,
    tasks: curatedTasks
  };
}

/**
 * Compute smart quick-date chips for the Web UI ("Tomorrow", "Friday", "Monday") relative to today.
 * Avoids duplicate dates (e.g. when Tomorrow IS Friday or Monday).
 * @param {string} todayIso YYYY-MM-DD
 * @returns {Array<{ key: string, label: string, sublabel: string, date: string }>}
 */
export function getQuickDateChips(todayIso) {
  const dt = parseIsoDate(todayIso);
  if (!dt) return [];

  const dow = dt.getUTCDay(); // 0=Sun..6=Sat
  const chips = [];
  const usedDates = new Set();

  const addChip = (key, label, targetDateStr) => {
    if (usedDates.has(targetDateStr)) return;
    usedDates.add(targetDateStr);
    const tDt = parseIsoDate(targetDateStr);
    const sublabel = tDt ? `${SHORT_MONTHS[tDt.getUTCMonth()]} ${tDt.getUTCDate()}` : targetDateStr;
    chips.push({ key, label, sublabel, date: targetDateStr });
  };

  // 1. Tomorrow (if tomorrow is a school day Mon-Fri)
  const tomorrowIso = addDays(todayIso, 1);
  const tomorrowDow = (dow + 1) % 7;
  if (tomorrowDow >= 1 && tomorrowDow <= 5) {
    addChip('tomorrow', `Tomorrow (${SHORT_DAYS[tomorrowDow]})`, tomorrowIso);
  }

  // 2. Upcoming Friday
  let daysUntilFri = (5 - dow + 7) % 7;
  if (daysUntilFri === 0) daysUntilFri = 7;
  const fridayIso = addDays(todayIso, daysUntilFri);
  addChip('friday', 'Friday', fridayIso);

  // 3. Upcoming Monday
  let daysUntilMon = (1 - dow + 7) % 7;
  if (daysUntilMon === 0) daysUntilMon = 7;
  const mondayIso = addDays(todayIso, daysUntilMon);
  addChip('monday', 'Monday', mondayIso);

  // 4. If tomorrow was Fri or Mon (leaving only 2 chips), add Next Tue/Wed for convenience
  if (chips.length < 3) {
    let daysUntilWed = (3 - dow + 7) % 7;
    if (daysUntilWed <= 1) daysUntilWed += 7;
    addChip('wednesday', 'Wednesday', addDays(todayIso, daysUntilWed));
  }

  return chips;
}
