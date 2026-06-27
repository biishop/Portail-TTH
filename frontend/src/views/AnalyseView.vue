<script setup>
import { ref, computed, onMounted } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, BarChart } from 'echarts/charts'
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
  DataZoomComponent,
} from 'echarts/components'
import VChart from 'vue-echarts'
import api from '../api'
import { stationLabel, cycleIcon, cleanCycle } from '../constants'

use([CanvasRenderer, LineChart, BarChart, GridComponent, TooltipComponent, LegendComponent, DataZoomComponent])


const TABS = [
  { id: 'cible',      icon: '🎯', label: 'Superposition des traces' },
  { id: 'portique',   icon: '🏗️', label: 'Sollicitation des portiques' },
  { id: 'recettes',   icon: '📋', label: 'Catalogue des recettes' },
  { id: 'config',     icon: '⚗️', label: 'Configuration des cycles' },
]
const activeTab = ref('cible')
const activeTabLabel = computed(() => TABS.find((t) => t.id === activeTab.value)?.label)

const fours = ref([])
const station = ref(null)
const cycles = ref([])
const selectedCycle = ref('')
const n = ref(10)
const overlay = ref(null)
const loadingCycles = ref(false)
const loadingOverlay = ref(false)

function formatDate(s) {
  if (!s) return ''
  return s.replace('T', ' ').slice(0, 19)
}

async function loadFours() {
  const { data } = await api.get('/fours')
  fours.value = data
  if (data.length) {
    station.value = data[0].station
    await loadCycles()
  }
}

async function loadCycles() {
  if (station.value === null) return
  selectedCycle.value = ''
  overlay.value = null
  loadingCycles.value = true
  try {
    const { data } = await api.get('/analyse/cycles', { params: { station: station.value } })
    cycles.value = data.items
  } finally {
    loadingCycles.value = false
  }
}

async function loadOverlay() {
  if (station.value === null || !selectedCycle.value) return
  loadingOverlay.value = true
  try {
    const { data } = await api.get('/analyse/overlay', {
      params: { station: station.value, cycle: selectedCycle.value, n: n.value },
    })
    overlay.value = data
  } finally {
    loadingOverlay.value = false
  }
}

// Plus l'echantillon est ancien (idx eleve), moins il a de contraste.
function opacityFor(idx, total) {
  if (total <= 1) return 1
  return 1 - (idx / (total - 1)) * 0.85
}

const overlayCharts = computed(() => {
  if (!overlay.value) return []
  const passages = overlay.value.passages

  const variables = new Map()
  for (const p of passages) {
    for (const v of p.variables) {

      if (!variables.has(v.variable)) variables.set(v.variable, v.name)
    }
  }

  const charts = []
  for (const [variable, name] of variables) {
    const series = passages.map((p, idx) => {
      const v = p.variables.find((x) => x.variable === variable)
      const opacity = opacityFor(idx, passages.length)
      return {
        name: `${p.charge} — ${formatDate(p.tps_deb)}`,
        type: 'line',
        showSymbol: false,
        data: v ? v.points : [],
        lineStyle: { color: '#2563eb', opacity },
        itemStyle: { color: '#2563eb', opacity },
      }
    })
    charts.push({
      variable,
      label: name,
      option: {
        tooltip: { trigger: 'axis' },
        legend: { data: series.map((s) => s.name), top: 0, type: 'scroll' },
        grid: { top: 40, left: 60, right: 30, bottom: 60 },
        xAxis: { type: 'value', name: 'Temps écoulé (min)', nameLocation: 'middle', nameGap: 30 },
        yAxis: { type: 'value' },
        dataZoom: [{ type: 'inside' }, { type: 'slider' }],
        series,
      },
    })
  }
  return charts
})

// ── Portiques ─────────────────────────────────────────────────────
const portiquesListe   = ref([])
const selectedPortique = ref(null)
const portiquestats    = ref(null)
const loadingPortique  = ref(false)

async function loadPortiques() {
  const { data } = await api.get('/analyse/portiques')
  portiquesListe.value = data
  if (data.length) {
    // pré-sélectionner le portique le plus actif
    selectedPortique.value = data.reduce((a, b) => (b.nb_charges > a.nb_charges ? b : a)).portique
    await loadPortiqueStats()
  }
}

