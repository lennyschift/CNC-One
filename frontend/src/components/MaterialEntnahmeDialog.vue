<script setup>
// Material aus dem Lager entnehmen bzw. beim Fertigmelden zurückmelden: welche Charge genau, wie viele Stangen/Platten,
// welches Reststück zurück ins Lager geht. Daraus Verbrauch gesamt und je Stück. Beim Fertigmelden (pflicht) geht es
// alternativ „ohne Lagerentnahme“ mit Grund (z. B. Beistellung des Kunden).
import { ref, computed, watch } from 'vue';
import { X, PackageMinus, Check, AlertTriangle } from '@lucide/vue';
import NumField from './NumField.vue';
import ChargenAuswahl from './ChargenAuswahl.vue';
import { useFertigung } from '../stores/fertigung.js';
import { entnahmeRechnen, entnahmeVorschlag } from '../lib/fertigung.js';
import { artikelText } from '../lib/werkstoffbaum.js';
import { zahl } from '../lib/format.js';

const f = useFertigung();
const fb = computed(() => (f.materialAnfrage ? f.bauteil(f.materialAnfrage.fbId) : null));
const pflicht = computed(() => !!f.materialAnfrage?.pflicht);
const chargen = computed(() => fb.value?.roh?.passend ?? []);

const charge = ref('');
const stueck = ref(1);
const restLaenge = ref(0);
const restBreite = ref(0);
const menge = ref(0);
const notiz = ref('');
const ohne = ref(false);
const grund = ref('');
const arbeitet = ref(false);

const c = computed(() => chargen.value.find((x) => x.id === charge.value) ?? null);
function vorbelegen() {
  if (!fb.value) return;
  menge.value = fb.value.menge;
  charge.value = (chargen.value.find((x) => x.id === fb.value.roh?.gewaehlt) ?? chargen.value.find((x) => x.ok) ?? chargen.value[0])?.id ?? '';
  ohne.value = !chargen.value.length;
  grund.value = '';
  notiz.value = '';
}
watch(() => f.materialAnfrage, (a) => { if (a) vorbelegen(); });
watch(charge, () => {
  const bekannt = fb.value?.roh?.verbrauch?.einheit === 'mm' ? fb.value.roh.verbrauch.jeStueck : 0;
  const v = entnahmeVorschlag(c.value, { ...(fb.value?.roh?.spez ?? {}), verbrauchJeStueck: bekannt }, menge.value || fb.value?.menge || 0);
  stueck.value = v.stueck;
  restLaenge.value = v.restLaenge;
  restBreite.value = 0;
});
const platte = computed(() => c.value?.form === 'Platte');
const r = computed(() => entnahmeRechnen(c.value, stueck.value, restLaenge.value, restBreite.value, menge.value));
const fehler = computed(() => {
  if (ohne.value) return pflicht.value && !grund.value.trim() ? 'Bitte einen Grund angeben.' : '';
  if (!c.value) return 'Bitte eine Charge wählen.';
  if (!(stueck.value >= 1)) return 'Mindestens 1 Stange/Platte.';
  if (stueck.value > c.value.stueck) return `In der Charge sind nur ${c.value.stueck} Stück.`;
  if (restLaenge.value > c.value.laenge || (platte.value && restBreite.value > c.value.breite)) return 'Das Reststück ist größer als das Material.';
  if (platte.value && restLaenge.value && !restBreite.value) return 'Beim Reststück einer Platte Länge und Breite angeben.';
  return '';
});
// Stangen: Verbrauch eingeben → Reststück = entnommen − Verbrauch (nicht kleiner als 0)
const entnommenMm = computed(() => (c.value ? Number(stueck.value || 0) * Number(c.value.laenge || 0) : 0));
const jeStueckMm = computed(() => Math.round((r.value.jeStueck || 0) * 10) / 10);
function gesamtSetzen(v) {
  restLaenge.value = Math.max(0, Math.round(entnommenMm.value - Number(v || 0)));
}
function jeStueckSetzen(v) {
  gesamtSetzen(Number(v || 0) * Number(menge.value || 0));
}
const titel = computed(() => artikelText(fb.value?.roh?.spez?.werkstoff, fb.value?.roh?.spez));
const verbraucht = computed(() => (r.value.einheit === 'mm²' ? `${zahl(r.value.verbraucht / 1e6, 3)} m²` : `${zahl(r.value.verbraucht, 0)} mm`));
const jeStueck = computed(() => (r.value.einheit === 'mm²' ? `${zahl(r.value.jeStueck / 1e4, 1)} cm²` : `${zahl(r.value.jeStueck, 1)} mm`));
const soll = computed(() => {
  const s = fb.value?.roh?.spez;
  return s?.laenge ? (platte.value ? `${zahl(Number(s.breite) + Number(s.saege || 0), 1)} × ${zahl(Number(s.laenge) + Number(s.saege || 0), 1)} mm` : `${zahl(Number(s.laenge) + Number(s.saege || 0), 1)} mm`) : '';
});

async function buchen() {
  if (fehler.value || arbeitet.value) return;
  if (ohne.value) { f.materialAntwort({ ohne: grund.value.trim() }); return; }
  arbeitet.value = true;
  const res = await f.materialEntnehmen(fb.value.id, { charge: charge.value, stueck: stueck.value, rest_laenge: restLaenge.value || 0, rest_breite: restBreite.value || 0, menge: menge.value, notiz: notiz.value });
  arbeitet.value = false;
  if (res) f.materialAntwort({});
}
</script>

