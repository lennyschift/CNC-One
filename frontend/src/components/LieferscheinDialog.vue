<script setup>
// Lieferschein anlegen: aus einem Auftrag (vorgeschlagen wird die gefertigte, noch nicht gelieferte Menge) oder frei aus den
// Bauteilen eines Kunden. Ohne Preise. Ist weniger auf Lager als geliefert wird, entsteht im Lager eine Minusbuchung,
// die ausgeglichen ist, sobald die Fertigung einbucht.
import { ref, reactive, computed, onMounted } from 'vue';
import { Plus, Trash2, Hash, AlertTriangle, Search } from '@lucide/vue';
import StammDialog from './StammDialog.vue';
import PartImage from './PartImage.vue';
import NumField from './NumField.vue';
import CustomerCombobox from './CustomerCombobox.vue';
import SerienFeld from './SerienFeld.vue';
import { call } from '../data/api.js';
import { bereich, bereichText, hoechste } from '../lib/serien.js';
import { useBelege } from '../stores/belege.js';
import { useLieferung } from '../stores/lieferung.js';

const props = defineProps({ auftragId: { type: String, default: '' } });
const emit = defineEmits(['schliessen', 'angelegt']);
const b = useBelege();
const l = useLieferung();

const kundeId = ref('');
const kundeName = ref('');
const kopf = reactive({ lieferdatum: '', kundenbestellnr: '', bemerkung: '' });
const zeilen = reactive([]);
const bauteile = ref([]);
const geladen = ref(false);
const speichert = ref(false);
const suche = ref('');

onMounted(async () => {
  if (props.auftragId) {
    const v = await l.vorschlag(props.auftragId);
    if (v) {
      kundeId.value = v.kundeId;
      kundeName.value = v.kundeName;
      kopf.kundenbestellnr = v.kundenbestellnr;
      for (const p of v.positionen) {
        if (p.offen <= 0) continue;
        zeilen.push({
          key: p.auftragPosKey, aktiv: p.vorschlag > 0, bauteilId: p.bauteilId, teil: p.teil,
          menge: p.vorschlag > 0 ? p.vorschlag : p.offen, auftrag: props.auftragId, auftragsposition: p.auftragPosKey,
          bestellt: p.bestellt, gefertigt: p.gefertigt, geliefert: p.geliefert, offen: p.offen,
          serienVon: p.serienVon, serienBis: p.serienBis, serienStellen: p.serienStellen, serienStart: '',
        });
      }
    }
  } else {
    // frisch holen: Bauteile, Lagerbestand und der Lieferstand der Aufträge (zum Zuordnen)
    await Promise.all([b.auftraegeNeuLaden(), l.lagerLaden().catch(() => {})]);
    try { bauteile.value = await call('cnc_one.api.stammdaten.liste', { art: 'bauteil' }); } catch { /* Auswahl bleibt leer */ }
  }
  geladen.value = true;
});

// ---- freie Lieferung: Bauteile des Kunden
const verfuegbar = computed(() => {
  const q = suche.value.trim().toLowerCase();
  const schon = new Set(zeilen.map((z) => z.bauteilId));
  return bauteile.value.filter((x) => x.kundeId === kundeId.value && x.status === 'Aktiv' && !schon.has(x.id)
    && (!q || `${x.name} ${x.teilenummer}`.toLowerCase().includes(q)));
});
const bestandVon = (id) => l.lager.find((x) => x.bauteilId === id)?.bestand ?? 0;

// Offene Auftragspositionen dieses Kunden zum Bauteil (zum optionalen Zuordnen einer freien Position)
function auftragsOptionen(z) {
  const out = [];
  for (const a of b.auftraege) {
    if (a.kunde?.id !== kundeId.value || a.status === 'Storniert') continue;
    for (const p of a.positionen) {
      const offen = p.menge - (p.geliefert ?? 0);
      if (p.teil.teilenummer === z.teil.teilenummer && offen > 0) out.push({ wert: `${a.id}|${p.key}`, label: `${a.id} · offen ${offen} Stk`, auftrag: a.id, pos: p, offen });
    }
  }
  return out;
}
function auftragWahl(z, wert) {
  const o = auftragsOptionen(z).find((x) => x.wert === wert);
  z.auftrag = o?.auftrag ?? '';
  z.auftragsposition = o?.pos.key ?? '';
  z.offen = o?.offen ?? null;
  z.serienVon = o?.pos.serienVon ? o.pos.serienVon + (o.pos.geliefert ?? 0) : null;
  z.serienBis = o?.pos.serienBis ?? null;
  z.serienStellen = o?.pos.serienStellen ?? z.serienStellen;
}
function hinzu(x) {
  zeilen.push({
    key: x.id, aktiv: true, bauteilId: x.id, teil: { name: x.name, teilenummer: x.teilenummer, zeichnungsnr: x.zeichnungsnr, vorschaubild: '' }, menge: 1,
    auftrag: '', auftragsposition: '', offen: null, serienVon: null, serienBis: null, serienStellen: x.serienStellen ?? 4, serienStart: '', mitSerien: !!x.seriennummern,
  });
}

