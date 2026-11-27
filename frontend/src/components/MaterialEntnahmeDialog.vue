<script setup>
// Material aus dem Lager entnehmen bzw. beim Fertigmelden zurückmelden: welche Charge genau, wie viele Stangen/Platten,
// welches Reststück zurück ins Lager geht. Daraus Verbrauch gesamt und je Stück. Beim Fertigmelden (pflicht) geht es
// alternativ „ohne Lagerentnahme“ mit Grund (z. B. Beistellung des Kunden).
import { ref, computed, watch } from 'vue';
import { X, PackageMinus, Check, AlertTriangle } from '@lucide/vue';
import NumField from './NumField.vue';
import { useFertigung } from '../stores/fertigung.js';
import { entnahmeRechnen, entnahmeVorschlag } from '../lib/fertigung.js';
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
  const v = entnahmeVorschlag(c.value, fb.value?.roh?.spez, menge.value || fb.value?.menge || 0);
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
          <div v-if="!ohne">
            <div class="label mb-1.5">Charge</div>
            <div class="space-y-1.5">
              <label v-for="x in chargen" :key="x.id" class="flex cursor-pointer items-start gap-2.5 rounded-xl border px-3 py-2 transition" :class="charge === x.id ? 'border-accent bg-accent-soft/50' : 'border-line hover:border-mute'">
                <input v-model="charge" type="radio" :value="x.id" class="mt-1 accent-[var(--color-accent)]" />
                <div class="min-w-0 flex-1 text-sm">
                  <div class="flex items-center gap-2"><span class="font-semibold tnum">{{ x.id }}</span><span class="text-[11px] text-mute">{{ x.chargennr }}</span><span class="ml-auto text-[11px] tnum" :class="x.reicht >= fb.menge ? 'text-ok' : 'text-warn'">reicht für {{ x.reicht }}</span></div>
                  <div class="text-[11px] text-mute tnum">{{ x.stueck }} × {{ x.form === 'Platte' ? `${zahl(x.breite, 0)} × ${zahl(x.laenge, 0)}` : zahl(x.laenge, 0) }} mm · Zeugnis {{ x.zeugnis || 'keins' }}<template v-if="x.lagerplatz"> · {{ x.lagerplatz }}</template></div>
                  <div v-if="!x.ok" class="text-[11px] text-warn">fehlt: {{ x.fehlt.join(', ') }}</div>
                </div>
              </label>
            </div>
            <p v-if="!chargen.length" class="rounded-xl bg-surface2 px-3 py-2.5 text-xs text-mute">Keine passende Charge im Lager.</p>
          </div>

          <template v-if="!ohne && c">
            <div class="grid gap-3" :class="platte ? 'sm:grid-cols-4' : 'sm:grid-cols-3'">
              <NumField v-model="stueck" :label="platte ? 'Platten entnommen' : 'Stangen entnommen'" unit="Stk" :decimals="0" :min="1" :hint="`von ${c.stueck}, je ${zahl(c.laenge, 0)} mm`" />
              <NumField v-model="restLaenge" label="Reststück zurück: Länge" unit="mm" :decimals="0" :min="0" hint="0 = kein Rest" />
              <NumField v-if="platte" v-model="restBreite" label="Reststück: Breite" unit="mm" :decimals="0" :min="0" />
              <NumField v-model="menge" label="Gefertigte Menge" unit="Stk" :decimals="0" :min="1" hint="für den Verbrauch je Stück" />
            </div>
            <div class="grid grid-cols-2 gap-3 rounded-xl bg-surface2 px-4 py-3 text-sm">
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