<template>
  <Teleport to="body">
    <div v-if="fb" class="fixed inset-0 z-[70] grid place-items-center bg-black/45 p-4 backdrop-blur-[2px]" @mousedown.self="f.materialAntwort(null)">
      <div class="card flex max-h-[92vh] w-[min(640px,96vw)] flex-col overflow-hidden shadow-2xl">
        <header class="flex items-center justify-between border-b border-line px-5 py-3.5">
          <div>
            <h2 class="text-base font-semibold">{{ pflicht ? 'Fertig melden: welches Material wurde verwendet?' : 'Material aus dem Lager entnehmen' }}</h2>
            <p class="text-xs text-mute">{{ fb.id }} · {{ fb.teil.name }} · {{ fb.menge }} Stk<template v-if="soll"> · Zuschnitt {{ soll }}</template></p>
          </div>
          <button class="grid h-8 w-8 place-items-center rounded-lg text-mute hover:bg-surface2" @click="f.materialAntwort(null)"><X :size="18" /></button>
        </header>

        <div class="min-h-0 space-y-4 overflow-auto px-5 py-4">
          <ChargenAuswahl v-if="!ohne" :chargen="chargen" :gewaehlt="charge" :titel="titel" :bedarf="fb.menge" @waehlen="(x) => (charge = x.id)" />

          <template v-if="!ohne && c">
            <div class="grid gap-3" :class="platte ? 'sm:grid-cols-4' : 'sm:grid-cols-3'">
              <NumField v-model="stueck" :label="platte ? 'Platten entnommen' : 'Stangen entnommen'" unit="Stk" :decimals="0" :min="1" :hint="`von ${c.stueck}, je ${zahl(c.laenge, 0)} mm`" />
              <NumField v-model="menge" label="Gefertigte Menge" unit="Stk" :decimals="0" :min="1" hint="für den Verbrauch je Stück" />
              <NumField v-model="restLaenge" label="Reststück zurück: Länge" unit="mm" :decimals="0" :min="0" hint="0 = kein Rest" />
              <NumField v-if="platte" v-model="restBreite" label="Reststück: Breite" unit="mm" :decimals="0" :min="0" />
            </div>
            <!-- Stangen: Verbrauch je Stück oder gesamt eingeben, das Reststück rechnet sich daraus (und umgekehrt) -->
            <div v-if="!platte" class="rounded-xl bg-surface2 px-4 py-3">
              <div class="grid gap-3 sm:grid-cols-2">
                <NumField :model-value="jeStueckMm" label="Verbraucht je Stück" unit="mm" :decimals="1" :min="0" :hint="soll ? `geplant ${soll}` : 'inkl. Säge und Verschnitt'" @update:model-value="jeStueckSetzen" />
                <NumField :model-value="r.verbraucht" label="Verbraucht gesamt" unit="mm" :decimals="0" :min="0" :hint="`entnommen ${zahl(entnommenMm, 0)} mm`" @update:model-value="gesamtSetzen" />
              </div>
              <p class="mt-1.5 text-[11px] text-mute">Eine Angabe genügt: Verbrauch je Stück, gesamt oder das Reststück – der Rest rechnet sich. Der Verbrauch je Stück wird am Bauteil gemerkt und beim nächsten Auftrag für den Materialbedarf genommen.</p>
            </div>
            <div v-else class="grid grid-cols-2 gap-3 rounded-xl bg-surface2 px-4 py-3 text-sm">
              <div><div class="label">Verbraucht gesamt</div><div class="text-lg font-semibold tnum">{{ verbraucht }}</div></div>
              <div><div class="label">Je Stück</div><div class="text-lg font-semibold tnum">{{ jeStueck }}</div><div v-if="soll" class="text-[11px] text-mute">geplant {{ soll }}</div></div>
            </div>
            <p v-if="restLaenge > 0" class="text-xs text-mute">Das Reststück kommt als eigener Lagerposten mit derselben Charge, demselben Zeugnis und Lagerplatz zurück.</p>
            <label class="block"><span class="label mb-1 block">Notiz</span><input v-model="notiz" class="field" placeholder="z. B. Stange angeschnitten, Lagerplatz geändert" /></label>
          </template>

          <div v-if="pflicht" class="rounded-xl border border-line p-3">
            <label class="flex items-center gap-2 text-sm"><input v-model="ohne" type="checkbox" class="accent-[var(--color-accent)]" /> Ohne Lagerentnahme fertig melden</label>
            <input v-if="ohne" v-model="grund" class="field mt-2" placeholder="Grund, z. B. Beistellung des Kunden, Material aus anderem Auftrag" />
          </div>
        </div>

        <footer class="flex flex-wrap items-center gap-2 border-t border-line px-5 py-3.5">
          <span v-if="fehler" class="mr-auto flex items-center gap-1.5 text-xs text-warn"><AlertTriangle :size="13" /> {{ fehler }}</span>
          <button class="btn ml-auto" @click="f.materialAntwort(null)">Abbrechen</button>
          <button class="btn btn-primary" :disabled="!!fehler || arbeitet" :class="fehler ? 'pointer-events-none opacity-40' : ''" @click="buchen">
            <template v-if="ohne"><Check :size="15" /> Weiter ohne Entnahme</template><template v-else><PackageMinus :size="15" /> Entnahme buchen{{ pflicht ? ' und weiter' : '' }}</template>
          </button>
        </footer>
      </div>
    </div>
  </Teleport>
</template>
