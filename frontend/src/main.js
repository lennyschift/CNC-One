import { createApp } from 'vue';
import { createPinia } from 'pinia';
import { createRouter, createWebHashHistory } from 'vue-router';
import App from './App.vue';
import WorkbenchView from './views/WorkbenchView.vue';
import AngebotListView from './views/AngebotListView.vue';
import AngebotDetailView from './views/AngebotDetailView.vue';
import AuftragListView from './views/AuftragListView.vue';
import AuftragDetailView from './views/AuftragDetailView.vue';
import FertigungView from './views/FertigungView.vue';
import FertigungDetailView from './views/FertigungDetailView.vue';
import AnfragenListView from './views/AnfragenListView.vue';
import AnfrageVergleichView from './views/AnfrageVergleichView.vue';
import AnfrageDetailView from './views/AnfrageDetailView.vue';
import RechnungListView from './views/RechnungListView.vue';
import RechnungDetailView from './views/RechnungDetailView.vue';
import MahnwesenView from './views/MahnwesenView.vue';
import MahnungDetailView from './views/MahnungDetailView.vue';
import EingangsrechnungListView from './views/EingangsrechnungListView.vue';
import MeineEinstellungenView from './views/MeineEinstellungenView.vue';
import EingangsrechnungDetailView from './views/EingangsrechnungDetailView.vue';
import FirmaView from './views/FirmaView.vue';
import LieferscheinListView from './views/LieferscheinListView.vue';
import LieferscheinDetailView from './views/LieferscheinDetailView.vue';
import LagerView from './views/LagerView.vue';
import StammHubView from './views/StammHubView.vue';
import KundenView from './views/KundenView.vue';
import BauteileView from './views/BauteileView.vue';
import TeilefamilienView from './views/TeilefamilienView.vue';
import SchwaerzregelnView from './views/SchwaerzregelnView.vue';
import AnfragevorlagenView from './views/AnfragevorlagenView.vue';
import LieferantenView from './views/LieferantenView.vue';
import MaschinenView from './views/MaschinenView.vue';
import MaterialienView from './views/MaterialienView.vue';
import ArbeitsgaengeView from './views/ArbeitsgaengeView.vue';
import PosteingangView from './views/PosteingangView.vue';
import MailEinstellungenView from './views/MailEinstellungenView.vue';
import DokumenteView from './views/DokumenteView.vue';
import ArchivView from './views/ArchivView.vue';
import CheckVorlageView from './views/CheckVorlageView.vue';
import DruckvorlagenView from './views/DruckvorlagenView.vue';
import FensterView from './views/FensterView.vue';
import { ladeStammdaten } from './data/repo.js';
import './style.css';

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', redirect: '/workbench' },
    // eigenes Fenster für Zeichnung bzw. 3D-Modell (zweiter Bildschirm), ohne Seitenleiste
    { path: '/fenster/:art', component: FensterView, meta: { titel: 'Fenster', fenster: true } },
    { path: '/posteingang/:id?', component: PosteingangView, meta: { titel: 'Posteingang', bereich: 'posteingang' } },
    { path: '/workbench', component: WorkbenchView, meta: { titel: 'Angebots-Workbench', bereich: 'workbench' } },
    { path: '/angebote', component: AngebotListView, meta: { titel: 'Angebote', bereich: 'angebote' } },
    { path: '/angebote/:id', component: AngebotDetailView, meta: { titel: 'Angebot', bereich: 'angebote' } },
    { path: '/auftraege', component: AuftragListView, meta: { titel: 'Aufträge', bereich: 'auftraege' } },
    { path: '/auftraege/:id', component: AuftragDetailView, meta: { titel: 'Auftrag', bereich: 'auftraege' } },
    { path: '/fertigung', component: FertigungView, meta: { titel: 'Fertigung', bereich: 'fertigung' } },
    { path: '/fertigung/:id', component: FertigungDetailView, meta: { titel: 'Fertigungsbauteil', bereich: 'fertigung' } },
    { path: '/lieferscheine', component: LieferscheinListView, meta: { titel: 'Lieferscheine', bereich: 'lieferscheine' } },
    { path: '/lieferscheine/:id', component: LieferscheinDetailView, meta: { titel: 'Lieferschein', bereich: 'lieferscheine' } },
    { path: '/rechnungen', component: RechnungListView, meta: { titel: 'Rechnungen', bereich: 'rechnungen', unterbereich: 'rechnungen' } },
    { path: '/rechnungen/:id', component: RechnungDetailView, meta: { titel: 'Rechnung', bereich: 'rechnungen', unterbereich: 'rechnungen' } },
    { path: '/meine-einstellungen', component: MeineEinstellungenView, meta: { titel: 'Meine Einstellungen' } },
    { path: '/eingangsrechnungen', component: EingangsrechnungListView, meta: { titel: 'Eingangsrechnungen', bereich: 'rechnungen', unterbereich: 'eingang' } },
    { path: '/eingangsrechnungen/:id', component: EingangsrechnungDetailView, meta: { titel: 'Eingangsrechnung', bereich: 'rechnungen', unterbereich: 'eingang' } },
    { path: '/mahnwesen', component: MahnwesenView, meta: { titel: 'Mahnwesen', bereich: 'rechnungen', unterbereich: 'mahnwesen' } },
    { path: '/mahnungen/:id', component: MahnungDetailView, meta: { titel: 'Mahnung', bereich: 'rechnungen', unterbereich: 'mahnwesen' } },
    { path: '/dokumente/:id?', component: DokumenteView, meta: { titel: 'Dokumente', bereich: 'dokumente' } },
    { path: '/stammdaten/archiv', component: ArchivView, meta: { titel: 'Stammdaten: Archiv', bereich: 'stammdaten' } },
    { path: '/stammdaten/checkliste', component: CheckVorlageView, meta: { titel: 'Stammdaten: Checkliste Fertigung', bereich: 'stammdaten' } },
    { path: '/stammdaten/mail', component: MailEinstellungenView, meta: { titel: 'Stammdaten: Mail-Anbindung', bereich: 'stammdaten' } },
    { path: '/stammdaten/druckvorlagen', component: DruckvorlagenView, meta: { titel: 'Stammdaten: Druckvorlagen', bereich: 'stammdaten' } },
    { path: '/stammdaten/firma', component: FirmaView, meta: { titel: 'Stammdaten: Firma', bereich: 'stammdaten' } },
    { path: '/lager', component: LagerView, meta: { titel: 'Lager', bereich: 'lager' } },
    { path: '/anfragen', component: AnfragenListView, meta: { titel: 'Lieferantenanfragen', bereich: 'anfragen' } },
    { path: '/anfragen/vergleich/:vorgang', component: AnfrageVergleichView, meta: { titel: 'Angebotsvergleich', bereich: 'anfragen' } },
    { path: '/anfragen/:id', component: AnfrageDetailView, meta: { titel: 'Lieferantenanfrage', bereich: 'anfragen' } },
    { path: '/stammdaten', component: StammHubView, meta: { titel: 'Stammdaten', bereich: 'stammdaten' } },
    { path: '/stammdaten/kunden', component: KundenView, meta: { titel: 'Stammdaten: Kunden', bereich: 'stammdaten' } },
    { path: '/stammdaten/bauteile', component: BauteileView, meta: { titel: 'Stammdaten: Bauteile', bereich: 'stammdaten' } },
    { path: '/stammdaten/schwaerzen', component: SchwaerzregelnView, meta: { titel: 'Stammdaten: Schwärzen', bereich: 'stammdaten' } },
    { path: '/stammdaten/teilefamilien', component: TeilefamilienView, meta: { titel: 'Stammdaten: Teilefamilien', bereich: 'stammdaten' } },
    { path: '/stammdaten/anfragevorlagen', component: AnfragevorlagenView, meta: { titel: 'Stammdaten: Anfragevorlagen', bereich: 'stammdaten' } },
    { path: '/stammdaten/lieferanten', component: LieferantenView, meta: { titel: 'Stammdaten: Lieferanten', bereich: 'stammdaten' } },
    { path: '/stammdaten/maschinen', component: MaschinenView, meta: { titel: 'Stammdaten: Maschinen', bereich: 'stammdaten' } },
    { path: '/stammdaten/materialien', component: MaterialienView, meta: { titel: 'Stammdaten: Rohmaterial', bereich: 'stammdaten' } },
    { path: '/stammdaten/arbeitsgaenge', component: ArbeitsgaengeView, meta: { titel: 'Stammdaten: Arbeitsgänge und Vorlagen', bereich: 'stammdaten' } },
  ],
});

function fehlerSeite(text) {
  const el = document.getElementById('app');
  el.innerHTML = `<div style="display:grid;place-items:center;height:100%;font-family:system-ui,sans-serif;text-align:center;padding:24px">
    <div><div style="font-size:18px;font-weight:600;margin-bottom:8px">CNC One konnte nicht starten</div>
    <div style="opacity:.7;max-width:420px;margin:0 auto 16px"></div>
    <a href="" style="padding:8px 14px;border:1px solid #8884;border-radius:10px;text-decoration:none;color:inherit">Erneut versuchen</a></div></div>`;
  el.querySelector('div > div > div:nth-child(2)').textContent = text;
}

// Erst Stammdaten und Benutzer aus Frappe laden, dann die Oberfläche starten.
ladeStammdaten()
  .then(() => createApp(App).use(createPinia()).use(router).mount('#app'))
  .catch((e) => fehlerSeite(e.message || 'Unbekannter Fehler'));
