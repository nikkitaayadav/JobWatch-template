/**
 * JobWatch tracker: Google Apps Script bound to the "JobWatch Tracker" Google Sheet.
 *
 * One-time setup (see README.md):
 *   1. Paste this file into Extensions > Apps Script, change TOKEN below, save.
 *   2. Run setup() once (grant permissions).
 *   3. Deploy > New deployment > Web app: Execute as "Me", Who has access "Anyone".
 *   4. Put the web app URL and TOKEN in config/sheet.json.
 *
 * Claude's scheduled runs call the web app:
 *   POST {token, tab, rows:[{...}]} appends new jobs to that company's tab (skips Job IDs already there).
 *   GET  ?token=...&tab=Google        returns every row's Job ID, Status and Notes as JSON.
 * One tab per company (Google, Meta, ...). A missing tab is created and formatted automatically.
 * You only ever edit the Status and Notes columns.
 */

// Replace with your own long random string, and put the same value in config/sheet.json.
const TOKEN = 'CHANGE_ME_TO_A_LONG_RANDOM_STRING';
const DEFAULT_TAB = 'Google';
const HEADERS = ['Status', 'Found', 'Label', 'Score', 'Role', 'Location', 'Posted', 'Apply', 'Prep / gaps', 'Notes', 'Job ID'];
const STATUSES = ['New', 'Prepping', 'Applied', 'Applied w/ referral', 'Referral requested', 'Not interested', 'Missed', 'Closed'];

function setup() {
  getTab_(DEFAULT_TAB);
}

function getTab_(name) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sh = ss.getSheetByName(name);
  if (sh) return sh;
  sh = ss.insertSheet(name);
  sh.getRange(1, 1, 1, HEADERS.length).setValues([HEADERS])
    .setFontWeight('bold').setBackground('#202124').setFontColor('#ffffff');
  sh.setFrozenRows(1);
  sh.setFrozenColumns(1);
  const widths = [150, 85, 120, 55, 320, 180, 85, 70, 320, 200, 150];
  widths.forEach((w, i) => sh.setColumnWidth(i + 1, w));
  applyFormatting_(sh);
  return sh;
}

function applyFormatting_(sh) {
  const n = Math.max(sh.getMaxRows() - 1, 1);
  const m = headerMap_(sh);
  const status = sh.getRange(2, m['Status'] + 1, n, 1);
  status.setDataValidation(SpreadsheetApp.newDataValidation()
    .requireValueInList(STATUSES, true).setAllowInvalid(false).build());
  const label = sh.getRange(2, m['Label'] + 1, n, 1);
  const rule = (text, color, range) => SpreadsheetApp.newConditionalFormatRule()
    .whenTextContains(text).setBackground(color).setRanges([range]).build();
  sh.setConditionalFormatRules([
    rule('APPLY NOW', '#ceead6', label),
    rule('APPLY + PREP', '#fef0c7', label),
    rule('NEAR MISS', '#fce8e6', label),
    rule('New', '#e8f0fe', status),
    rule('Applied', '#ceead6', status),
    rule('Referral', '#e6f4ea', status),
    rule('Prepping', '#fef7e0', status),
    rule('Not interested', '#f1f3f4', status),
    rule('Missed', '#f1f3f4', status),
    rule('Closed', '#f1f3f4', status),
  ]);
}

function json_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}

// Columns are found by their header text, so you can reorder columns freely.
function headerMap_(sh) {
  const head = sh.getRange(1, 1, 1, sh.getLastColumn()).getValues()[0];
  const map = {};
  head.forEach((h, i) => { if (h !== '') map[String(h).trim()] = i; });
  return map;
}

function doGet(e) {
  if (!e || !e.parameter || e.parameter.token !== TOKEN) return json_({ error: 'unauthorized' });
  const sh = getTab_(e.parameter.tab || DEFAULT_TAB);
  const values = sh.getDataRange().getValues();
  const m = headerMap_(sh);
  const rows = values.slice(1).filter(r => r[m['Job ID']] !== '').map(r => ({
    jobId: String(r[m['Job ID']]), status: r[m['Status']], notes: r[m['Notes']],
    label: r[m['Label']], role: r[m['Role']], score: r[m['Score']], found: r[m['Found']],
  }));
  return json_({ rows });
}

function doPost(e) {
  const body = JSON.parse(e.postData.contents);
  if (body.token !== TOKEN) return json_({ error: 'unauthorized' });
  const lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try {
    const sh = getTab_(body.tab || DEFAULT_TAB);
    const m = headerMap_(sh);
    const width = sh.getLastColumn();
    const idCol = m['Job ID'] + 1;
    const last = sh.getLastRow();
    const existing = new Set(last > 1
      ? sh.getRange(2, idCol, last - 1, 1).getValues().map(r => String(r[0])) : []);
    const added = [];
    (body.rows || []).forEach(r => {
      if (existing.has(String(r.jobId))) return;
      const link = r.url ? '=HYPERLINK("' + r.url + '","Apply")' : '';
      const byName = {
        'Status': 'New', 'Label': r.label, 'Score': r.score, 'Role': r.role, 'Location': r.location,
        'Posted': r.posted, 'Apply': link, 'Prep / gaps': r.prep || '', 'Notes': '', 'Found': toDate_(r.found),
        'Job ID': "'" + r.jobId,
      };
      const row = new Array(width).fill('');
      Object.keys(byName).forEach(k => { if (k in m) row[m[k]] = byName[k]; });
      sh.appendRow(row);
      existing.add(String(r.jobId));
      added.push(r.jobId);
    });
    // Newest high scores on top of the open list: sort by Found desc, then Score desc.
    if (sh.getLastRow() > 2) {
      sh.getRange(2, 1, sh.getLastRow() - 1, width)
        .sort([{ column: m['Found'] + 1, ascending: false }, { column: m['Score'] + 1, ascending: false }]);
    }
    return json_({ added: added.length, ids: added });
  } finally {
    lock.releaseLock();
  }
}

// Found is kept as a date with no time, so it sorts and displays like the other rows.
function toDate_(v) {
  const m = String(v || '').match(/^(\d{4})-(\d{2})-(\d{2})/);
  return m ? new Date(+m[1], +m[2] - 1, +m[3]) : '';
}
