import type { RedactionRect, RuleKind } from "./types";

export const KIND_LABEL: Record<RuleKind, string> = {
  keyword: "Stichwort",
  header: "Kopfzeile",
  changeTable: "Änderungstabelle",
  labelRight: "Wert neben Beschriftung",
  email: "E-Mail",
  phone: "Telefon",
  logo: "Logo",
  annotation: "Anmerkung/Stempel",
  manual: "Manuell",
};

/** Key of the "kind" an area is documented under: its rule, or "import" for areas loaded from a JSON file. */
export function rectKindKey(r: Pick<RedactionRect, "kind" | "source">): string {
  return r.kind ?? (r.source === "import" ? "import" : "manual");
}

/** Human label for the list: "Logo", "Manuell", "Import" — "Logo (angepasst)" if the user changed an automatic proposal. */
export function rectKindLabel(r: Pick<RedactionRect, "kind" | "source">): string {
  const key = rectKindKey(r);
  const base = key === "import" ? "Import" : KIND_LABEL[key as RuleKind] ?? "Manuell";
  return r.kind && r.kind !== "manual" && r.source === "manual" ? `${base} (angepasst)` : base;
}

/** Counts areas by documented kind. */
export function countRectsByKind(rects: readonly Pick<RedactionRect, "kind" | "source">[]): Record<string, number> {
  const out: Record<string, number> = {};
  for (const r of rects) {
    const k = rectKindKey(r);
    out[k] = (out[k] ?? 0) + 1;
  }
  return out;
}

export function describeKindCounts(counts: Record<string, number>): string {
  return Object.entries(counts)
    .filter(([, n]) => n > 0)
    .map(([k, n]) => `${k === "import" ? "Import" : KIND_LABEL[k as RuleKind] ?? k} ${n}`)
    .join(", ");
}