// ---- Prüfung und Vorschau je Zeile
const sicht = computed(() => zeilen.map((z) => {
  const menge = Math.floor(Number(z.menge) || 0);
  const fehler = !z.aktiv ? '' : menge <= 0 ? 'Menge eingeben' : z.offen !== null && menge > z.offen ? `Es sind nur noch ${z.offen} Stk offen` : '';
  // Seriennummern: aus dem Auftrag der nächste ungelieferte Bereich, sonst von Hand
  let serien = null;
  if (z.serienVon) serien = menge > 0 ? { von: z.serienVon, bis: z.serienVon + menge - 1 } : null;
  else if (z.mitSerien && String(z.serienStart || '').trim()) {
    const br = bereich(z.serienStart, menge);
    serien = br && br.bis <= hoechste(z.serienStellen) ? br : null;
  }
  const serienFehler = z.aktiv && z.mitSerien && !z.serienVon && String(z.serienStart || '').trim() && !serien ? 'Seriennummern passen nicht in die Stellenzahl' : '';
  // Minusbuchung: wie viel ist noch nicht gefertigt bzw. nicht auf Lager?
  const verfuegbarMenge = z.auftragsposition && z.gefertigt !== undefined ? z.gefertigt - z.geliefert : bestandVon(z.bauteilId);
  const minus = z.aktiv && z.bauteilId ? Math.max(0, menge - Math.max(0, verfuegbarMenge)) : 0;
  return { z, menge, fehler: fehler || serienFehler, serien, minus, verfuegbarMenge };
}));
const aktive = computed(() => sicht.value.filter((s) => s.z.aktiv));
const gueltig = computed(() => !!kundeId.value && aktive.value.length > 0 && aktive.value.every((s) => !s.fehler));
const gesamt = computed(() => aktive.value.reduce((n, s) => n + s.menge, 0));

async function anlegen() {
  speichert.value = true;
  const rec = await l.anlegen({
    kunde: kundeId.value,
    lieferdatum: kopf.lieferdatum || null,
    kundenbestellnr: kopf.kundenbestellnr,
    bemerkung: kopf.bemerkung,
    positionen: aktive.value.map((s) => ({
      bauteilId: s.z.bauteilId, menge: s.menge, auftrag: s.z.auftrag || null, auftragsposition: s.z.auftragsposition || null,
      serienStart: !s.z.serienVon && s.z.mitSerien ? String(s.z.serienStart || '') : '',
    })),
  });
  speichert.value = false;
  if (rec) emit('angelegt', rec);
}
</script>

