<script setup>
// Rohmaterial eines Fertigungsbauteils: Rohteil wie in der Workbench (ohne Preise), vorbelegt aus dem Angebot samt der
// dort gewählten Charge. Darunter die passenden Chargen im Lager (die gewählte zuerst, dann die, die reichen); eine
// Charge wählen = reservieren. Entnahmen (Stangen/Platten raus, Reststück zurück) mit Verbrauch gesamt und je Stück.
import { reactive, computed, watch } from 'vue';
import { Layers, Check, FileBadge, Warehouse, PackageMinus, Undo2, AlertTriangle } from '@lucide/vue';
import RohmaterialKarte from './RohmaterialKarte.vue';
import MaterialChip from './MaterialChip.vue';
import { useFertigung } from '../stores/fertigung.js';
import { zahl } from '../lib/format.js';

const props = defineProps({ fb: { type: Object, required: true } });
const f = useFertigung();

// Das Rohteil als „Bauteil“ für die Karte der Workbench; Änderungen gehen an den Server (roh_setzen)
const FELDER = ['form', 'abmessungId', 'abmessung', 'zustand', 'ausfuehrung', 'laenge', 'breite', 'saege', 'anforderungen', 'zeugnis'];
const spezVon = (material, roh) => {
  const s = Object.fromEntries(FELDER.filter((k) => roh?.[k] !== undefined && roh?.[k] !== null && roh?.[k] !== '').map((k) => [k, roh[k]]));
  if (material) s.werkstoff = material;
  return s;
};
const teil = reactive({ name: '', teilenummer: '', material: '', roh: null, gewichtKg: 0 });
let geladen = '';
function laden() {
  const s = props.fb.roh?.spez ?? {};
  const { werkstoff, ...roh } = s;
  Object.assign(teil, {
    name: props.fb.teil.name, teilenummer: props.fb.teil.teilenummer, material: werkstoff || props.fb.rohmaterial?.werkstoff || '',
    roh: Object.keys(roh).length || props.fb.roh?.gewaehlt ? { saege: 3, ...roh, charge: props.fb.roh?.gewaehlt || '', ausLager: !!props.fb.roh?.gewaehlt } : null,
  });
  geladen = stand();
}
const stand = () => JSON.stringify([spezVon(teil.material, teil.roh), teil.roh?.charge || '']);
const serverStand = () => JSON.stringify([props.fb.roh?.spez ?? {}, props.fb.roh?.gewaehlt || '']);
watch(() => [props.fb.id, serverStand()], ([id], alt) => { if (!alt || id !== alt[0] || stand() === geladen) laden(); }, { immediate: true });

let timer = null;
watch(teil, () => {
  clearTimeout(timer);
  timer = setTimeout(async () => {
    const jetzt = stand();
    if (jetzt === geladen) return;
    const [spez, charge] = JSON.parse(jetzt);
    const [altSpez, altCharge] = JSON.parse(geladen);
    const werte = {};
    if (JSON.stringify(spez) !== JSON.stringify(altSpez)) werte.spez = spez;
    if (charge !== altCharge) werte.charge = charge;
    geladen = jetzt;
    await f.rohSetzen(props.fb.id, werte);
  }, 600);
}, { deep: true });

const roh = computed(() => props.fb.roh ?? { passend: [], entnahmen: [] });
const platte = computed(() => roh.value.spez?.form === 'Platte');
const mass = (c) => (c.form === 'Platte' ? `${c.stueck} × ${zahl(c.breite, 0)} × ${zahl(c.laenge, 0)}` : `${c.stueck} × ${zahl(c.laenge, 0)}`);
function waehlen(c) {
  if (!teil.roh) return;
  const neu = teil.roh.charge === c.id ? '' : c.id;
  teil.roh.charge = neu;
  teil.roh.ausLager = !!neu;
}
const verbrauch = (e) => (e.einheit === 'mm²' ? `${zahl(e.verbraucht / 1e6, 3)} m²` : `${zahl(e.verbraucht, 0)} mm`);
const jeStk = (e) => (e.einheit === 'mm²' ? `${zahl(e.jeStueck / 1e4, 1)} cm²` : `${zahl(e.jeStueck, 1)} mm`);
const wann = (iso) => (iso ? new Date(iso).toLocaleString('de-DE', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }) : '');
</script>

