/**
 * Google Apps Script Web App Backend for Homework Tracker
 *
 * Setup Instructions:
 * 1. Open your Google Sheet (https://sheets.google.com).
 * 2. Go to Extensions > Apps Script.
 * 3. Delete any starter code and paste this entire file into Code.gs.
 * 4. Click Save (Ctrl+S).
 * 5. Click Deploy > New deployment > Select type: "Web app".
 * 6. Set "Execute as": Me, and "Who has access": Anyone.
 * 7. Click Deploy, authorize permissions, and copy the Web App URL.
 */

var DEFAULT_SHEET_NAME = 'Homework';
var HEADERS = ['ID', 'Kid', 'Class', 'Type', 'Title', 'Due', 'Notes', 'Active', 'UpdatedAt'];

function getTargetSheet(e) {
  var spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
  var sheetName = DEFAULT_SHEET_NAME;

  if (e && e.parameter) {
    if (e.parameter.sheet) {
      sheetName = e.parameter.sheet;
    } else if (e.parameter.sheetName) {
      sheetName = e.parameter.sheetName;
    }
  }

  var sheet = spreadsheet.getSheetByName(sheetName);
  if (!sheet) {
    sheet = spreadsheet.insertSheet(sheetName);
    sheet.appendRow(HEADERS);
    sheet.getRange(1, 1, 1, HEADERS.length).setFontWeight('bold');
    sheet.setFrozenRows(1);
  }
  return sheet;
}

/**
 * Formats a cell value from the Due column into either a Weekday name ("Monday".."Friday")
 * or a normalized "YYYY-MM-DD" date string if Google Sheets converted it to a Date object.
 */
function normalizeDueValue(rawVal, timezone) {
  if (rawVal === null || rawVal === undefined || rawVal === '') {
    return '';
  }
  if (Object.prototype.toString.call(rawVal) === '[object Date]' && !isNaN(rawVal.getTime())) {
    return Utilities.formatDate(rawVal, timezone || Session.getScriptTimeZone() || 'America/New_York', 'yyyy-MM-dd');
  }
  return String(rawVal).trim();
}

function parseActiveValue(rawVal) {
  if (rawVal === null || rawVal === undefined || rawVal === '') {
    return true;
  }
  if (typeof rawVal === 'boolean') {
    return rawVal;
  }
  var str = String(rawVal).trim().toLowerCase();
  if (str === 'false' || str === '0' || str === 'no' || str === 'paused') {
    return false;
  }
  return true;
}

function generateRowId(index) {
  return 'hw-' + new Date().getTime() + '-' + index + '-' + Math.floor(Math.random() * 10000);
}

function doGet(e) {
  try {
    var sheet = getTargetSheet(e);
    var spreadsheetTz = SpreadsheetApp.getActiveSpreadsheet().getSpreadsheetTimeZone() || 'America/New_York';
    var data = sheet.getDataRange().getValues();

    if (data.length <= 1) {
      return createJsonResponse({ status: 'success', items: [] });
    }

    var headers = data[0].map(function(h) { return String(h).toLowerCase().trim(); });
    var idIdx = headers.indexOf('id');
    var kidIdx = headers.indexOf('kid');
    var classIdx = headers.indexOf('class');
    var typeIdx = headers.indexOf('type');
    var titleIdx = headers.indexOf('title');
    var dueIdx = headers.indexOf('due');
    var notesIdx = headers.indexOf('notes');
    var activeIdx = headers.indexOf('active');
    var updatedIdx = headers.indexOf('updatedat');

    if (idIdx === -1) idIdx = 0;
    if (kidIdx === -1) kidIdx = 1;
    if (classIdx === -1) classIdx = 2;
    if (typeIdx === -1) typeIdx = 3;
    if (titleIdx === -1) titleIdx = 4;
    if (dueIdx === -1) dueIdx = 5;
    if (notesIdx === -1) notesIdx = 6;
    if (activeIdx === -1) activeIdx = 7;
    if (updatedIdx === -1) updatedIdx = 8;

    var items = [];
    for (var i = 1; i < data.length; i++) {
      var row = data[i];
      var title = String(row[titleIdx] || '').trim();
      var kid = String(row[kidIdx] || '').trim();
      if (!title && !kid) {
        continue;
      }

      var rowId = String(row[idIdx] || '').trim();
      if (!rowId) {
        rowId = generateRowId(i);
        // Backfill missing ID into sheet so manually added rows get a persistent ID
        sheet.getRange(i + 1, idIdx + 1).setValue(rowId);
      }

      var rawType = String(row[typeIdx] || 'upcoming').trim().toLowerCase();
      var normalizedType = (rawType === 'weekly') ? 'weekly' : 'upcoming';

      items.push({
        id: rowId,
        kid: kid || 'Isaac',
        class: String(row[classIdx] || '').trim(),
        type: normalizedType,
        title: title,
        due: normalizeDueValue(row[dueIdx], spreadsheetTz),
        notes: String(row[notesIdx] || '').trim(),
        active: parseActiveValue(row[activeIdx]),
        updatedAt: normalizeDueValue(row[updatedIdx], spreadsheetTz)
      });
    }

    return createJsonResponse({ status: 'success', items: items });
  } catch (err) {
    return createJsonResponse({ status: 'error', message: err.toString(), items: [] });
  }
}

function doPost(e) {
  try {
    var sheet = getTargetSheet(e);
    var contents = (e && e.postData && e.postData.contents) ? e.postData.contents : '[]';
    var payload = JSON.parse(contents);

    var items = [];
    if (Array.isArray(payload)) {
      items = payload;
    } else if (payload && Array.isArray(payload.items)) {
      items = payload.items;
    } else {
      return createJsonResponse({ status: 'error', message: 'Expected JSON array or { items: [...] }' });
    }

    sheet.clearContents();
    sheet.appendRow(HEADERS);
    sheet.getRange(1, 1, 1, HEADERS.length).setFontWeight('bold');
    sheet.setFrozenRows(1);

    var rowsToWrite = [];
    var nowIso = new Date().toISOString();

    for (var i = 0; i < items.length; i++) {
      var item = items[i];
      if (!item || (!item.title && !item.kid)) continue;

      var itemId = String(item.id || '').trim() || generateRowId(i + 1);
      var itemType = String(item.type || 'upcoming').trim().toLowerCase() === 'weekly' ? 'weekly' : 'upcoming';
      var isActive = item.active === undefined || item.active === null ? true : Boolean(item.active);

      rowsToWrite.push([
        itemId,
        String(item.kid || 'Isaac').trim(),
        String(item.class || '').trim(),
        itemType,
        String(item.title || '').trim(),
        String(item.due || '').trim(),
        String(item.notes || '').trim(),
        isActive ? 'TRUE' : 'FALSE',
        String(item.updatedAt || nowIso)
      ]);
    }

    if (rowsToWrite.length > 0) {
      // Force the 'Due' column (column 6) to plain text format so YYYY-MM-DD strings aren't mangled
      sheet.getRange(2, 6, rowsToWrite.length, 1).setNumberFormat('@');
      sheet.getRange(2, 1, rowsToWrite.length, HEADERS.length).setValues(rowsToWrite);
    }

    return createJsonResponse({ status: 'success', count: rowsToWrite.length });
  } catch (err) {
    return createJsonResponse({ status: 'error', message: err.toString() });
  }
}

function createJsonResponse(data) {
  return ContentService.createTextOutput(JSON.stringify(data))
    .setMimeType(ContentService.MimeType.JSON);
}