async function loadPortiqueStats() {
  if (!selectedPortique.value) return
  loadingPortique.value = true
  try {
    const { data } = await api.get(`/analyse/portique/${selectedPortique.value}`)
    portiquestats.value = data
  } finally {
    loadingPortique.value = false
  }
}

const portiqueMensuelOption = computed(() => {
  const d = portiquestats.value
  if (!d?.par_mois?.length) return {}
  const months = d.par_mois.map((m) => m.mois)
  return {
    tooltip: { trigger: 'axis' },
    legend: { top: 0, data: ['Nb fournées', 'Tonnage (kg)', 'Cumulatif (kg)'] },
    grid:   { top: 50, left: 70, right: 70, bottom: 60 },
    xAxis:  { type: 'category', data: months, axisLabel: { rotate: 45, fontSize: 10 } },
    yAxis: [
      { type: 'value', name: 'Cycles / Tonnage' },
      { type: 'value', name: 'Cumulatif (kg)', position: 'right' },
    ],
    dataZoom: [{ type: 'inside' }, { type: 'slider' }],
    series: [
      {
        name: 'Nb fournées', type: 'bar', data: d.par_mois.map((m) => m.nb_fournees),
        itemStyle: { color: '#2563eb' },
      },
      {
        name: 'Tonnage (kg)', type: 'bar', data: d.par_mois.map((m) => m.poids_kg),
        itemStyle: { color: '#f59e0b' },
      },
      {
        name: 'Cumulatif (kg)', type: 'line', yAxisIndex: 1,
        data: d.par_mois.map((m) => m.cum_poids_kg),
        smooth: true, showSymbol: false,
        lineStyle: { color: '#22c55e', width: 2 },
        areaStyle: { color: 'rgba(34,197,94,0.08)' },
      },
    ],
  }
})

const portiquesHistoOption = computed(() => {
  const d = portiquestats.value
  if (!d?.histogramme?.length) return {}
  return {
    tooltip: { trigger: 'axis' },
    grid:    { top: 20, left: 60, right: 20, bottom: 60 },
    xAxis:   { type: 'category', data: d.histogramme.map((h) => h.label),
               axisLabel: { rotate: 30, fontSize: 10 } },
    yAxis:   { type: 'value', name: 'Nb fournées' },
    series: [{
      type: 'bar',
      data: d.histogramme.map((h, i) => ({
        value: h.nb,
        itemStyle: {
          color: i < 3 ? '#22c55e' : i < 7 ? '#f59e0b' : '#ef4444',
        },
      })),
    }],
  }
})

// ── Recettes ──────────────────────────────────────────────────────
const recettes         = ref([])
const selectedRecette  = ref(null)
const recetteSearch    = ref('')

const recettesFiltrees = computed(() => {
  const q = recetteSearch.value.toLowerCase()
  return q
    ? recettes.value.filter(r => r.recette.toLowerCase().includes(q))
    : recettes.value
})

const recetteDetail = computed(() =>
  recettes.value.find(r => r.recette === selectedRecette.value) || null
)

async function loadRecettes() {
  const { data } = await api.get('/analyse/recettes')
  recettes.value = data
  if (data.length) selectedRecette.value = data[0].recette
}

// ── Config cycles ─────────────────────────────────────────────────
const cfgSources      = ref([])
const cfgSource       = ref(null)
const cfgCycles       = ref([])
const cfgCycleSearch  = ref('')
const cfgSelectedCycle = ref(null)
const cfgDetail       = ref(null)
const cfgParamsMeta   = ref({})
const cfgLoading      = ref(false)

const cfgCyclesFiltres = computed(() => {
  const q = cfgCycleSearch.value.toLowerCase()
  return q ? cfgCycles.value.filter(c => c.toLowerCase().includes(q)) : cfgCycles.value
})

async function loadCfgSources() {
  const { data } = await api.get('/analyse/config-cycles/sources')
  cfgSources.value = data
  if (data.length) {
    cfgSource.value = data[0].id
    await loadCfgCycles()
  }
}

async function loadCfgCycles() {
  if (!cfgSource.value) return
  cfgSelectedCycle.value = null
  cfgDetail.value = null
  cfgCycleSearch.value = ''
  const { data } = await api.get(`/analyse/config-cycles/${cfgSource.value}`)
  cfgCycles.value   = data.cycles
  cfgParamsMeta.value = data.params_meta
  if (data.cycles.length) {
    cfgSelectedCycle.value = data.cycles[0]
    await loadCfgDetail()
  }
}

