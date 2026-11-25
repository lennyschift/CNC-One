// Die Bereiche unter "Stammdaten". Menü im Seitenstreifen, Übersicht und Reiter nutzen dieselbe Liste.
import { Users, Package, Truck, Cog, Layers, ListTree, Building2, Mail, Archive, ListChecks, FileCode2, Network, ShieldCheck } from '@lucide/vue';

export const STAMM_PUNKTE = [
  { id: 'kunden', label: 'Kunden', icon: Users, to: '/stammdaten/kunden', text: 'Firmen mit Adressen, Ansprechpartnern und Steuerdaten', zaehler: 'kunden' },
  { id: 'bauteile', label: 'Bauteile', icon: Package, to: '/stammdaten/bauteile', text: 'Bauteile der Kunden mit gespeichertem Arbeitsplan', zaehler: 'bauteile' },
  { id: 'teilefamilien', label: 'Teilefamilien', icon: Network, to: '/stammdaten/teilefamilien', text: 'Varianten eines Teils verknüpfen, mit Vorschlägen', zaehler: null },
  { id: 'lieferanten', label: 'Lieferanten', icon: Truck, to: '/stammdaten/lieferanten', text: 'Für Fremdvergabe und Lieferantenanfragen', zaehler: 'lieferanten' },
  { id: 'anfragevorlagen', label: 'Anfragevorlagen', icon: ListChecks, to: '/stammdaten/anfragevorlagen', text: 'Welche Lieferanten bei welchem Werkstoff angefragt werden', zaehler: null },
  { id: 'maschinen', label: 'Maschinen', icon: Cog, to: '/stammdaten/maschinen', text: 'Maschinen mit Stundensatz für die Kalkulation', zaehler: 'maschinen' },
  { id: 'materialien', label: 'Rohmaterial', icon: Layers, to: '/stammdaten/materialien', text: 'Werkstoffe nach ISO-Gruppe mit Zuständen, Formen, Ausführungen, Abmessungen und Anforderungen', zaehler: 'materialien' },
  { id: 'firma', label: 'Firma', icon: Building2, to: '/stammdaten/firma', text: 'Anschrift, Steuer und Bankverbindungen für Belege', zaehler: null },
  { id: 'schwaerzen', label: 'Schwärzen', icon: ShieldCheck, to: '/stammdaten/schwaerzen', text: 'Regeln, welche Kundendaten auf Zeichnungen für Partner entfernt werden', zaehler: null },
  { id: 'druckvorlagen', label: 'Druckvorlagen', icon: FileCode2, to: '/stammdaten/druckvorlagen', text: 'PDF-Vorlagen der Belege ändern, mit Vorschau', zaehler: null },
  { id: 'archiv', label: 'Archiv', icon: Archive, to: '/stammdaten/archiv', text: 'Aufbewahrungsfristen der Dokumente', zaehler: null },
  { id: 'mail', label: 'Mail-Anbindung', icon: Mail, to: '/stammdaten/mail', text: 'Postfach, aus dem Anfragen geholt werden', zaehler: null },
  { id: 'arbeitsgaenge', label: 'Arbeitsgänge und Vorlagen', icon: ListTree, to: '/stammdaten/arbeitsgaenge', text: 'Arbeitsgangarten und Vorlagen für Arbeitspläne', zaehler: 'vorlagen' },
];
