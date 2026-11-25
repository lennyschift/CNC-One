/**
 * Regelsatz für die automatische Erkennung beim Schwärzen. In CNC One liegen die Regelsätze in der Datenbank
 * (Doctype „Schwaerzregelsatz“: ein Standard für alle, dazu einer je Kunde), geprüft und begrenzt auf dem Server
 * (api/schwaerzen.py). Hier nur das Format, Grenzen und der Standard.
 *
 * Übernommen aus dem Schwärz-Werkzeug (web/src/features/redaction/rules.ts) — ohne zod und ohne fest eingetragene
 * Kundennamen: die Begriffe eines Kunden (Name, Kürzel, Ansprechpartner, Mail-Domain) setzt CNC One selbst dazu.
 */

export const RULE_LIMITS = {
  maxKeywords: 200,
  maxKeywordLength: 80,
  maxLogos: 12,
} as const;

export const LOGO_ZONES = ["all", "top", "bottom", "left", "right", "corners"] as const;
export type LogoZone = (typeof LOGO_ZONES)[number];

export interface LogoOptions {
  threshold?: number;
  maxHits?: number;
  zone?: LogoZone;
}

export interface LogoTemplate {
  id: string;
  name: string;
  /** Bild als data:-URL oder Adresse einer (privaten) Datei dieser Site. */
  dataUrl: string;
  /** Größe des Originalbilds in Pixel (= bei 300 dpi): die Suchgrößen beziehen sich darauf. */
  width: number;
  height: number;
  enabled: boolean;
}

/** Standard für Treffer je Logo und Seite: ein Logo steht meist ein- oder zweimal da, mehr sind Verwechslungen. */
export const DEFAULT_LOGO_MAX_HITS = 3;

export interface RuleSet {
  version: 1;
  name: string;
  /** Wörter, die selbst geschwärzt werden (Kundenname …). */
  directKeywords: string[];
  /** Kopfzeilen-Wörter: der Text direkt DARUNTER wird geschwärzt. */
  headerKeywords: string[];
  /** Teil der Kopfzeilen-Wörter, die eine Spalte der Änderungstabelle anführen: die ganze Spalte wird geschwärzt. */
  changeTableKeywords: string[];
  /** Beschriftungen („Gez.“, „Gepr.“): die Felder RECHTS daneben in derselben Zeile werden geschwärzt. */
  labelRightKeywords: string[];
  /** Spaltenköpfe von Änderungstabellen, die nach OBEN wachsen (unterste 35 % der Seite). */
  columnAboveKeywords: string[];
  detectEmail: boolean;
  /** Telefonnummern-Muster (aus: Teilenummern sehen manchmal so aus). */
  detectPhone: boolean;
  /** 0,3 … 0,95; schwächere Logo-Treffer werden nicht vorgeschlagen. */
  logoThreshold: number;
  logos: LogoTemplate[];
  logoOptions: Record<string, LogoOptions>;
  disabledFolderLogos: string[];
}

/**
 * Standard-Regelsatz für alle Kunden: nur, was bei fast jeder Zeichnung Personen- oder Firmendaten trägt. Kundennamen
 * stehen hier bewusst NICHT; die kommen aus dem Regelsatz des Kunden und aus den Stammdaten des Kunden.
 */
export function defaultRuleSet(): RuleSet {
  return {
    version: 1,
    name: "Standard",
    directKeywords: [],
    headerKeywords: [],
    changeTableKeywords: [],
    labelRightKeywords: ["Gez.", "Gezeichnet", "Gepr.", "Geprüft", "Freigegeben", "Erstellt", "Bearb.", "Drawn by", "Checked by", "Approved by"],
    columnAboveKeywords: [],
    detectEmail: true,
    detectPhone: false,
    logoThreshold: 0.45,
    logos: [],
    logoOptions: {},
    disabledFolderLogos: [],
  };
}

