/**
 * Next Chapter — Application Tracker (Google Apps Script)
 *
 * Lives INSIDE Marcel's Google account, bound to the tracker spreadsheet.
 * Three jobs, zero manual entry:
 *   1. doPost      — webhook for the newsletter's Save buttons and the VM's
 *                    LinkedIn feed (applied list + recruiter replies).
 *   2. scanGmail   — daily: application confirmations -> Applied; replies
 *                    from tracked companies -> Heard back; rejection
 *                    phrasing -> Rejected.
 *   3. scanCalendar— daily: events matching a tracked company -> Interview
 *                    with the meeting date.
 * Setup steps: see SHEET-SETUP.md in the repo. Run dailyScan on a daily
 * time trigger; deploy doPost as a Web app (execute as me / anyone).
 *
 * Status ladder (writes only ever move UP; Rejected is terminal):
 *   Saved -> Applied -> Heard back -> Interview -> Offer   |  Rejected
 */

var SHEET_NAME = 'Tracker';
var TOKEN = 'CHANGE-ME-any-random-words';   // must match the repo's SHEET_TOKEN variable

var HEADERS = ['First seen', 'Applied on', 'Last contact on', 'Contact via',
               'Meeting on', 'Status', 'Title', 'Company', 'Location',
               'Salary', 'Score', 'Source', 'Job URL', 'Detected via',
               'Last update', 'Notes'];
var COL = {};  // name -> 1-based column index, filled by sheet_()
var LADDER = {'': 0, 'Saved': 1, 'Applied': 2, 'Heard back': 3,
              'Interview': 4, 'Offer': 5, 'Rejected': 9, 'Withdrawn': 9};

var REJECTION_PHRASES = ['unfortunately', 'other candidates', 'not selected',
                         'not moving forward', 'decided to pursue',
                         'will not be moving', 'position has been filled'];
var CONFIRMATION_SUBJECTS = ['your application was sent to',
                             'thank you for applying',
                             'application received',
                             'we received your application',
                             'your application to'];
// Senders that are confirmations/notifications, never a human reply.
var NOREPLY = /no-?reply|donotreply|notifications?@|jobs-noreply|talent@linkedin/i;