async function loadCfgDetail() {
  if (!cfgSource.value || !cfgSelectedCycle.value) return
  cfgLoading.value = true
  try {
    const { data } = await api.get(
      `/analyse/config-cycles/${cfgSource.value}/${encodeURIComponent(cfgSelectedCycle.value)}`
    )
    cfgDetail.value     = data.rows
    cfgParamsMeta.value = data.params_meta
  } finally {
    cfgLoading.value = false
  }
}

const SOURCE_FALLBACK_ICONS = {
  cryogenique: '❄️',
  revenu:      '♨️',
  trempe:      '💧',
  attente:     '⏱️',
  lavage:      '🚿',
  prelavage:   '🚿',
  lav_rev:     '🚿',
  n2hp:        '💨',
}

function cfgIcon(cycle) {
  const icon = cycleIcon(cycle)
  if (icon !== '🔥') return icon
  return SOURCE_FALLBACK_ICONS[cfgSource.value] || '🔥'
}

async function selectCfgCycle(cycle) {
  cfgSelectedCycle.value = cycle
  await loadCfgDetail()
}

function fmtDureeS(s) {
  if (!s) return null
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60)
  if (h > 0) return `${h}h${String(m).padStart(2,'0')}`
  return `${m}min`
}

function fmtParam(val, unit) {
  if (val === null || val === undefined || val === 0) return '—'
  if (unit === 's') {
    const m = Math.floor(val / 60), s = val % 60, h = Math.floor(m / 60)
    if (h > 0) return `${h}h${String(m % 60).padStart(2,'0')} (${val}s)`
    if (m > 0) return `${m}min${s > 0 ? String(s).padStart(2,'0') + 's' : ''} (${val}s)`
    return `${val}s`
  }
  return unit ? `${val} ${unit}` : String(val)
}

onMounted(() => {
  loadFours()
  loadPortiques()
  loadRecettes()
  loadCfgSources()
})
</script>

