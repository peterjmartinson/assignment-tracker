import fs from 'node:fs';
import path from 'node:path';
import { parseConfigYaml, DEFAULT_CONFIG } from '../js/configLoader.js';
import { fetchHomeworkFromSheets } from '../js/sheetsSync.js';
import { evaluateHomeworkForDate, getTodayIso } from '../js/evaluator.js';

function loadServerConfig() {
  try {
    const configPath = path.join(process.cwd(), 'config.yaml');
    if (fs.existsSync(configPath)) {
      const raw = fs.readFileSync(configPath, 'utf8');
      return parseConfigYaml(raw);
    }
  } catch (err) {
    console.warn('Warning: Could not read config.yaml on server:', err.message);
  }
  return DEFAULT_CONFIG;
}

/**
 * Vercel Serverless Function: GET /api/homework?date=YYYY-MM-DD
 *
 * Evaluates Weekly (Today + Tomorrow / Fri->Mon / Sat,Sun->Mon) and
 * Upcoming (3-day lookahead, auto-expiring after due date) homework from Google Sheets.
 */
export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }

  try {
    const config = loadServerConfig();
    const timezone = config?.settings?.timezone || 'America/New_York';
    const targetDate = (req.query?.date && String(req.query.date).trim()) || getTodayIso(timezone);
    const scriptUrl =
      (req.query?.script_url && String(req.query.script_url).trim()) ||
      process.env.GOOGLE_SCRIPT_URL ||
      config?.google_sheets?.script_url ||
      '';
    const sheetName = config?.google_sheets?.sheet_name || 'Homework';

    if (!scriptUrl) {
      return res.status(400).json({
        status: 'error',
        message: 'Google Apps Script URL is not configured in config.yaml or GOOGLE_SCRIPT_URL env var.',
        date: targetDate,
        tasks: []
      });
    }

    const sheetResult = await fetchHomeworkFromSheets(scriptUrl, fetch, sheetName);
    if (!sheetResult.success) {
      return res.status(502).json({
        status: 'error',
        message: `Failed to fetch homework from Google Sheet: ${sheetResult.error}`,
        date: targetDate,
        tasks: []
      });
    }

    const evaluated = evaluateHomeworkForDate(sheetResult.items, targetDate, config);
    return res.status(200).json({
      status: 'success',
      ...evaluated
    });
  } catch (err) {
    return res.status(500).json({
      status: 'error',
      message: err.message || 'Internal server error',
      tasks: []
    });
  }
}
