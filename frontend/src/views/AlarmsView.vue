<script setup>
import { ref, computed, onMounted } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, LineChart, ScatterChart } from 'echarts/charts'
import {
  GridComponent, TooltipComponent, LegendComponent,
  DataZoomComponent, MarkLineComponent,
} from 'echarts/components'
import VChart from 'vue-echarts'
import api from '../api'

// Libellé lisible : description si dispo, sinon code
function label(code, description) {
  return description && description.trim() ? description : (code ?? '—')
}

use([CanvasRenderer, BarChart, LineChart, ScatterChart, GridComponent,
     TooltipComponent, LegendComponent, DataZoomComponent, MarkLineComponent])

// ── État ──────────────────────────────────────────────────────────
const stats  = ref(null)
const items  = ref([])
const total  = ref(0)
const codes  = ref([])
const limit  = 100
const offset = ref(0)

const filters = ref({ code: '', q: '', date_from: '', date_to: '' })

// ── Helpers ───────────────────────────────────────────────────────
function formatDate(s) {
  if (!s) return '—'
  return s.replace('T', ' ').slice(0, 19)
}

function formatDuree(s) {
  if (s == null || s < 0) return '—'
  if (s < 60)   return `${s}s`
  const m = Math.floor(s / 60), sec = s % 60
  if (m < 60)   return `${m}m${sec > 0 ? String(sec).padStart(2, '0') + 's' : ''}`
  const h = Math.floor(m / 60), min = m % 60
  return `${h}h${String(min).padStart(2, '0')}`
}

// Classe de sévérité basée sur la durée (EEMUA 191)
function severityClass(duree) {
  if (duree == null)  return 'sev-unknown'
  if (duree < 300)    return 'sev-ok'      // < 5 min
  if (duree < 3600)   return 'sev-warn'    // 5 min – 1 h
  return 'sev-crit'                         // > 1 h  (standing alarm)
}

// ── Charts ────────────────────────────────────────────────────────
// Couleur par durée (ISA-18.2 : vert=court, orange=moyen, rouge=long)
function durationColor(s) {
  if (s == null || s < 300)  return '#22c55e'  // < 5 min
  if (s < 3600)               return '#f59e0b'  // < 1 h
  return '#ef4444'                               // standing alarm
}

// Graphique : alarmes par jour (bar) + ligne de tendance mobile 7j
const chartDailyOption = computed(() => {
  if (!stats.value?.par_jour?.length) return {}
  const days  = stats.value.par_jour.map(d => d.jour)
  const nbArr = stats.value.par_jour.map(d => d.nb)

  // Moyenne mobile 7 jours
  const ma7 = nbArr.map((_, i) => {
    const slice = nbArr.slice(Math.max(0, i - 6), i + 1)
    return Math.round((slice.reduce((a, b) => a + b, 0) / slice.length) * 10) / 10
  })

  return {
    tooltip: { trigger: 'axis' },
    legend: { data: ['Alarmes/jour', 'Moy. 7j'], top: 0 },
    grid: { top: 40, left: 50, right: 20, bottom: 60 },
    xAxis: { type: 'category', data: days, axisLabel: { rotate: 30, fontSize: 10 } },
    yAxis: { type: 'value', name: 'Nb' },
    dataZoom: [{ type: 'inside' }, { type: 'slider' }],
    series: [
      {
        name: 'Alarmes/jour', type: 'bar',
        data: nbArr, itemStyle: { color: '#ef4444', opacity: 0.7 },
      },
      {
        name: 'Moy. 7j',
        type: 'line', smooth: true, showSymbol: false,
        data: ma7,
        lineStyle: { color: '#2563eb', width: 2 },
        itemStyle: { color: '#2563eb' },
      },
    ],
  }
})