<template>
  <section class="card p-5">
    <div class="mb-3 flex items-center gap-2">
      <h3 class="flex items-center gap-2 text-sm font-semibold"><Layers :size="16" class="text-accent" /> Rohmaterial</h3>
      <MaterialChip :fb="fb" class="ml-auto" />
    </div>
    <RohmaterialKarte :teil="teil" zeile ohne-preis :kunde-id="fb.kundeId" :nur-ansicht="fb.status === 'Fertig'" />
    <p class="mt-2 text-xs" :class="['fehlt', 'teilweise'].includes(roh.status) ? 'text-accent' : 'text-mute'">{{ roh.text }}<template v-if="roh.status !== 'entnommen' && roh.status !== 'ohne'"> · Bedarf {{ fb.menge }} Stk</template></p>

    <!-- passende Chargen im Lager -->
    <div v-if="roh.status !== 'entnommen' && roh.passend?.length" class="mt-3 space-y-1.5">
      <div class="label flex items-center gap-1.5"><Warehouse :size="12" /> Im Lager · Charge wählen</div>
      <button v-for="c in roh.passend" :key="c.id" type="button" class="w-full rounded-xl border px-3 py-2 text-left transition" :class="roh.gewaehlt === c.id ? 'border-accent bg-accent-soft/50' : c.ok && c.reicht >= fb.menge ? 'border-ok/40 hover:border-ok' : 'border-line hover:border-mute'" :disabled="fb.status === 'Fertig'" @click="waehlen(c)">
        <div class="flex items-center gap-2 text-sm"><FileBadge :size="14" class="text-mute" /><span class="font-semibold tnum">{{ c.id }}</span><span class="truncate text-[11px] text-mute">{{ c.chargennr }}</span>
          <span class="ml-auto shrink-0 text-[11px] tnum" :class="c.reicht >= fb.menge ? 'text-ok' : 'text-warn'">reicht für {{ c.reicht }}</span><Check v-if="roh.gewaehlt === c.id" :size="14" class="text-accent" /></div>
        <div class="mt-0.5 text-[11px] text-mute tnum">{{ mass(c) }} mm · Zeugnis {{ c.zeugnis || 'keins' }}<template v-if="c.lagerplatz"> · {{ c.lagerplatz }}</template><template v-if="c.lieferant"> · {{ c.lieferant }}</template></div>
        <div v-if="!c.ok" class="mt-0.5 text-[11px] text-warn">fehlt: {{ c.fehlt.join(', ') }}</div>
      </button>
    </div>

    <!-- Entnahmen -->
    <div v-if="roh.entnahmen?.length" class="mt-3 space-y-1.5">
      <div class="label flex items-center gap-1.5"><PackageMinus :size="12" /> Entnommen</div>
      <div v-for="e in roh.entnahmen" :key="e.id" class="rounded-xl bg-surface2 px-3 py-2 text-xs">
        <div class="flex items-center gap-2"><span class="font-semibold tnum">{{ e.charge }}</span><span class="text-mute">{{ e.chargennr }}</span>
          <button v-if="fb.status !== 'Fertig'" type="button" class="ml-auto text-mute hover:text-accent" title="Entnahme zurücknehmen (falsche Charge)" @click="f.entnahmeZurueck(fb.id, e.id)"><Undo2 :size="13" /></button></div>
        <div class="mt-0.5 tnum">{{ e.stueck }} × {{ e.form === 'Platte' ? `${zahl(e.breite, 0)} × ${zahl(e.laenge, 0)}` : zahl(e.laenge, 0) }} mm<template v-if="e.restLaenge"> · Rest {{ e.form === 'Platte' ? `${zahl(e.restBreite, 0)} × ${zahl(e.restLaenge, 0)}` : zahl(e.restLaenge, 0) }} mm zurück ins Lager<template v-if="e.restCharge"> ({{ e.restCharge }})</template></template></div>
        <div class="mt-0.5 font-medium tnum">Verbraucht {{ verbrauch(e) }} · {{ jeStk(e) }} je Stück ({{ e.menge }} Stk)</div>
        <div class="text-[11px] text-mute">{{ e.von }} · {{ wann(e.am) }}<template v-if="e.notiz"> · {{ e.notiz }}</template></div>
      </div>
    </div>
    <p v-if="roh.ohneLager" class="mt-3 flex items-start gap-1.5 rounded-lg bg-surface2 px-2.5 py-1.5 text-xs text-mute"><AlertTriangle :size="13" class="mt-0.5 shrink-0" /> Ohne Lagerentnahme: {{ roh.ohneLager }}</p>

    <button v-if="fb.status !== 'Fertig' && roh.status !== 'ohne'" type="button" class="btn mt-3 w-full justify-center" :disabled="!roh.passend?.length" :class="roh.passend?.length ? '' : 'pointer-events-none opacity-40'" :title="roh.passend?.length ? '' : 'Keine passende Charge im Lager'" @click="f.materialAbfragen(fb.id)"><PackageMinus :size="15" /> {{ roh.entnahmen?.length ? 'Weitere Entnahme' : 'Material entnehmen' }}</button>
    <p v-if="platte" class="mt-1 text-[11px] text-mute">Platten: Verbrauch als Fläche.</p>
  </section>
</template>