// ---------------------------------------------------------------------------
// Identity — mirrors history.py normalize_url / job_fingerprint in the repo
// ---------------------------------------------------------------------------
function normalizeUrl(url) {
  var u = (url || '').trim();
  var m = u.match(/linkedin\.com\/jobs\/view\/(?:[^\/?#]*?-)?(\d{6,})/i);
  if (m) return 'linkedin:' + m[1];
  u = u.split('#')[0].split('?')[0].replace(/\/+$/, '').toLowerCase();
  return u.replace(/^https?:\/\/(www\.)?/, '');
}

function normalizeText(t) {
  t = (t || '').toLowerCase().trim();
  ['inc', 'inc.', 'ltd', 'ltd.', 'limited', 'llc', 'corp', 'corp.',
   'co.', 'co', 'group', 'canada'].forEach(function (s) {
    if (t.slice(-(s.length + 1)) === ' ' + s) t = t.slice(0, -(s.length + 1)).trim();
  });
  return t.replace(/[^a-z0-9 ]+/g, ' ').replace(/\s+/g, ' ').trim();
}

function fingerprint(company, title) {
  return normalizeText(company) + '|' + normalizeText(title);
}

// A short token for matching a company in email senders / event text.
// "Placemaking 4G" -> "placemaking"; skip tokens under 4 chars.
function companyToken(company) {
  var words = normalizeText(company).split(' ').filter(function (w) {
    return w.length >= 4;
  });
  return words.length ? words[0] : '';
}

// ---------------------------------------------------------------------------
// Sheet access + upsert
// ---------------------------------------------------------------------------
function sheet_() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sh = ss.getSheetByName(SHEET_NAME);
  if (!sh) {
    sh = ss.insertSheet(SHEET_NAME);
    sh.appendRow(HEADERS);
    sh.setFrozenRows(1);
  }
  HEADERS.forEach(function (h, i) { COL[h] = i + 1; });
  return sh;
}

function findRow_(sh, url, company, title) {
  var data = sh.getDataRange().getValues();
  var nurl = normalizeUrl(url);
  var fp = fingerprint(company, title);
  for (var r = 1; r < data.length; r++) {
    var rowUrl = data[r][COL['Job URL'] - 1];
    if (nurl && rowUrl && normalizeUrl(rowUrl) === nurl) return r + 1;
    if (company && title &&
        fingerprint(data[r][COL['Company'] - 1],
                    data[r][COL['Title'] - 1]) === fp) return r + 1;
  }
  return 0;
}

function today_() {
  return Utilities.formatDate(new Date(), Session.getScriptTimeZone(),
                              'yyyy-MM-dd');
}

/**
 * evt: {action, title, company, location, salary, score, source, url,
 *       via, date}
 * action: save | unsave | applied | contact | meeting | rejected
 */
function upsert(evt) {
  var sh = sheet_();
  var row = findRow_(sh, evt.url || '', evt.company || '', evt.title || '');
  var isNew = !row;
  if (isNew) {
    row = sh.getLastRow() + 1;
    sh.getRange(row, COL['First seen']).setValue(today_());
    ['Title', 'Company', 'Location', 'Salary', 'Score', 'Source']
      .forEach(function (f) {
        var v = evt[f.toLowerCase()];
        if (v !== undefined && v !== null && v !== '')
          sh.getRange(row, COL[f]).setValue(v);
      });
    if (evt.url) sh.getRange(row, COL['Job URL']).setValue(evt.url);
    if (evt.via) sh.getRange(row, COL['Detected via']).setValue(evt.via);
  }
  var current = String(sh.getRange(row, COL['Status']).getValue() || '');
  var when = evt.date || today_();

  var target = '';
  if (evt.action === 'save') target = 'Saved';
  if (evt.action === 'applied') {
    target = 'Applied';
    if (!sh.getRange(row, COL['Applied on']).getValue())
      sh.getRange(row, COL['Applied on']).setValue(when);
  }
  if (evt.action === 'contact') {
    target = 'Heard back';
    sh.getRange(row, COL['Last contact on']).setValue(when);
    if (evt.via) sh.getRange(row, COL['Contact via']).setValue(evt.via);
  }
  if (evt.action === 'meeting') {
    target = 'Interview';
    sh.getRange(row, COL['Meeting on']).setValue(when);
  }
  if (evt.action === 'rejected') target = 'Rejected';
  if (evt.action === 'unsave') {
    // Only clears a plain bookmark; never touches an application in flight.
    if (current === 'Saved') sh.getRange(row, COL['Status']).setValue('');
    sh.getRange(row, COL['Last update']).setValue(today_());
    return {row: row, status: ''};
  }

  // Ladder: never move DOWN (a Saved click after Applied changes nothing).
  if (target && LADDER[target] > (LADDER[current] || 0)) {
    sh.getRange(row, COL['Status']).setValue(target);
    current = target;
  }
  sh.getRange(row, COL['Last update']).setValue(today_());
  return {row: row, status: current, isNew: isNew};
}

// ---------------------------------------------------------------------------
// 1. Webhook (Save buttons + VM LinkedIn feed)
// ---------------------------------------------------------------------------
function doPost(e) {
  var out = {ok: false};
  try {
    var evt = JSON.parse(e.postData.contents);
    if (evt.token !== TOKEN) {
      out.error = 'bad token';
    } else {
      var res = upsert(evt);
      out = {ok: true, row: res.row, status: res.status};
    }
  } catch (err) {
    out.error = String(err);
  }
  return ContentService.createTextOutput(JSON.stringify(out))
    .setMimeType(ContentService.MimeType.JSON);
}

// ---------------------------------------------------------------------------
// 2. Gmail scan (daily)
// ---------------------------------------------------------------------------
function scanGmail() {
  // A. New application confirmations (any company, last 3 days).
  var q = 'newer_than:3d (' + CONFIRMATION_SUBJECTS.map(function (s) {
    return 'subject:"' + s + '"';
  }).join(' OR ') + ')';
  GmailApp.search(q, 0, 30).forEach(function (thread) {
    var msg = thread.getMessages()[0];
    var subject = msg.getSubject() || '';
    var company = '';
    // "Your application was sent to Placemaking 4G" / "Your application to X"
    var m = subject.match(/application (?:was sent|to|received)[^A-Za-z0-9]*(?:to\s+)?(.+)$/i);
    if (m) company = m[1].replace(/[.!]$/, '').trim();
    if (!company) {
      var from = msg.getFrom() || '';
      company = (from.split('<')[0] || '').replace(/["']/g, '').trim();
    }
    if (!company) return;
    upsert({action: 'applied', company: company, title: subjectTitle_(subject),
            via: 'gmail', date: Utilities.formatDate(msg.getDate(),
              Session.getScriptTimeZone(), 'yyyy-MM-dd')});
  });

  // B. Replies + rejections from tracked companies.
  trackedRows_().forEach(function (t) {
    var token = companyToken(t.company);
    if (!token) return;
    GmailApp.search('newer_than:3d from:(' + token + ')', 0, 10)
      .forEach(function (thread) {
        thread.getMessages().forEach(function (msg) {
          var from = msg.getFrom() || '';
          if (NOREPLY.test(from)) return;
          var when = Utilities.formatDate(msg.getDate(),
            Session.getScriptTimeZone(), 'yyyy-MM-dd');
          var body = (msg.getPlainBody() || '').slice(0, 2000).toLowerCase();
          var rejected = REJECTION_PHRASES.some(function (p) {
            return body.indexOf(p) !== -1;
          });
          upsert({action: rejected ? 'rejected' : 'contact',
                  company: t.company, title: t.title, url: t.url,
                  via: 'email', date: when});
        });
      });
  });
}

function subjectTitle_(subject) {
  // Best-effort role from "Your application to Acme for VP Finance" shapes.
  var m = subject.match(/for (?:the )?(?:position of |role of )?(.+)$/i);
  return m ? m[1].trim() : '';
}

function trackedRows_() {
  var sh = sheet_();
  var data = sh.getDataRange().getValues();
  var rows = [];
  for (var r = 1; r < data.length; r++) {
    var status = String(data[r][COL['Status'] - 1] || '');
    if (!status || status === 'Rejected' || status === 'Withdrawn') continue;
    rows.push({company: String(data[r][COL['Company'] - 1] || ''),
               title: String(data[r][COL['Title'] - 1] || ''),
               url: String(data[r][COL['Job URL'] - 1] || '')});
  }
  return rows;
}

// ---------------------------------------------------------------------------
// 3. Calendar scan (daily)
// ---------------------------------------------------------------------------
function scanCalendar() {
  var now = new Date();
  var start = new Date(now.getTime() - 2 * 24 * 3600 * 1000);
  var end = new Date(now.getTime() + 30 * 24 * 3600 * 1000);
  var events = CalendarApp.getDefaultCalendar().getEvents(start, end);
  var tracked = trackedRows_();
  events.forEach(function (ev) {
    var text = (ev.getTitle() + ' ' + (ev.getDescription() || '')).toLowerCase();
    var guests = ev.getGuestList().map(function (g) {
      return g.getEmail().toLowerCase();
    }).join(' ');
    tracked.forEach(function (t) {
      var token = companyToken(t.company);
      if (!token) return;
      if (text.indexOf(token) !== -1 || guests.indexOf(token) !== -1) {
        upsert({action: 'meeting', company: t.company, title: t.title,
                url: t.url, via: 'calendar',
                date: Utilities.formatDate(ev.getStartTime(),
                  Session.getScriptTimeZone(), 'yyyy-MM-dd')});
      }
    });
  });
}

// The function to put on the daily time trigger.
function dailyScan() {
  scanGmail();
  scanCalendar();
}
