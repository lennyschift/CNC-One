// Regelsatz der übernommenen Tests (erfundene Firma „AFR GmbH“ in den Test-PDFs): so wie der frühere Standard des
// Schwärz-Werkzeugs. Nur für Tests — der Standard in CNC One enthält keine Kundennamen.
import { defaultRuleSet as standard, type RuleSet } from "../rules";

export function defaultRuleSet(): RuleSet {
  return {
    ...standard(),
    directKeywords: ["AFR", "AFR GmbH", "VW"],
    headerKeywords: ["Telefon", "Phone", "Abt.", "Dept", "Drawn by", "konst", "Geaendert", "Changed", "Genehmigt", "Appr.", "Name", "Drawn"],
    changeTableKeywords: ["Geaendert", "Changed", "Genehmigt", "Appr."],
    labelRightKeywords: [],
  };
}
