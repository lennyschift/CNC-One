// Die Bereiche unter "Stammdaten". Menü im Seitenstreifen, Übersicht und Reiter nutzen dieselbe Liste.
import { Users, Package, Truck, Cog, Layers, ListTree, Building2 } from '@lucide/vue';

export const STAMM_PUNKTE = [
  { id: 'kunden', label: 'Kunden', icon: Users, to: '/stammdaten/kunden', text: 'Firmen mit Adressen, Ansprechpartnern und Steuerdaten', zaehler: 'kunden' },
  { id: 'bauteile', label: 'Bauteile', icon: Package, to: '/stammdaten/bauteile', text: 'Bauteile der Kunden mit gespeichertem Arbeitsplan', zaehler: 'bauteile' },
  { id: 'lieferanten', label: 'Lieferanten', icon: Truck, to: '/stammdaten/lieferanten', text: 'Für Fremdvergabe und Lieferantenanfragen', zaehler: 'lieferanten' },
  { id: 'maschinen', label: 'Maschinen', icon: Cog, to: '/stammdaten/maschinen', text: 'Maschinen mit Stundensatz für die Kalkulation', zaehler: 'maschinen' },
  { id: 'materialien', label: 'Rohmaterial', icon: Layers, to: '/stammdaten/materialien', text: 'Rohmaterial mit Preis je Kilogramm', zaehler: 'materialien' },
  { id: 'firma', label: 'Firma', icon: Building2, to: '/stammdaten/firma', text: 'Anschrift, Steuer und Bankverbindungen für Belege', zaehler: null },
  { id: 'arbeitsgaenge', label: 'Arbeitsgänge und Vorlagen', icon: ListTree, to: '/stammdaten/arbeitsgaenge', text: 'Arbeitsgangarten und Vorlagen für Arbeitspläne', zaehler: 'vorlagen' },
];