// Graphique : timeline scatter (x=date, y=code, taille∝log(durée), couleur=sévérité)
const chartTimelineOption = computed(() => {
  if (!stats.value?.timeline?.length) return {}

  const allCodes = [...new Set(stats.value.timeline.map(d => d.code))].sort()
  const codeIdx  = Object.fromEntries(allCodes.map((c, i) => [c, i]))

  const COLORS = ['#2563eb','#f59e0b','#22c55e','#ef4444','#8b5cf6',
                  '#0ea5e9','#f97316','#10b981','#ec4899','#84cc16']

  // Un dataset par code pour la légende
  const seriesMap = {}
  for (const d of stats.value.timeline) {
    if (!seriesMap[d.code]) seriesMap[d.code] = []
    seriesMap[d.code].push([
      d.tps_apparition,
      d.code,
      d.duree_s ?? 0,
    ])
  }

  const series = Object.entries(seriesMap).map(([code, data], i) => ({
    name: code,
    type: 'scatter',
    data,
    symbolSize: (v) => Math.max(4, Math.min(20, Math.log1p(v[2] / 60) * 4 + 4)),
    itemStyle: { color: COLORS[i % COLORS.length], opacity: 0.75 },
    tooltip: {
      formatter: (p) =>
        `<b>${p.seriesName}</b><br/>${formatDate(p.data[0])}<br/>Durée : ${formatDuree(p.data[2])}`,
    },
  }))

  return {
    tooltip: { trigger: 'item' },
    legend: { data: Object.keys(seriesMap), top: 0, type: 'scroll' },
    grid: { top: 50, left: 140, right: 20, bottom: 60 },
    xAxis: { type: 'time' },
    yAxis: {
      type: 'category',
      data: allCodes,
      axisLabel: { fontSize: 10, fontFamily: 'monospace' },
    },
    dataZoom: [{ type: 'inside', xAxisIndex: 0 }, { type: 'slider', xAxisIndex: 0 }],
    series,
  }
})

// Graphique : Pareto top codes
const chartParetoOption = computed(() => {
  if (!stats.value?.top5?.length) return {}
  const rows    = [...stats.value.top5].sort((a, b) => a.nb - b.nb) // ascending → horizontal
  const codes_  = rows.map(r => r.code)
  const nb_     = rows.map(r => r.nb)
  const maxNb   = Math.max(...nb_)
  return {
    tooltip: { trigger: 'axis' },
    grid: { top: 10, left: 140, right: 30, bottom: 20 },
    xAxis: { type: 'value' },
    yAxis: { type: 'category', data: codes_, axisLabel: { fontSize: 10, fontFamily: 'monospace' } },
    series: [{
      type: 'bar',
      data: nb_.map((v, i) => ({
        value: v,
        itemStyle: { color: `hsl(${210 - Math.round(v / maxNb * 180)},80%,50%)` },
        label: { show: true, position: 'right', fontSize: 11, formatter: `{c}` },
      })),
    }],
  }
})

// ── Chargement ────────────────────────────────────────────────────
async function loadStats() {
  const { data } = await api.get('/alarmes/stats')
  stats.value = data
}

async function loadCodes() {
  const { data } = await api.get('/alarmes/codes')
  codes.value = data
}

async function loadAlarmes() {
  const params = { limit, offset: offset.value }
  if (filters.value.code)      params.code      = filters.value.code
  if (filters.value.q)         params.q         = filters.value.q
  if (filters.value.date_from) params.date_from = filters.value.date_from
  if (filters.value.date_to)   params.date_to   = filters.value.date_to
  const { data } = await api.get('/alarmes', { params })
  items.value  = data.items
  total.value  = data.total
}

const listRef = ref(null)

function applyFilters() {
  offset.value = 0
  loadAlarmes().then(() => {
    listRef.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  })
}
function prevPage() { offset.value = Math.max(0, offset.value - limit); loadAlarmes() }
function nextPage() { if (offset.value + limit < total.value) { offset.value += limit; loadAlarmes() } }
function filterByCode(c) { filters.value.code = filters.value.code === c ? '' : c; applyFilters() }

onMounted(() => { loadStats(); loadCodes(); loadAlarmes() })
</script>