<template>
  <h1 class="page-title">Analyse</h1>

  <div class="analyse-tabs">
    <button
      v-for="tab in TABS"
      :key="tab.id"
      class="analyse-tab"
      :class="{ active: activeTab === tab.id }"
      :data-tooltip="tab.label"
      @click="activeTab = tab.id"
    >
      {{ tab.icon }}
    </button>
  </div>

  <template v-if="activeTab === 'cible'">
    <div class="card">
      <h2>{{ activeTabLabel }}</h2>
      <div class="filters">
        <label>
          Four
          <select v-model.number="station" @change="loadCycles">
            <option v-for="f in fours" :key="f.station" :value="f.station">
              {{ stationLabel(f.station) }}
            </option>
          </select>
        </label>
        <label>
          Cycles existants
          <select v-model="selectedCycle" :disabled="loadingCycles || !cycles.length">
            <option value="" disabled>
              {{ loadingCycles ? 'Chargement…' : (cycles.length ? 'Choisir un cycle' : 'Aucun cycle') }}
            </option>
            <option v-for="c in cycles" :key="c.cycle" :value="c.cycle">
              {{ c.cycle }} ({{ c.nb_occurrences }})
            </option>
          </select>
        </label>
        <label>
          Échantillons (n)
          <select v-model.number="n">
            <option v-for="opt in [5, 10, 20, 50]" :key="opt" :value="opt">{{ opt }}</option>
          </select>
        </label>
        <button class="btn btn-primary" :disabled="!selectedCycle || loadingOverlay" @click="loadOverlay">
          OK
        </button>
      </div>
    </div>

    <p v-if="loadingOverlay" class="loading">Chargement des courbes…</p>

    <template v-else-if="overlay">
      <div class="card" v-for="chart in overlayCharts" :key="chart.variable">
        <h2>{{ chart.label }}</h2>
        <v-chart :option="chart.option" autoresize style="height: 350px;" />
      </div>
      <p v-if="!overlayCharts.length">Aucune donnée de température pour ce four.</p>
    </template>
  </template>

  <!-- ── Portiques ─────────────────────────────────────────────── -->
  <template v-if="activeTab === 'portique'">
    <div class="card">
      <h2>{{ activeTabLabel }}</h2>
      <div class="filters">
        <label>
          Portique
          <select v-model.number="selectedPortique" @change="loadPortiqueStats">
            <option v-for="p in portiquesListe" :key="p.portique" :value="p.portique">
              Portique {{ p.portique }} — {{ p.nb_charges }} fournées
            </option>
          </select>
        </label>
      </div>

      <div class="portique-notice">
        ⚠️ Aucun événement d'entretien/remise à zéro enregistré — les statistiques couvrent
        toute la période d'exploitation depuis l'origine des données.
      </div>
    </div>

    <p v-if="loadingPortique" class="loading">Calcul des sollicitations…</p>

    <template v-else-if="portiquestats && portiquestats.total_fournees > 0">

      <!-- KPIs -->
      <div class="portique-kpis">
        <div class="pkpi">
          <div class="pkpi-icon" style="background:linear-gradient(135deg,#2563eb,#1d4ed8)">🏋️</div>
          <div class="pkpi-body">
            <div class="pkpi-value">{{ portiquestats.total_fournees.toLocaleString('fr-FR') }}</div>
            <div class="pkpi-label">Cycles de levage</div>
          </div>
        </div>
        <div class="pkpi">
          <div class="pkpi-icon" style="background:linear-gradient(135deg,#f59e0b,#d97706)">⚖️</div>
          <div class="pkpi-body">
            <div class="pkpi-value">{{ (portiquestats.poids_cumule_kg / 1000).toLocaleString('fr-FR', {maximumFractionDigits:1}) }} t</div>
            <div class="pkpi-label">Tonnage cumulé soulevé</div>
          </div>
        </div>
        <div class="pkpi">
          <div class="pkpi-icon" style="background:linear-gradient(135deg,#22c55e,#16a34a)">📊</div>
          <div class="pkpi-body">
            <div class="pkpi-value">{{ portiquestats.poids_moyen_kg?.toLocaleString('fr-FR', {maximumFractionDigits:0}) }} kg</div>
            <div class="pkpi-label">Charge moyenne / fournée</div>
          </div>
        </div>
        <div class="pkpi">
          <div class="pkpi-icon" style="background:linear-gradient(135deg,#ef4444,#dc2626)">⚡</div>
          <div class="pkpi-body">
            <div class="pkpi-value">{{ portiquestats.indice_fatigue.toLocaleString('fr-FR', {maximumFractionDigits:1}) }}</div>
            <div class="pkpi-label">Indice de fatigue (Miner³)</div>
            <div class="pkpi-sub">éq. cycles à charge max</div>
          </div>
        </div>
      </div>

      <!-- Infos charge max -->
      <div class="portique-meta card">
        <span>Charge max observée : <b>{{ portiquestats.poids_max_kg?.toLocaleString('fr-FR') }} kg</b></span>
        <span class="sep">·</span>
        <span>Données : {{ portiquestats.par_mois[0]?.mois }} → {{ portiquestats.par_mois.at(-1)?.mois }}</span>
        <span class="sep">·</span>
        <span>Interprétation : indice &lt; 50 = faible usure · 50–200 = modéré · &gt; 200 = surveiller</span>
      </div>

      <!-- Évolution mensuelle -->
      <div class="card">
        <h2>Évolution mensuelle — cycles & tonnage</h2>
        <v-chart :option="portiqueMensuelOption" autoresize style="height:320px" />
      </div>

      <!-- Spectre de charge -->
      <div class="card">
        <h2>Spectre de charge — répartition des fournées par tranche de poids</h2>
        <div class="histo-legend">
          <span class="hl hl-green">■ Léger</span>
          <span class="hl hl-amber">■ Moyen</span>
          <span class="hl hl-red">■ Lourd</span>
        </div>
        <v-chart :option="portiquesHistoOption" autoresize style="height:260px" />
      </div>

    </template>
    <p v-else-if="portiquestats && portiquestats.total_fournees === 0" class="loading">
      Aucune donnée de poids pour ce portique.
    </p>
  </template>

  <!-- ── Configuration des cycles ─────────────────────────────── -->
  <template v-if="activeTab === 'config'">
    <div class="card">
      <h2>{{ activeTabLabel }}</h2>
      <div class="filters">
        <label>
          Type de cycle
          <select v-model="cfgSource" @change="loadCfgCycles">
            <option v-for="s in cfgSources" :key="s.id" :value="s.id">
              {{ s.label }} ({{ s.nb_cycles }} cycles)
            </option>
          </select>
        </label>
      </div>
    </div>

    <div class="recettes-layout">
      <!-- Liste cycles -->
      <div class="card rec-list-card">
        <input v-model="cfgCycleSearch" type="text" class="cfg-search"
               placeholder="Rechercher un cycle…" />
        <div
          v-for="c in cfgCyclesFiltres" :key="c"
          class="rec-item"
          :class="{ active: cfgSelectedCycle === c }"
          @click="selectCfgCycle(c)"
        >
          <span class="cfg-icon">{{ cfgIcon(c) }}</span>
          <span class="cfg-name">{{ cleanCycle(c) }}</span>
        </div>
      </div>

      <!-- Détail paramètres -->
      <div class="card rec-detail-card">
        <template v-if="cfgSelectedCycle && cfgDetail">
          <div class="rec-detail-header">
            <h3>{{ cfgIcon(cfgSelectedCycle) }} {{ cfgSelectedCycle }}</h3>
            <span class="badge badge-info">{{ cfgDetail.length }} bloc{{ cfgDetail.length > 1 ? 's' : '' }}</span>
          </div>

          <p v-if="cfgLoading" class="loading">Chargement…</p>
          <table v-else>
            <thead>
              <tr>
                <th v-if="cfgDetail[0]?.bloc !== undefined">Bloc</th>
                <th v-for="(meta, col) in cfgParamsMeta" :key="col">
                  {{ meta[0] }}
                  <span class="param-unit" v-if="meta[1]"> ({{ meta[1] }})</span>
                </th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in cfgDetail" :key="row.id">
                <td v-if="row.bloc !== undefined" class="bloc-cell">{{ row.bloc }}</td>
                <td v-for="(meta, col) in cfgParamsMeta" :key="col"
                    :class="{ 'param-zero': !row[col] || row[col] === 0,
                               'param-val': row[col] && row[col] !== 0 }">
                  {{ fmtParam(row[col], meta[1]) }}
                </td>
              </tr>
            </tbody>
          </table>
        </template>
        <p v-else class="loading">Sélectionnez un cycle.</p>
      </div>
    </div>
  </template>

  <!-- ── Catalogue des recettes ──────────────────────────────── -->
  <template v-if="activeTab === 'recettes'">
    <div class="card">
      <h2>{{ activeTabLabel }}</h2>
      <div class="filters">
        <label>
          Rechercher
          <input v-model="recetteSearch" type="text" placeholder="nom de recette…" />
        </label>
        <span class="rec-count">{{ recettesFiltrees.length }} recette{{ recettesFiltrees.length > 1 ? 's' : '' }}</span>
      </div>
    </div>

    <div class="recettes-layout">
      <!-- Liste gauche -->
      <div class="card rec-list-card">
        <div
          v-for="r in recettesFiltrees" :key="r.recette"
          class="rec-item"
          :class="{ active: selectedRecette === r.recette }"
          @click="selectedRecette = r.recette"
        >
          <div class="rec-name">{{ r.recette }}</div>
          <div class="rec-meta">{{ r.steps.length }} étapes · {{ r.deb_valid?.slice(0,10) }}</div>
        </div>
      </div>

      <!-- Détail droite -->
      <div class="card rec-detail-card" v-if="recetteDetail">
        <div class="rec-detail-header">
          <h3>{{ recetteDetail.recette }}</h3>
          <span class="badge badge-info">{{ recetteDetail.steps.length }} étapes</span>
        </div>
        <p class="rec-valid">Valide depuis {{ recetteDetail.deb_valid?.replace('T',' ').slice(0,16) }}</p>

        <!-- Séquence visuelle des cycles -->
        <div class="rec-sequence">
          <div v-for="(step, idx) in recetteDetail.steps" :key="step.bloc" class="rec-step-wrap">
            <div class="rec-step">
              <div class="rec-step-icon">{{ cycleIcon(step.cycle) }}</div>
              <div class="rec-step-info">
                <div class="rec-step-cycle">{{ step.cycle }}</div>
                <div class="rec-step-bloc">bloc {{ step.bloc }}</div>
                <div class="rec-step-params" v-if="step.params && (step.params.temperatures?.length || step.params.duree_s || step.params.cp)">
                  <span v-if="step.params.temperatures?.length" class="rp-temp">
                    🌡️ {{ step.params.temperatures.join(' › ') }} °C
                  </span>
                  <span v-if="step.params.cp" class="rp-cp">Cp {{ step.params.cp }}%</span>
                  <span v-if="step.params.duree_s" class="rp-dur">⏱️ {{ fmtDureeS(step.params.duree_s) }}</span>
                </div>
              </div>
            </div>
            <div class="rec-arrow" v-if="idx < recetteDetail.steps.length - 1">›</div>
          </div>
        </div>

        <!-- Tableau des étapes -->
        <table style="margin-top:1rem">
          <thead>
            <tr><th>Bloc</th><th>Cycle</th><th>Températures</th><th>Cp</th><th>Durée</th></tr>
          </thead>
          <tbody>
            <tr v-for="step in recetteDetail.steps" :key="step.bloc">
              <td>{{ step.bloc }}</td>
              <td>
                <span style="margin-right:0.4rem">{{ cycleIcon(step.cycle) }}</span>
                {{ step.cycle }}
              </td>
              <td class="param-val">
                {{ step.params?.temperatures?.map(t => t + '°C').join(' › ') || '—' }}
              </td>
              <td class="param-val">
                {{ step.params?.cp ? step.params.cp + ' %C' : '—' }}
              </td>
              <td class="param-val">
                {{ step.params?.duree_s ? fmtDureeS(step.params.duree_s) : '—' }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="card rec-detail-card" v-else>
        <p class="loading">Sélectionnez une recette dans la liste.</p>
      </div>
    </div>
  </template>
</template>

<style scoped>
.analyse-tabs {
  display: flex;
  gap: 0.5rem;
  background: white;
  border-radius: 12px;
  padding: 0.75rem;
  margin-bottom: 1.5rem;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06), 0 1px 2px rgba(0, 0, 0, 0.04);
}

