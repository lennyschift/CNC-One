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
import AnfrageDetailView from './views/AnfrageDetailView.vue';
import StammdatenView from './views/StammdatenView.vue';
import { ladeStammdaten } from './data/repo.js';
import './style.css';

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', redirect: '/workbench' },
    { path: '/workbench', component: WorkbenchView, meta: { titel: 'Angebots-Workbench', bereich: 'workbench' } },
    { path: '/angebote', component: AngebotListView, meta: { titel: 'Angebote', bereich: 'angebote' } },
    { path: '/angebote/:id', component: AngebotDetailView, meta: { titel: 'Angebot', bereich: 'angebote' } },
    { path: '/auftraege', component: AuftragListView, meta: { titel: 'Aufträge', bereich: 'auftraege' } },
    { path: '/auftraege/:id', component: AuftragDetailView, meta: { titel: 'Auftrag', bereich: 'auftraege' } },
    { path: '/fertigung', component: FertigungView, meta: { titel: 'Fertigung', bereich: 'fertigung' } },
    { path: '/fertigung/:id', component: FertigungDetailView, meta: { titel: 'Fertigungsbauteil', bereich: 'fertigung' } },
    { path: '/anfragen', component: AnfragenListView, meta: { titel: 'Lieferantenanfragen', bereich: 'anfragen' } },
    { path: '/anfragen/:id', component: AnfrageDetailView, meta: { titel: 'Lieferantenanfrage', bereich: 'anfragen' } },
    { path: '/stammdaten', component: StammdatenView, meta: { titel: 'Stammdaten: Arbeitsgänge und Vorlagen', bereich: 'stammdaten' } },
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