<template>
  <h1 class="page-title">Alarmes CITECT</h1>

  <template v-if="stats">
    <!-- ── KPI ─────────────────────────────────────────────────── -->
    <div class="kpi-row">
      <div class="kpi">
        <div class="kpi-icon" style="background:linear-gradient(135deg,#ef4444,#dc2626)">🔴</div>
        <div>
          <div class="kpi-val">{{ stats.total.toLocaleString('fr-FR') }}</div>
          <div class="kpi-lbl">Total alarmes</div>
        </div>
      </div>
      <div class="kpi">
        <div class="kpi-icon" style="background:linear-gradient(135deg,#f59e0b,#d97706)">⏱️</div>
        <div>
          <div class="kpi-val">{{ formatDuree(stats.duree_moy) }}</div>
          <div class="kpi-lbl">Durée moyenne</div>
        </div>
      </div>
      <div class="kpi">
        <div class="kpi-icon" style="background:linear-gradient(135deg,#8b5cf6,#7c3aed)">🔥</div>
        <div>
          <div class="kpi-val" style="font-size:0.9rem;line-height:1.3">{{ label(stats.top5[0]?.code, stats.top5[0]?.description) }}</div>
          <div class="kpi-lbl">Plus fréquente ({{ stats.top5[0]?.nb }} occur.)</div>
        </div>
      </div>
      <div class="kpi">
        <div class="kpi-icon" style="background:linear-gradient(135deg,#dc2626,#991b1b)">⚠️</div>
        <div>
          <div class="kpi-val">{{ formatDuree(stats.duree_max) }}</div>
          <div class="kpi-lbl">Durée max (standing alarm)</div>
        </div>
      </div>
    </div>

    <!-- ── Top 5 + dernières ──────────────────────────────────── -->
    <div class="top-row">
      <div class="card">
        <h3 class="section-h">Top 5 — codes les plus fréquents</h3>
        <v-chart :option="chartParetoOption" autoresize style="height:160px" />
        <table style="margin-top:0.75rem">
          <thead><tr><th>Libellé</th><th>Nb</th><th>Durée moy.</th><th>Max</th></tr></thead>
          <tbody>
            <tr v-for="r in stats.top5" :key="r.code"
                style="cursor:pointer" @click="filterByCode(r.code)"
                :class="{ 'row-active': filters.code === r.code }">
              <td>
                <div class="lbl-primary">{{ label(r.code, r.description) }}</div>
                <span class="al-code-sm">{{ r.code }}</span>
              </td>
              <td>{{ r.nb }}</td>
              <td>{{ formatDuree(r.duree_moy) }}</td>
              <td :class="severityClass(r.duree_max)">{{ formatDuree(r.duree_max) }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="card">
        <h3 class="section-h">5 dernières alarmes</h3>
        <table>
          <thead><tr><th>Date</th><th>Durée</th><th>Libellé</th></tr></thead>
          <tbody>
            <tr v-for="a in stats.dernieres" :key="a.tps_apparition"
                style="cursor:pointer" @click="filterByCode(a.code)"
                :class="{ 'row-active': filters.code === a.code }">
              <td class="al-ts">{{ formatDate(a.tps_apparition) }}</td>
              <td :class="severityClass(a.duree_s)">{{ formatDuree(a.duree_s) }}</td>
              <td>
                <div class="lbl-primary">{{ label(a.code, a.description) }}</div>
                <span class="al-code-sm">{{ a.code }}</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- ── Taux journalier ────────────────────────────────────── -->
    <div class="card">
      <h3 class="section-h">
        Taux d'alarmes journalier
        <span class="section-note">Barre = nb/jour · Ligne = moyenne mobile 7 jours</span>
      </h3>
      <v-chart :option="chartDailyOption" autoresize style="height:260px" />
    </div>

    <!-- ── Timeline scatter ───────────────────────────────────── -->
    <div class="card">
      <h3 class="section-h">
        Répartition temporelle par code (top 10)
        <span class="section-note">
          Taille du point ∝ durée · 🟢 &lt;5 min · 🟡 5 min–1 h · 🔴 &gt;1 h (standing alarm)
        </span>
      </h3>
      <v-chart :option="chartTimelineOption" autoresize style="height:340px" />
    </div>
  </template>

  <!-- ── Liste filtrée ────────────────────────────────────────── -->
  <div class="two-col-layout" ref="listRef">
    <div class="card codes-panel">
      <div class="codes-title">Codes alarme</div>
      <div
        v-for="c in codes" :key="c.code"
        class="code-item"
        :class="{ active: filters.code === c.code }"
        @click="filterByCode(c.code)"
      >
        <div class="code-name">{{ label(c.code, c.description) }}</div>
        <div class="code-desc">{{ c.code }}</div>
        <div class="code-nb">{{ c.nb }}</div>
      </div>
    </div>

    <div class="main-panel">
      <div class="filters">
        <label>
          Recherche
          <input type="text" v-model="filters.q" @keyup.enter="applyFilters"
                 placeholder="code, description…" />
        </label>
        <label>Du <input type="date" v-model="filters.date_from" /></label>
        <label>Au <input type="date" v-model="filters.date_to" /></label>
        <button class="btn btn-primary" @click="applyFilters">Filtrer</button>
        <button class="btn btn-secondary"
                @click="filters = { code:'', q:'', date_from:'', date_to:'' }; applyFilters()">
          Réinitialiser
        </button>
      </div>

      <div class="card">
        <div class="list-header">
          <span class="total-label">
            {{ total.toLocaleString('fr-FR') }} alarme{{ total > 1 ? 's' : '' }}
            <template v-if="filters.code"> · code <b>{{ filters.code }}</b></template>
          </span>
        </div>
        <table>
          <thead>
            <tr><th>Apparition</th><th>Durée</th><th>Libellé</th></tr>
          </thead>
          <tbody>
            <tr v-for="a in items" :key="a.id">
              <td class="al-ts">{{ formatDate(a.tps_apparition) }}</td>
              <td :class="severityClass(a.duree_s)">{{ formatDuree(a.duree_s) }}</td>
              <td>
                <div class="lbl-primary">{{ label(a.code, a.description) }}</div>
                <span class="al-code-sm">{{ a.code }}</span>
              </td>
            </tr>
          </tbody>
        </table>
        <div class="pagination" v-if="total > limit">
          <button class="btn btn-secondary" @click="prevPage" :disabled="offset === 0">Précédent</button>
          <span>{{ offset + 1 }} – {{ Math.min(offset + limit, total) }} / {{ total }}</span>
          <button class="btn btn-secondary" @click="nextPage" :disabled="offset + limit >= total">Suivant</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* ── KPI ──────────────────────────────────────────────────────── */
.kpi-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 1rem;
  margin-bottom: 1rem;
}

