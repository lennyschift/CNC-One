<script setup>
import { ref, computed, onMounted, watch } from 'vue';
import { useRoute } from 'vue-router';
import { vAutoAnimate } from '@formkit/auto-animate/vue';
import { ArrowLeft, Hash, Cog, Truck, ChevronUp, ChevronDown, Trash2, Plus, Layers, NotebookPen, History, Send, PackageCheck, Save, Workflow, X } from '@lucide/vue';
import PartImage from '../components/PartImage.vue';
import NumField from '../components/NumField.vue';
import StatusBadge from '../components/StatusBadge.vue';
import { repo } from '../data/repo.js';
import { useFertigung } from '../stores/fertigung.js';
import { useStamm } from '../stores/stamm.js';
import { STATUS, produziert, fortschritt, ueberproduktion, nochNichtGesendet, felderVon } from '../lib/fertigung.js';
import { zahl } from '../lib/format.js';
import { bereichText, erledigt, offen as serieOffen } from '../lib/serien.js';

const route = useRoute();
const f = useFertigung();
const stamm = useStamm();
const fb = computed(() => f.bauteil(route.params.id));

// Änderungen an Feldern (Namen, Zeiten, Material, Notizen ...) werden automatisch gespeichert.
const feldStand = (x) => (x ? JSON.stringify([x.id, felderVon(x)]) : '');
watch(() => feldStand(fb.value), (neu, alt) => {
  if (!neu || !alt) return;
  const id = JSON.parse(neu)[0];
  if (id === JSON.parse(alt)[0]) f.felderPlanen(id);
});

const maschinen = ref([]);
const lieferanten = ref([]);
onMounted(async () => { [maschinen.value, lieferanten.value] = await Promise.all([repo.maschinen.liste(), repo.lieferanten.liste()]); });

