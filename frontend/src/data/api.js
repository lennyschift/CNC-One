// Aufrufe an die Frappe-App. Die Oberfläche wird von Frappe ausgeliefert, deshalb gelten Anmeldung und CSRF-Schutz der Sitzung.

export class ApiFehler extends Error {
  constructor(text, status, art) {
    super(text);
    this.status = status;
    this.art = art;
  }
}

const csrf = () => window.frappe_csrf_token || '';

function textAus(data) {
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

export async function abmelden() {
  try { await fetch('/api/method/logout', { method: 'POST', credentials: 'same-origin', headers: { 'X-Frappe-CSRF-Token': csrf() } }); } catch { /* egal */ }
  zumLogin();
}