.kpi {
  background: white;
  border-radius: 12px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06);
  padding: 1rem;
  display: flex;
  align-items: center;
  gap: 0.875rem;
}

.kpi-icon {
  width: 2.75rem; height: 2.75rem;
  border-radius: 10px;
  display: flex; align-items: center; justify-content: center;
  font-size: 1.25rem; flex-shrink: 0;
}

.kpi-val { font-size: 1.5rem; font-weight: 700; color: #0f172a; line-height: 1.1; }
.kpi-lbl { font-size: 0.75rem; color: #64748b; margin-top: 0.2rem; }

/* ── Sections ─────────────────────────────────────────────────── */
.top-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
  margin-bottom: 1rem;
}

.section-h {
  font-size: 0.875rem;
  font-weight: 700;
  color: #0f172a;
  margin: 0 0 0.75rem 0;
  display: flex;
  align-items: baseline;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.section-note {
  font-size: 0.75rem;
  font-weight: 400;
  color: #64748b;
}

/* Sévérité durée */
.sev-ok      { color: #16a34a; font-weight: 600; }
.sev-warn    { color: #d97706; font-weight: 600; }
.sev-crit    { color: #dc2626; font-weight: 700; }
.sev-unknown { color: #94a3b8; }

/* ── Liste ────────────────────────────────────────────────────── */
.two-col-layout {
  display: grid;
  grid-template-columns: 240px 1fr;
  gap: 1rem;
  align-items: start;
}

.codes-panel { padding: 0.75rem; position: sticky; top: 1rem; }
.codes-title {
  font-size: 0.75rem; font-weight: 700; text-transform: uppercase;
  letter-spacing: 0.05em; color: #64748b; margin: 0 0 0.5rem 0.25rem;
}

.code-item {
  display: flex; flex-direction: column;
  padding: 0.45rem 0.625rem;
  border-radius: 8px; cursor: pointer; transition: background 0.12s;
  position: relative;
}
.code-item:hover  { background: #f1f5f9; }
.code-item.active { background: #eff6ff; border-left: 3px solid #2563eb; }

.code-name { font-size: 0.8rem; font-weight: 700; color: #1e293b; font-family: monospace; }
.code-desc { font-size: 0.7rem; color: #64748b; white-space: nowrap;
             overflow: hidden; text-overflow: ellipsis; margin-top: 0.1rem; }
.code-nb   { position: absolute; right: 0.5rem; top: 50%; transform: translateY(-50%);
             font-size: 0.75rem; font-weight: 700; color: #94a3b8; }

.main-panel  { min-width: 0; }
.list-header { margin-bottom: 0.625rem; }
.total-label { font-size: 0.875rem; color: #64748b; font-weight: 600; }

/* Ligne sélectionnée dans les tables de stats */
:deep(tr.row-active td) { background: #eff6ff !important; }

.al-ts      { font-size: 0.8rem; color: #475569; white-space: nowrap; }
.al-code    { font-size: 0.75rem; font-family: monospace; background: #fee2e2;
              color: #991b1b; padding: 0.1rem 0.4rem; border-radius: 4px; }
.al-code-sm { font-size: 0.7rem; font-family: monospace; color: #94a3b8;
              display: inline-block; margin-top: 0.15rem; }
.lbl-primary { font-size: 0.8125rem; font-weight: 600; color: #1e293b; }

@media (max-width: 1100px) {
  .kpi-row       { grid-template-columns: repeat(2, 1fr); }
  .top-row       { grid-template-columns: 1fr; }
  .two-col-layout { grid-template-columns: 1fr; }
}
</style>