const buchMenge = ref({});
const sendMenge = ref({});
const fertig = computed(() => (fb.value ? produziert(fb.value) : 0));
const anteil = computed(() => (fb.value ? fortschritt(fb.value) : 0));
const ueber = computed(() => (fb.value ? ueberproduktion(fb.value) : 0));
const ring = computed(() => 2 * Math.PI * 34);
const stunden = (min) => zahl(min / 60, 1);
const zeit = (iso) => new Date(iso).toLocaleString('de-DE', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
const tag = (d) => (d ? new Date(d).toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit' }) : '–');
const geplantMin = (ag) => (ag.typ === 'fremd' ? 0 : ag.ruestMin + ag.stueckMin * fb.value.menge);
const rest = (ag) => Math.max(0, fb.value.menge - ag.gebucht);
const vorlagen = computed(() => (fb.value ? stamm.vorlagenFuer(fb.value.kundeId) : []));
const arten = (typ) => stamm.arten.filter((a) => a.typ === typ);

function buchen(ag, menge) {
  f.buchen(fb.value.id, ag.id, menge ?? buchMenge.value[ag.id]);
  buchMenge.value[ag.id] = 0;
}
function maschineWechsel(ag, name) {
  ag.maschine = name;
  const m = maschinen.value.find((x) => x.name === name);
  if (m) ag.satz = m.satz;
}
function vorlageWahl(e) {
  if (e.target.value) f.vorlageAnwenden(fb.value.id, e.target.value);
  e.target.value = '';
}
function sendungAnlegen(ag) {
  f.sendungAnlegen(fb.value.id, ag.id, sendMenge.value[ag.id] || undefined);
  sendMenge.value[ag.id] = 0;
}
const sendungStatus = (s) => (s.datumZurueck ? 'zurück' : s.datumWeg ? 'beim Lieferanten' : 'geplant');
</script>

<template>
  <div v-if="fb" class="mx-auto max-w-[1300px] space-y-4">
    <RouterLink to="/fertigung" class="inline-flex items-center gap-1.5 text-sm text-mute hover:text-ink"><ArrowLeft :size="15" /> Fertigung</RouterLink>

    <!-- Kopf -->
    <section class="card p-6">
      <div class="flex flex-wrap items-start gap-6">
        <PartImage :teil="fb.teil" :groesse="128" />
        <div class="min-w-[260px] flex-1">
          <div class="flex items-center gap-3"><span class="text-sm text-mute tnum">{{ fb.id }}</span><StatusBadge :status="fb.status" /></div>
          <h2 class="mt-1 text-2xl font-semibold tracking-tight">{{ fb.teil.name }}</h2>
          <p class="mt-0.5 text-sm text-mute">
            {{ fb.teil.teilenummer || 'ohne Teilenummer' }}<template v-if="fb.teil.zeichnungsnr"> · Zeichnung {{ fb.teil.zeichnungsnr }}</template><template v-if="fb.teil.material"> · {{ fb.teil.material }}</template>
          </p>
          <p v-if="fb.serienVon" class="mt-1 inline-flex items-center gap-1.5 rounded-full bg-surface2 px-3 py-1 text-sm"><Hash :size="14" class="text-accent" /> Seriennummern <span class="font-semibold tnum">{{ bereichText(fb.serienVon, fb.serienBis, fb.serienStellen) }}</span></p>
          <p class="mt-1 text-sm">Auftrag <RouterLink :to="`/auftraege/${fb.auftragId}`" class="text-accent hover:underline tnum">{{ fb.auftragId }}</RouterLink> · {{ fb.kundeName }}</p>

          <div class="mt-4 flex flex-wrap items-end gap-3">
            <div>
              <div class="label mb-1">Status</div>
              <div class="flex gap-1 rounded-xl border border-line bg-surface2 p-1">
                <button v-for="s in STATUS" :key="s" class="rounded-lg px-3 py-1.5 text-sm transition" :class="fb.status === s ? 'bg-accent text-white shadow-sm' : 'text-mute hover:text-ink'" @click="f.statusSetzen(fb.id, s)">{{ s }}</button>
              </div>
            </div>
            <label class="block"><span class="label mb-1 block">Priorität</span>
              <select v-model="fb.prioritaet" class="field"><option>Normal</option><option>Hoch</option><option>Eilig</option></select>
            </label>
            <label class="block"><span class="label mb-1 block">Liefertermin</span><input v-model="fb.termin" type="date" class="field" /></label>
          </div>
        </div>

        <div class="flex items-center gap-4 rounded-2xl bg-surface2 px-5 py-4">
          <svg viewBox="0 0 80 80" class="h-20 w-20 -rotate-90">
            <circle cx="40" cy="40" r="34" fill="none" stroke="var(--line)" stroke-width="7" />
            <circle cx="40" cy="40" r="34" fill="none" :stroke="anteil >= 1 ? 'var(--ok)' : 'var(--accent)'" stroke-width="7" stroke-linecap="round" :stroke-dasharray="ring" :stroke-dashoffset="ring * (1 - anteil)" style="transition: stroke-dashoffset 0.5s ease" />
          </svg>
          <div>
            <div class="text-2xl font-semibold tnum">{{ fertig }}<span class="text-base font-normal text-mute"> / {{ fb.menge }}</span></div>
            <div class="text-xs text-mute">Stück fertig durch alle Arbeitsgänge</div>
            <div v-if="ueber" class="mt-1.5 inline-block rounded-md bg-surface px-2 py-0.5 text-xs font-medium text-ok">+{{ ueber }} Überproduktion, geht später ins Lager</div>
          </div>
        </div>
      </div>
    </section>

    <div class="grid items-start gap-4 xl:grid-cols-[1fr_380px]">
      <!-- Arbeitsgänge -->
      <section class="space-y-3">
        <div class="flex flex-wrap items-center gap-2">
          <h3 class="mr-auto text-sm font-semibold">Arbeitsgänge</h3>
          <select class="field !w-auto" @change="vorlageWahl"><option value="">Vorlage anwenden …</option><option v-for="v in vorlagen" :key="v.id" :value="v.id">{{ v.name }}{{ v.kundeId ? ' (Kunde)' : '' }}</option></select>
          <button class="btn" @click="f.arbeitsgangHinzu(fb.id, 'intern')"><Plus :size="15" /> Arbeitsgang</button>
          <button class="btn" @click="f.arbeitsgangHinzu(fb.id, 'fremd')"><Truck :size="15" /> Fremdvergabe</button>
          <button class="btn" :disabled="!fb.arbeitsgaenge.length" :class="!fb.arbeitsgaenge.length ? 'pointer-events-none opacity-40' : ''" title="Arbeitsplan für künftige Angebote und Aufträge am Bauteil speichern" @click="f.planAmBauteilSpeichern(fb.id)"><Save :size="15" /> Am Bauteil speichern</button>
        </div>

        <div v-if="!fb.arbeitsgaenge.length" class="card grid place-items-center px-6 py-12 text-center">
          <Workflow :size="34" class="text-mute" :stroke-width="1.4" />
          <p class="mt-3 text-sm font-medium">Dieses Bauteil hat noch keine Arbeitsgänge</p>
          <p class="mt-1 max-w-md text-xs text-mute">Wählen Sie eine Vorlage oder legen Sie Arbeitsgänge an. Erst dann lässt sich Menge buchen. Mit „Am Bauteil speichern“ gelten sie auch für künftige Aufträge.</p>
        </div>

        <div v-auto-animate class="space-y-3">
          <article v-for="(ag, i) in fb.arbeitsgaenge" :key="ag.id" class="card p-5">
            <div class="flex items-center gap-3">
              <span class="grid h-8 w-8 shrink-0 place-items-center rounded-full text-sm font-semibold tnum" :class="ag.status === 'Fertig' ? 'bg-ok text-white' : ag.status === 'Läuft' ? 'bg-accent text-white' : 'bg-surface2 text-mute'">{{ i + 1 }}</span>
              <input v-model="ag.name" :list="'arten-' + ag.typ" class="min-w-0 flex-1 bg-transparent text-base font-semibold outline-none placeholder:font-normal placeholder:text-mute" :placeholder="ag.typ === 'fremd' ? 'Name der Fremdvergabe' : 'Name des Arbeitsgangs'" />
              <datalist :id="'arten-' + ag.typ"><option v-for="a in arten(ag.typ)" :key="a.id" :value="a.name" /></datalist>
              <span class="inline-flex items-center gap-1 rounded-full bg-surface2 px-2.5 py-0.5 text-xs text-mute"><component :is="ag.typ === 'fremd' ? Truck : Cog" :size="12" /> {{ ag.typ === 'fremd' ? 'Fremdvergabe' : 'Intern' }}</span>
              <span v-if="ag.serie" class="inline-flex items-center gap-1 rounded-full bg-accent-soft px-2.5 py-0.5 text-xs text-accent"><Hash :size="12" /> Seriennummern</span>
              <StatusBadge :status="ag.status" />
              <div class="flex">
                <button class="grid h-7 w-7 place-items-center rounded-lg text-mute hover:bg-surface2 hover:text-ink" title="Nach oben" @click="f.arbeitsgangVerschieben(fb.id, ag.id, -1)"><ChevronUp :size="15" /></button>
                <button class="grid h-7 w-7 place-items-center rounded-lg text-mute hover:bg-surface2 hover:text-ink" title="Nach unten" @click="f.arbeitsgangVerschieben(fb.id, ag.id, 1)"><ChevronDown :size="15" /></button>
                <button class="grid h-7 w-7 place-items-center rounded-lg text-mute hover:bg-accent-soft hover:text-accent" title="Arbeitsgang entfernen" @click="f.arbeitsgangWeg(fb.id, ag.id)"><Trash2 :size="15" /></button>
              </div>
            </div>

            <!-- intern -->
            <div v-if="ag.typ === 'intern'" class="mt-4 grid gap-3 sm:grid-cols-4">
              <label class="block"><span class="label mb-1 block">Maschine</span>
                <select class="field" :value="ag.maschine" @change="maschineWechsel(ag, $event.target.value)"><option value="">– wählen –</option><option v-for="m in maschinen" :key="m.name" :value="m.name">{{ m.name }}</option></select>
              </label>
              <NumField v-model="ag.satz" label="Satz" unit="€/h" />
              <NumField v-model="ag.ruestMin" label="Rüstzeit" unit="min" :step="5" />
              <NumField v-model="ag.stueckMin" label="Stückzeit" unit="min" :step="0.5" :hint="`geplant ${stunden(geplantMin(ag))} h`" />
            </div>

            <!-- fremd: Sendungen -->
            <div v-else class="mt-4 space-y-3">
              <div class="grid gap-3 sm:grid-cols-3">
                <label class="block"><span class="label mb-1 block">Lieferant</span>
                  <select v-model="ag.lieferant" class="field"><option value="">– wählen –</option><option v-for="l in lieferanten" :key="l.id" :value="l.name">{{ l.name }}</option></select>
                </label>
                <label class="block"><span class="label mb-1 block">Anfrage / Bestellung</span><input v-model="ag.bestellung" class="field" :placeholder="ag.anfrageId || 'z. B. Bestellnummer'" /></label>
              </div>
              <div class="rounded-xl bg-surface2 p-3">
                <div class="mb-2 flex items-center justify-between text-xs text-mute"><span>Sendungen (auch Teilmengen)</span><span class="tnum">noch nicht gesendet: {{ nochNichtGesendet(fb, ag) }} Stk</span></div>
                <div v-auto-animate class="space-y-1.5">
                  <div v-for="s in ag.sendungen" :key="s.id" class="flex flex-wrap items-center gap-2 rounded-lg bg-surface px-3 py-2 text-sm">
                    <span class="w-16 font-semibold tnum">{{ s.menge }} Stk</span>
                    <span class="text-xs text-mute">weg {{ tag(s.datumWeg) }} · zurück {{ tag(s.datumZurueck) }}</span>
                    <span class="rounded-full px-2 py-0.5 text-[11px]" :class="s.datumZurueck ? 'bg-surface2 text-ok' : s.datumWeg ? 'bg-surface2 text-warn' : 'bg-surface2 text-mute'">{{ sendungStatus(s) }}</span>
                    <span v-if="s.abgehakt" class="text-[11px] text-mute">mit abgehakt</span>
                    <span class="ml-auto flex gap-1.5">
                      <button v-if="!s.datumWeg" class="btn !py-1 !text-xs" @click="f.sendungWeg(fb.id, ag.id, s.id)"><Send :size="13" /> Ware weg</button>
                      <button v-else-if="!s.datumZurueck" class="btn btn-primary !py-1 !text-xs" @click="f.sendungZurueck(fb.id, ag.id, s.id)"><PackageCheck :size="13" /> Ware zurück</button>
                      <button class="grid h-7 w-7 place-items-center rounded-lg text-mute hover:text-accent" title="Sendung entfernen" @click="f.sendungLoeschen(fb.id, ag.id, s.id)"><X :size="14" /></button>
                    </span>
                  </div>
                </div>
                <div v-if="nochNichtGesendet(fb, ag) > 0" class="mt-2.5 flex flex-wrap items-end gap-2">
                  <NumField v-model="sendMenge[ag.id]" label="Menge der Sendung" unit="Stk" :decimals="0" class="w-40" :hint="`Rest ${nochNichtGesendet(fb, ag)}`" />
                  <button class="btn" @click="sendungAnlegen(ag)"><Plus :size="15" /> Sendung anlegen</button>
                  <span class="pb-2 text-xs text-mute">Leer lassen = alles, was noch fehlt.</span>
                </div>
              </div>
            </div>

            <!-- Fortschritt und Buchen -->
            <div class="mt-4 rounded-xl bg-surface2 p-3.5">
              <div class="mb-1.5 flex justify-between text-xs"><span class="text-mute">Gebucht</span><span class="font-medium tnum">{{ ag.gebucht }} / {{ fb.menge }} Stk<template v-if="ag.gebucht > fb.menge"> · <span class="text-ok">+{{ ag.gebucht - fb.menge }} Überproduktion</span></template></span></div>
              <div class="h-2 overflow-hidden rounded-full bg-line"><div class="h-full rounded-full transition-all duration-500" :class="ag.gebucht >= fb.menge ? 'bg-ok' : 'bg-accent'" :style="{ width: Math.min(100, (ag.gebucht / fb.menge) * 100) + '%' }" /></div>
              <div v-if="ag.typ === 'intern'" class="mt-3 flex flex-wrap items-end gap-2">
                <NumField v-model="buchMenge[ag.id]" label="Menge buchen" unit="Stk" :decimals="0" class="w-36" />
                <button class="btn btn-primary" :disabled="!buchMenge[ag.id]" :class="!buchMenge[ag.id] ? 'pointer-events-none opacity-40' : ''" @click="buchen(ag)">Buchen</button>
                <button class="btn" @click="buchen(ag, 1)">+1</button>
                <button class="btn" @click="buchen(ag, 5)">+5</button>
                <button class="btn" @click="buchen(ag, 10)">+10</button>
                <button v-if="rest(ag) > 0" class="btn" @click="buchen(ag, rest(ag))">Rest ({{ rest(ag) }})</button>
              </div>
              <p v-if="ag.serie && fb.serienVon" class="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 rounded-lg bg-surface px-3 py-2 text-xs">
                <span class="inline-flex items-center gap-1 text-mute"><Hash :size="12" /> Seriennummern</span>
                <span v-if="erledigt(fb.serienVon, fb.serienBis, ag.gebucht)" class="text-ok">angebracht: <span class="font-semibold tnum">{{ bereichText(erledigt(fb.serienVon, fb.serienBis, ag.gebucht).von, erledigt(fb.serienVon, fb.serienBis, ag.gebucht).bis, fb.serienStellen) }}</span></span>
                <span v-if="serieOffen(fb.serienVon, fb.serienBis, ag.gebucht)" class="text-warn">noch offen: <span class="font-semibold tnum">{{ bereichText(serieOffen(fb.serienVon, fb.serienBis, ag.gebucht).von, serieOffen(fb.serienVon, fb.serienBis, ag.gebucht).bis, fb.serienStellen) }}</span></span>
              </p>
              <p v-if="i > 0 && ag.typ === 'intern' && ag.gebucht < fb.menge" class="mt-2 text-xs text-mute">Wird hier gebucht, gelten die Arbeitsgänge davor automatisch als abgehakt.</p>
              <p v-else-if="ag.typ === 'fremd'" class="mt-2 text-xs text-mute">Gebucht wird, was vom Lieferanten zurück ist.</p>
            </div>
          </article>
        </div>
      </section>

      <!-- Rechte Spalte -->
      <aside class="space-y-4">
        <section class="card p-5">
          <h3 class="mb-4 flex items-center gap-2 text-sm font-semibold"><Layers :size="16" class="text-accent" /> Rohmaterial</h3>
          <div class="flex gap-3">
            <PartImage art="material" :groesse="64" />
            <div class="min-w-0 flex-1">
              <div class="font-medium">{{ fb.rohmaterial.werkstoff || 'Kein Werkstoff' }}</div>
              <div class="text-xs text-mute">Bedarf für {{ fb.menge }} Stk</div>
            </div>
          </div>
          <div class="mt-4 grid grid-cols-2 gap-3">
            <label class="block"><span class="label mb-1 block">Charge</span><input v-model="fb.rohmaterial.charge" class="field" placeholder="z. B. 24-0815" /></label>
            <label class="block"><span class="label mb-1 block">Lagerplatz</span><input v-model="fb.rohmaterial.lagerplatz" class="field" placeholder="z. B. R2-04" /></label>
            <NumField v-model="fb.rohmaterial.verbrauchtMm" label="Verbrauchte Länge" unit="mm" :decimals="0" />
            <label class="block"><span class="label mb-1 block">Info (Maß, Länge)</span><input v-model="fb.rohmaterial.info" class="field" placeholder="z. B. Ø30 × 3000" /></label>
          </div>
        </section>

        <section class="card p-5">
          <h3 class="mb-4 flex items-center gap-2 text-sm font-semibold"><NotebookPen :size="16" class="text-accent" /> Prüfung und Notizen</h3>
          <label class="block"><span class="label mb-1 block">Prüfmaße und Qualität</span><textarea v-model="fb.notizen.pruefmasse" rows="3" class="field resize-y" placeholder="Gemessene Werte, Auffälligkeiten …" /></label>
          <label class="mt-3 block"><span class="label mb-1 block">Bemerkungen Fertigung</span><textarea v-model="fb.notizen.bemerkungen" rows="3" class="field resize-y" /></label>
        </section>

        <section class="card p-5">
          <h3 class="mb-3 flex items-center gap-2 text-sm font-semibold"><History :size="16" class="text-accent" /> Buchungen</h3>
          <ul v-auto-animate class="space-y-1.5">
            <li v-for="b in fb.buchungen" :key="b.id" class="group flex items-center gap-3 rounded-lg px-2 py-1.5 text-sm hover:bg-surface2">
              <span class="w-14 shrink-0 text-xs text-mute tnum">{{ zeit(b.zeit) }}</span>
              <span class="min-w-0 flex-1 truncate">{{ b.agName }}<span v-if="b.auto" class="ml-1.5 text-[11px] text-mute">abgehakt</span></span>
              <span class="font-medium tnum">+{{ b.menge }}</span>
              <button class="grid h-6 w-6 place-items-center rounded-md text-mute opacity-0 transition hover:text-accent group-hover:opacity-100" title="Buchung stornieren" @click="f.buchungLoeschen(fb.id, b.id)"><Trash2 :size="13" /></button>
            </li>
          </ul>
          <p v-if="!fb.buchungen.length" class="py-4 text-center text-xs text-mute">Noch keine Buchungen.</p>
        </section>
      </aside>
    </div>
  </div>

  <div v-else class="card mx-auto grid max-w-lg place-items-center p-14 text-center">
    <p class="font-medium">Fertigungsbauteil nicht gefunden</p>
    <RouterLink to="/fertigung" class="btn mt-4">Zur Fertigung</RouterLink>
  </div>
</template>