.analyse-tab {
  position: relative;
  width: 3rem;
  height: 3rem;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.5rem;
  border: none;
  border-radius: 10px;
  background: #f0f4f8;
  cursor: pointer;
  transition: all 0.2s ease;
}

.analyse-tab::after {
  content: attr(data-tooltip);
  position: absolute;
  top: 100%;
  left: 50%;
  transform: translate(-50%, 4px);
  background: var(--brand-navy);
  color: white;
  font-size: 0.75rem;
  font-weight: 600;
  white-space: nowrap;
  padding: 0.375rem 0.75rem;
  border-radius: 6px;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.15s ease, transform 0.15s ease;
  z-index: 10;
}

.analyse-tab:hover::after {
  opacity: 1;
  transform: translate(-50%, 8px);
}

.analyse-tab:hover {
  background: #e2e8f0;
}

.analyse-tab.active {
  background: linear-gradient(135deg, var(--brand-flame) 0%, var(--brand-flame-2) 100%);
  box-shadow: 0 4px 12px rgba(37, 99, 235, 0.35);
}

/* ── Portiques ────────────────────────────────────────────────── */
.portique-notice {
  background: #fef9c3;
  border-left: 3px solid #f59e0b;
  padding: 0.625rem 0.875rem;
  border-radius: 6px;
  font-size: 0.8125rem;
  color: #92400e;
  margin-top: 0.75rem;
}

