import jsyaml from 'js-yaml';

export const DEFAULT_CONFIG = {
  google_sheets: {
    sheet_name: 'Homework',
    script_url: ''
  },
  settings: {
    upcoming_lookahead_days: 3,
    timezone: 'America/New_York'
  },
  kids: {
    Isaac: {
      color: 'blue',
      classes: [
        'Art History',
        'English Language',
        'English Literature',
        'French',
        'History',
        'Latin',
        'Math',
        'Math Competition',
        'Science'
      ]
    },
    Asher: {
      color: 'green',
      classes: [
        'Art History',
        'English Language',
        'French',
        'Math',
        'Piano',
        'Science'
      ]
    }
  }
};

/**
 * Starter weekly homework migrated from workspace/homework.yaml
 * so the sheet can be populated with 1 click once connected.
 */
export const STARTER_WEEKLY_ITEMS = [
  {
    id: 'hw-seed-isaac-1',
    kid: 'Isaac',
    class: 'Art History',
    type: 'weekly',
    title: 'Google Classroom',
    due: 'Monday',
    notes: '',
    active: true
  },
  {
    id: 'hw-seed-isaac-2',
    kid: 'Isaac',
    class: 'English Language',
    type: 'weekly',
    title: 'Spelling Test',
    due: 'Wednesday',
    notes: '',
    active: true
  },
  {
    id: 'hw-seed-isaac-3',
    kid: 'Isaac',
    class: 'English Language',
    type: 'weekly',
    title: 'Trad Spelling',
    due: 'Wednesday',
    notes: '',
    active: true
  },
  {
    id: 'hw-seed-isaac-4',
    kid: 'Isaac',
    class: 'Math Competition',
    type: 'weekly',
    title: 'Work Packet 1 Hour!',
    due: 'Thursday',
    notes: '',
    active: true
  },
  {
    id: 'hw-seed-asher-1',
    kid: 'Asher',
    class: 'Piano',
    type: 'weekly',
    title: 'Hand in Piano log',
    due: 'Monday',
    notes: '',
    active: true
  },
  {
    id: 'hw-seed-asher-2',
    kid: 'Asher',
    class: 'Math',
    type: 'weekly',
    title: 'Beast Academy Book',
    due: 'Tuesday',
    notes: '',
    active: true
  },
  {
    id: 'hw-seed-asher-3',
    kid: 'Asher',
    class: 'French',
    type: 'weekly',
    title: "Watch moi, c'est twice",
    due: 'Tuesday',
    notes: '',
    active: true
  },
  {
    id: 'hw-seed-asher-4',
    kid: 'Asher',
    class: 'French',
    type: 'weekly',
    title: 'Homework Packet',
    due: 'Tuesday',
    notes: '',
    active: true
  },
  {
    id: 'hw-seed-asher-5',
    kid: 'Asher',
    class: 'English Language',
    type: 'weekly',
    title: 'Spelling Test',
    due: 'Friday',
    notes: '',
    active: true
  },
  {
    id: 'hw-seed-asher-6',
    kid: 'Asher',
    class: 'English Language',
    type: 'weekly',
    title: 'Workbook Pages',
    due: 'Friday',
    notes: '',
    active: true
  }
];

export function getYamlParser() {
  if (typeof jsyaml !== 'undefined' && jsyaml) {
    if (typeof jsyaml.load === 'function') return jsyaml;
    if (jsyaml.default && typeof jsyaml.default.load === 'function') return jsyaml.default;
  }
  if (typeof window !== 'undefined' && window.jsyaml && typeof window.jsyaml.load === 'function') {
    return window.jsyaml;
  }
  return null;
}

export function parseConfigYaml(yamlString) {
  const parser = getYamlParser();
  if (!parser) {
    throw new Error('YAML parser not available');
  }
  const parsed = parser.load(yamlString);
  if (!parsed || !parsed.kids || typeof parsed.kids !== 'object') {
    throw new Error('Invalid config.yaml schema: missing "kids" section');
  }
  return {
    google_sheets: {
      ...DEFAULT_CONFIG.google_sheets,
      ...(parsed.google_sheets || {})
    },
    settings: {
      ...DEFAULT_CONFIG.settings,
      ...(parsed.settings || {})
    },
    kids: parsed.kids
  };
}

export async function loadConfig(configPath = 'config.yaml', fetchFn = null) {
  const performFetch = fetchFn || (typeof fetch !== 'undefined' ? fetch.bind(globalThis) : null);

  if (!performFetch) {
    return DEFAULT_CONFIG;
  }

  try {
    const response = await performFetch(configPath, { cache: 'no-store' });
    if (!response || !response.ok) {
      throw new Error(`Failed to fetch config file: status ${response?.status}`);
    }
    const text = await response.text();
    return parseConfigYaml(text);
  } catch (error) {
    console.warn('Error loading or parsing config.yaml. Falling back to default configuration:', error.message);
    return DEFAULT_CONFIG;
  }
}