const liste = (v: unknown, max = RULE_LIMITS.maxKeywords): string[] => {
  if (!Array.isArray(v)) return [];
  const seen = new Set<string>();
  const out: string[] = [];
  for (const x of v) {
    const s = String(x ?? "").trim().slice(0, RULE_LIMITS.maxKeywordLength);
    if (!s || seen.has(s.toLowerCase())) continue;
    seen.add(s.toLowerCase());
    out.push(s);
    if (out.length >= max) break;
  }
  return out;
};

/** Beliebige Eingabe (aus der Datenbank) zu einem gültigen Regelsatz; fehlende Teile kommen aus dem Standard. */
export function regelnBereinigen(roh: unknown): RuleSet {
  const d = defaultRuleSet();
  const r = (roh && typeof roh === "object" ? roh : {}) as Partial<RuleSet>;
  const zahl = (v: unknown, lo: number, hi: number, std: number) => (typeof v === "number" && Number.isFinite(v) ? Math.min(hi, Math.max(lo, v)) : std);
  const logos = Array.isArray(r.logos)
    ? r.logos
        .filter((l) => l && typeof l.dataUrl === "string" && (/^data:image\/(png|jpeg);base64,/.test(l.dataUrl) || /^\/(private\/)?files\//.test(l.dataUrl)))
        .slice(0, RULE_LIMITS.maxLogos)
        .map((l) => ({
          id: String(l.id).slice(0, 64), name: String(l.name ?? "Logo").slice(0, 80), dataUrl: l.dataUrl,
          width: Math.round(zahl(l.width, 4, 20000, 100)), height: Math.round(zahl(l.height, 4, 20000, 100)), enabled: l.enabled !== false,
        }))
    : [];
  const optionen: Record<string, LogoOptions> = {};
  for (const [k, o] of Object.entries(r.logoOptions ?? {})) {
    if (!o || typeof o !== "object") continue;
    optionen[k.slice(0, 70)] = {
      ...(o.threshold != null ? { threshold: zahl(o.threshold, 0.3, 0.95, d.logoThreshold) } : {}),
      ...(o.maxHits != null ? { maxHits: Math.round(zahl(o.maxHits, 1, 10, DEFAULT_LOGO_MAX_HITS)) } : {}),
      ...(o.zone && (LOGO_ZONES as readonly string[]).includes(o.zone) ? { zone: o.zone } : {}),
    };
  }
  return normalizeRuleSet({
    version: 1,
    name: String(r.name ?? d.name).slice(0, 80),
    directKeywords: liste(r.directKeywords ?? d.directKeywords),
    headerKeywords: liste(r.headerKeywords ?? d.headerKeywords),
    changeTableKeywords: liste(r.changeTableKeywords ?? d.changeTableKeywords),
    labelRightKeywords: liste(r.labelRightKeywords ?? d.labelRightKeywords),
    columnAboveKeywords: liste(r.columnAboveKeywords ?? d.columnAboveKeywords),
    detectEmail: r.detectEmail ?? d.detectEmail,
    detectPhone: r.detectPhone ?? d.detectPhone,
    logoThreshold: zahl(r.logoThreshold, 0.3, 0.95, d.logoThreshold),
    logos,
    logoOptions: optionen,
    disabledFolderLogos: [],
  });
}

/** Behält nur die Änderungstabellen-Wörter, die auch Kopfzeilen-Wörter sind. */
export function normalizeRuleSet(r: RuleSet): RuleSet {
  const headers = new Set(r.headerKeywords.map((k) => k.toLowerCase()));
  return { ...r, changeTableKeywords: r.changeTableKeywords.filter((k) => headers.has(k.toLowerCase())) };
}

/** Begriffe für die Nachprüfung der gespeicherten Datei: jedes direkte Stichwort muss aus der Ausgabe verschwunden sein. */
export function auditTermsFromRules(r: RuleSet): string[] {
  return r.directKeywords.filter((k) => k.trim().length >= 2);
}