.portique-kpis {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 1rem;
  margin-bottom: 1rem;
}

.pkpi {
  background: white;
  border-radius: 12px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06);
  padding: 1.25rem;
  display: flex;
  align-items: center;
  gap: 1rem;
}

.pkpi-icon {
  width: 2.75rem; height: 2.75rem;
  border-radius: 10px;
  display: flex; align-items: center; justify-content: center;
  font-size: 1.25rem; flex-shrink: 0;
}

.pkpi-value { font-size: 1.6rem; font-weight: 700; color: #0f172a; line-height: 1; }
.pkpi-label { font-size: 0.8rem; color: #64748b; margin-top: 0.25rem; }
.pkpi-sub   { font-size: 0.7rem; color: #94a3b8; margin-top: 0.15rem; }

.portique-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.8125rem;
  color: #475569;
  margin-bottom: 1rem;
  padding: 0.75rem 1rem;
}

.portique-meta .sep { color: #cbd5e1; }

.histo-legend {
  display: flex;
  gap: 1rem;
  margin-bottom: 0.5rem;
  font-size: 0.8125rem;
  font-weight: 600;
}

.hl-green { color: #16a34a; }
.hl-amber { color: #d97706; }
.hl-red   { color: #dc2626; }

@media (max-width: 1100px) {
  .portique-kpis { grid-template-columns: repeat(2, 1fr); }
  .recettes-layout { grid-template-columns: 1fr; }
}

/* ── Catalogue recettes ─────────────────────────────────────────── */
.rec-count {
  font-size: 0.8125rem;
  color: #64748b;
  font-weight: 600;
  align-self: end;
  padding-bottom: 0.625rem;
}

.recettes-layout {
  display: grid;
  grid-template-columns: 280px 1fr;
  gap: 1rem;
  align-items: start;
}

.rec-list-card {
  padding: 0.5rem;
  max-height: 70vh;
  overflow-y: auto;
}

.rec-item {
  padding: 0.6rem 0.75rem;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.12s;
}
.rec-item:hover { background: #f1f5f9; }
.rec-item.active { background: #eff6ff; border-left: 3px solid #2563eb; }

.rec-name { font-size: 0.8125rem; font-weight: 700; color: #1e293b; }
.rec-meta { font-size: 0.7rem; color: #94a3b8; margin-top: 0.15rem; }

.rec-detail-card { min-width: 0; }

.rec-detail-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 0.25rem;
}
.rec-detail-header h3 {
  font-size: 1rem;
  font-weight: 700;
  color: #0f172a;
  margin: 0;
}

.rec-valid { font-size: 0.75rem; color: #64748b; margin: 0 0 1rem 0; }

/* Séquence visuelle */
.rec-sequence {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.25rem;
  padding: 0.875rem;
  background: #f8fafc;
  border-radius: 10px;
  border: 1px solid #e2e8f0;
}

.rec-step-wrap {
  display: flex;
  align-items: center;
  gap: 0.25rem;
}

.rec-step {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  background: white;
  border: 1.5px solid #e2e8f0;
  border-radius: 8px;
  padding: 0.4rem 0.625rem;
  transition: border-color 0.12s;
}
.rec-step:hover { border-color: #2563eb; }

.rec-step-icon { font-size: 1rem; }

.rec-step-info { display: flex; flex-direction: column; }
.rec-step-cycle { font-size: 0.75rem; font-weight: 700; color: #1e293b; white-space: nowrap; }
.rec-step-bloc  { font-size: 0.65rem; color: #94a3b8; }

.rec-step-params {
  display: flex;
  flex-wrap: wrap;
  gap: 0.3rem;
  margin-top: 0.2rem;
}

.rp-temp { font-size: 0.65rem; font-weight: 700; color: #dc2626; }
.rp-cp   { font-size: 0.65rem; font-weight: 600; color: #0ea5e9; background: #e0f2fe;
            padding: 0.05rem 0.3rem; border-radius: 4px; }
.rp-dur  { font-size: 0.65rem; color: #64748b; }

.rec-arrow { font-size: 1.1rem; color: #cbd5e1; font-weight: 700; }

/* ── Config cycles ────────────────────────────────────────────── */
.cfg-search {
  width: 100%;
  padding: 0.45rem 0.625rem;
  border: 1.5px solid #e2e8f0;
  border-radius: 8px;
  font-size: 0.8125rem;
  font-family: inherit;
  margin-bottom: 0.5rem;
}
.cfg-search:focus { outline: none; border-color: #2563eb; }

.cfg-icon { font-size: 1rem; flex-shrink: 0; }
.cfg-name { font-size: 0.8rem; font-weight: 700; color: #1e293b; }

.rec-item { display: flex; align-items: center; gap: 0.5rem; }

.bloc-cell  { font-weight: 700; color: #2563eb; text-align: center; width: 3rem; }
.param-val  { font-weight: 600; color: #1e293b; }
.param-zero { color: #cbd5e1; font-size: 0.8rem; }
.param-unit { font-weight: 400; font-size: 0.7rem; color: #94a3b8; }
</style>
