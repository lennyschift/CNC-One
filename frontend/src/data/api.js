// Aufrufe an die Frappe-App. Die Oberfläche wird von Frappe ausgeliefert, deshalb gelten Anmeldung und CSRF-Schutz der Sitzung.

export class ApiFehler extends Error {
  constructor(text, status, art) {
    super(text);
    this.status = status;
    this.art = art;
  }
}

const csrf = () => window.frappe_csrf_token || '';

export function textAus(data) {
  try {
    const m = JSON.parse(data._server_messages || '[]');
    if (m.length) return String(JSON.parse(m[0]).message).replace(/<[^>]+>/g, '');
  } catch { /* weiter */ }
  if (data.exception) return String(data.exception).split(':').slice(1).join(':').trim() || String(data.exception);
  return data.message || 'Unbekannter Fehler';
}

export function zumLogin() {
  window.location.href = `/login?redirect-to=${encodeURIComponent(window.location.pathname)}`;
}

// POST auf eine freigegebene Funktion der App, z. B. call('cnc_one.api.stamm.bootstrap').
export async function call(method, args = {}) {
  let r;
  try {
    r = await fetch(`/api/method/${method}`, {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json', 'X-Frappe-CSRF-Token': csrf() },
      body: JSON.stringify(args),
    });
  } catch {
    throw new ApiFehler('Der Server ist nicht erreichbar.', 0, 'netz');
  }
  let data = {};
  try { data = await r.json(); } catch { /* keine JSON-Antwort */ }
  if (r.status === 401 || data.exc_type === 'AuthenticationError' || data.session_expired) {
    zumLogin();
    throw new ApiFehler('Die Sitzung ist abgelaufen.', r.status, 'sitzung');
  }
  if (!r.ok) throw new ApiFehler(textAus(data), r.status, data.exc_type || 'fehler');
  return data.message;
}

// Lädt eine Datei als private Frappe-Datei hoch und hängt sie an ein Dokument. Liefert { name, file_url, file_name, file_size }.
export async function hochladen(datei, { doctype, docname, name = datei.name }) {
  const daten = new FormData();
  daten.append('file', datei, name);
  daten.append('is_private', '1');
  daten.append('doctype', doctype);
  daten.append('docname', docname);
  let r;
  try {
    r = await fetch('/api/method/upload_file', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { Accept: 'application/json', 'X-Frappe-CSRF-Token': csrf() },
      body: daten,
    });
  } catch {
    throw new ApiFehler('Der Server ist nicht erreichbar.', 0, 'netz');
  }
  let data = {};
  try { data = await r.json(); } catch { /* keine JSON-Antwort */ }
  if (r.status === 401) { zumLogin(); throw new ApiFehler('Die Sitzung ist abgelaufen.', r.status, 'sitzung'); }
  if (r.status === 413) throw new ApiFehler(`„${name}“ ist zu groß zum Hochladen.`, r.status, 'groesse');
  if (!r.ok) throw new ApiFehler(textAus(data), r.status, data.exc_type || 'fehler');
  return data.message;
}

export async function abmelden() {
  try { await fetch('/api/method/logout', { method: 'POST', credentials: 'same-origin', headers: { 'X-Frappe-CSRF-Token': csrf() } }); } catch { /* egal */ }
  zumLogin();
}