<template>
  <StammDialog :titel="auftragId ? `Lieferschein aus ${auftragId}` : 'Neuer Lieferschein'" :untertitel="kundeName" breite="900px" neu speichern-text="Lieferschein anlegen" :speichert="speichert" :gueltig="gueltig" @schliessen="emit('schliessen')" @speichern="anlegen">
    <p v-if="!geladen" class="py-8 text-center text-sm text-mute">Lädt …</p>
    <template v-else>
      <div v-if="!auftragId" class="max-w-md"><CustomerCombobox v-model="kundeId" /></div>

      <div class="grid gap-3 sm:grid-cols-3">
        <label class="block"><span class="label mb-1 block">Lieferdatum</span><input v-model="kopf.lieferdatum" type="date" class="field" /></label>
        <label class="block"><span class="label mb-1 block">Bestellnummer des Kunden</span><input v-model="kopf.kundenbestellnr" class="field" /></label>
        <label class="block"><span class="label mb-1 block">Bemerkung</span><input v-model="kopf.bemerkung" class="field" /></label>
      </div>

      <section>
        <h3 class="mb-2 text-sm font-semibold">Positionen <span class="font-normal text-mute">· ohne Preise</span></h3>
        <p v-if="auftragId && !zeilen.length" class="rounded-xl border border-dashed border-line px-4 py-6 text-center text-sm text-mute">Aus diesem Auftrag ist schon alles geliefert.</p>
        <div class="space-y-2">
          <div v-for="s in sicht" :key="s.z.key" class="rounded-xl border p-3 transition" :class="s.z.aktiv ? 'border-line bg-surface' : 'border-line/60 bg-surface2 opacity-75'">
            <div class="flex items-start gap-3">
              <input v-model="s.z.aktiv" type="checkbox" class="mt-1 h-4 w-4 accent-[var(--accent)]" title="Liefern" />
              <PartImage :teil="s.z.teil" :groesse="48" />
              <div class="min-w-0 flex-1">
                <div class="flex items-start justify-between gap-3">
                  <div class="min-w-0">
                    <div class="truncate font-medium">{{ s.z.teil.name || 'Ohne Bezeichnung' }}</div>
                    <div class="truncate text-xs text-mute">{{ s.z.teil.teilenummer }}<template v-if="s.z.teil.zeichnungsnr"> · Zeichnung {{ s.z.teil.zeichnungsnr }}</template></div>
                  </div>
                  <button v-if="!auftragId" type="button" class="grid h-7 w-7 shrink-0 place-items-center rounded-lg text-mute hover:text-accent" title="Position entfernen" @click="zeilen.splice(zeilen.indexOf(s.z), 1)"><Trash2 :size="14" /></button>
                </div>

                <div v-if="s.z.aktiv" class="mt-2.5 flex flex-wrap items-end gap-3">
                  <NumField v-model="s.z.menge" label="Liefermenge" unit="Stk" :decimals="0" :min="1" class="w-36" />
                  <div v-if="s.z.auftragsposition && s.z.bestellt" class="pb-2 text-xs text-mute tnum">bestellt {{ s.z.bestellt }} · gefertigt {{ s.z.gefertigt }} · geliefert {{ s.z.geliefert }} · <span class="font-medium text-ink">offen {{ s.z.offen }}</span></div>
                  <label v-else-if="!auftragId && auftragsOptionen(s.z).length" class="block"><span class="label mb-1 block">Zu Auftrag</span>
                    <select class="field !w-auto" :value="s.z.auftrag ? `${s.z.auftrag}|${s.z.auftragsposition}` : ''" @change="auftragWahl(s.z, $event.target.value)"><option value="">ohne Auftrag</option><option v-for="o in auftragsOptionen(s.z)" :key="o.wert" :value="o.wert">{{ o.label }}</option></select>
                  </label>
                  <SerienFeld v-if="s.z.mitSerien && !s.z.serienVon" v-model="s.z.serienStart" :stellen="s.z.serienStellen" label="Seriennummern ab (optional)" class="w-44" />
                  <div v-if="s.serien" class="pb-2 text-sm"><Hash :size="14" class="mr-1 inline text-accent" />Nummern <span class="font-semibold tnum">{{ bereichText(s.serien.von, s.serien.bis, s.z.serienStellen) }}</span></div>
                </div>
                <p v-if="s.fehler" class="mt-1.5 flex items-center gap-1.5 text-xs text-accent"><AlertTriangle :size="13" /> {{ s.fehler }}</p>
                <p v-else-if="s.z.aktiv && s.minus > 0" class="mt-1.5 flex items-center gap-1.5 text-xs text-warn"><AlertTriangle :size="13" /> {{ s.minus }} Stk noch nicht fertig: im Lager entsteht eine Minusbuchung, die mit der Fertigung ausgeglichen wird.</p>
              </div>
            </div>
          </div>
        </div>

        <div v-if="!auftragId && kundeId" class="mt-3 rounded-xl border border-line p-3">
          <div class="mb-2 flex items-center justify-between gap-3">
            <div class="label">Bauteil hinzufügen</div>
            <label class="relative"><Search :size="14" class="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-mute" /><input v-model="suche" class="field !w-52 !py-1.5 !pl-8" placeholder="suchen …" /></label>
          </div>
          <div class="max-h-44 space-y-1 overflow-auto">
            <button v-for="x in verfuegbar" :key="x.id" type="button" class="flex w-full items-center gap-3 rounded-lg px-2 py-1.5 text-left text-sm transition hover:bg-surface2" @click="hinzu(x)">
              <PartImage :teil="x" :groesse="30" /><span class="min-w-0 flex-1 truncate">{{ x.name || 'Ohne Bezeichnung' }} <span class="text-xs text-mute">{{ x.teilenummer }}</span></span>
              <span class="text-xs text-mute tnum">Lager {{ bestandVon(x.id) }}</span><Plus :size="14" class="text-accent" />
            </button>
            <p v-if="!verfuegbar.length" class="px-2 py-3 text-center text-xs text-mute">{{ suche ? 'Keine Treffer.' : 'Keine weiteren Bauteile dieses Kunden.' }}</p>
          </div>
        </div>
        <p v-else-if="!auftragId" class="mt-3 text-center text-xs text-mute">Bitte zuerst den Kunden wählen, dann lassen sich seine Bauteile hinzufügen.</p>
      </section>
      <p v-if="aktive.length" class="text-right text-sm text-mute">{{ aktive.length }} Position{{ aktive.length === 1 ? '' : 'en' }} · <span class="font-medium text-ink tnum">{{ gesamt }} Stk</span></p>
    </template>
  </StammDialog>
</template>
