<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import api from '../api'
import { stationsLabel, stationLabel, cycleIcon } from '../constants'

use([CanvasRenderer, BarChart, LineChart, GridComponent, TooltipComponent, LegendComponent])

const router = useRouter()
const dashboard = ref(null)

function formatDate(s) {
  if (!s) return ''
  return s.replace('T', ' ').slice(0, 19)
}

function formatDuree(min) {
  if (min == null) return '—'
  const h = Math.floor(min / 60), m = Math.round(min % 60)
  return h > 0 ? `${h}h${String(m).padStart(2, '0')}` : `${m}min`
}

function openCharge(charge) {
  router.push({ name: 'fournee-detail', params: { charge } })
}

function statutIcon(statut, cycle) {
  if (statut === 'termine') return '✅'
  return cycleIcon(cycle)
}

// Couleur par cycle (hash déterministe → même cycle = même couleur)
const CHIP_COLORS = [
  { bg: '#eff6ff', color: '#1d4ed8', border: '#bfdbfe' },
  { bg: '#f5f3ff', color: '#6d28d9', border: '#ddd6fe' },
  { bg: '#fef9c3', color: '#92400e', border: '#fde68a' },
  { bg: '#f0fdfa', color: '#0f766e', border: '#99f6e4' },
  { bg: '#fff7ed', color: '#c2410c', border: '#fed7aa' },
  { bg: '#f0fdf4', color: '#15803d', border: '#bbf7d0' },
  { bg: '#ecfeff', color: '#0e7490', border: '#a5f3fc' },
  { bg: '#fee2e2', color: '#991b1b', border: '#fca5a5' },
]

function chipColor(cycle) {
  let h = 0
  for (const c of cycle) h = (h * 31 + c.charCodeAt(0)) % CHIP_COLORS.length
  return CHIP_COLORS[h]
}

function paretoOptions(items, labelKey, valueKey, valueName) {
  return {
    tooltip: { trigger: 'axis' },
    legend: { top: 0 },
    grid: { left: 60, right: 60, top: 40, bottom: 90 },
    xAxis: {
      type: 'category',
      data: items.map((i) => i[labelKey]),
      axisLabel: { rotate: 45, interval: 0, fontSize: 11 },
    },
    yAxis: [
      { type: 'value', name: valueName },
      { type: 'value', name: 'Cumulé', min: 0, max: 100, axisLabel: { formatter: '{value}%' } },
    ],
    series: [
      { type: 'bar', name: valueName, data: items.map((i) => i[valueKey]) },
      { type: 'line', name: 'Cumulé', yAxisIndex: 1, symbol: 'circle', data: items.map((i) => i.cum_pct) },
    ],
  }
}

const paretoPieces = computed(() =>
  dashboard.value ? paretoOptions(dashboard.value.top_pieces, 'piece', 'nb_lots', 'Nb OF') : {}
)
const paretoRecettes = computed(() =>
  dashboard.value
    ? paretoOptions(dashboard.value.top_recettes, 'recette', 'nb_utilisations', 'Nb utilisations')
    : {}
)

async function load() {
  const { data } = await api.get('/dashboard')
  dashboard.value = data
}

onMounted(load)
</script>

<template>
  <h1 class="page-title">Tableau de bord</h1>

  <template v-if="dashboard">

    <!-- ── KPI ───────────────────────────────────────────────────── -->
    <div class="kpi-grid" v-if="dashboard.kpis">
      <div class="kpi-card">
        <div class="kpi-icon" style="background:linear-gradient(135deg,#2563eb,#1d4ed8)">📦</div>
        <div class="kpi-body">
          <div class="kpi-value">{{ dashboard.kpis.charges_aujourd_hui }}</div>
          <div class="kpi-label">Charges aujourd'hui</div>
        </div>
      </div>
      <div class="kpi-card">
        <div class="kpi-icon" style="background:linear-gradient(135deg,#f59e0b,#d97706)">🔥</div>
        <div class="kpi-body">
          <div class="kpi-value">{{ dashboard.kpis.charges_en_cours }}</div>
          <div class="kpi-label">Charges en cours</div>
        </div>
      </div>
      <div class="kpi-card">
        <div class="kpi-icon" style="background:linear-gradient(135deg,#22c55e,#16a34a)">📅</div>
        <div class="kpi-body">
          <div class="kpi-value">{{ dashboard.kpis.passages_semaine }}</div>
          <div class="kpi-label">Passages cette semaine</div>
        </div>
      </div>
      <div class="kpi-card">
        <div class="kpi-icon" style="background:linear-gradient(135deg,#8b5cf6,#7c3aed)">⏱️</div>
        <div class="kpi-body">
          <div class="kpi-value">{{ formatDuree(dashboard.kpis.duree_moy_min) }}</div>
          <div class="kpi-label">Durée moy. passage (7j)</div>
        </div>
      </div>
    </div>

    <!-- ── Répartition cycles en cours ───────────────────────────── -->
    <div class="card" v-if="dashboard.repartition_etapes.length">
      <h3 class="section-title">Cycles en cours — répartition par cycle</h3>
      <div class="repartition-grid">
        <div
          v-for="etape in dashboard.repartition_etapes"
          :key="etape.cycle"
          class="rep-chip"
          :style="`background:${chipColor(etape.cycle).bg};color:${chipColor(etape.cycle).color};border-color:${chipColor(etape.cycle).border}`"
        >
          <span class="rep-icon">🔥</span>
          <span class="rep-label">{{ etape.cycle }}</span>
          <span class="rep-count">{{ etape.nb }}</span>
        </div>
      </div>
    </div>

    <!-- ── Ligne 1 : Dernières charges + Top 10 pièces ───────────── -->
    <div class="two-col">
      <div class="card" v-if="dashboard.dernieres_charges.length">
        <div class="card-header">
          <h3 class="card-title">Dernières charges</h3>
        </div>
        <table>
          <thead>
            <tr>
              <th class="th-icon"></th><th>Charge</th><th>Date création</th><th>Fours</th><th>OF</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="c in dashboard.dernieres_charges" :key="c.charge"
                @click="openCharge(c.charge)" style="cursor:pointer">
              <td class="td-icon">{{ statutIcon(c.statut, c.cycle_en_cours) }}</td>
              <td>{{ c.charge }}</td>
              <td>{{ c.date_creat }}</td>
              <td>{{ stationsLabel(c.stations) }}</td>
              <td class="td-lots">{{ c.lots }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="card" v-if="dashboard.top_pieces.length">
        <div class="card-header">
          <h3 class="card-title">Top 10 références pièces</h3>
        </div>
        <v-chart :option="paretoPieces" autoresize style="height: 280px;" />
        <table>
          <thead>
            <tr>
              <th>Référence</th><th>Dénomination</th><th>Nuance</th>
              <th>Nb OF</th><th>Cumulé</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="p in dashboard.top_pieces" :key="p.piece">
              <td>{{ p.piece }}</td><td>{{ p.denomination }}</td><td>{{ p.nuance }}</td>
              <td>{{ p.nb_lots }}</td><td>{{ p.cum_pct }}%</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- ── Ligne 2 : Top 10 recettes + Programme hebdo ───────────── -->
    <div class="two-col">
      <div class="card" v-if="dashboard.top_recettes.length">
        <div class="card-header">
          <h3 class="card-title">Top 10 recettes</h3>
        </div>
        <v-chart :option="paretoRecettes" autoresize style="height: 280px;" />
      </div>

      <div class="card" v-if="dashboard.hebdo.length">
        <div class="card-header">
          <h3 class="card-title">Programme hebdomadaire des fours</h3>
        </div>
        <table>
          <thead>
            <tr>
              <th>Four</th><th>Jour</th><th>Heure</th><th>État</th>
              <th>Genre</th><th>Cons. 1</th><th>Cons. 2</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(h, idx) in dashboard.hebdo" :key="idx">
              <td>{{ stationLabel(h.station) }}</td>
              <td>{{ h.jour }}</td><td>{{ h.heure }}</td><td>{{ h.mar_arr_att }}</td>
              <td>{{ h.genre_enr }}</td><td>{{ h.cons1 }}</td><td>{{ h.cons2 }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- ── Entretien ──────────────────────────────────────────────── -->
    <div class="card" v-if="dashboard.entretien.length">
      <div class="card-header">
        <h3 class="card-title">Plan d'entretien — 10 actions les plus fréquentes</h3>
      </div>
      <table>
        <thead>
          <tr>
            <th>Position</th><th>Action</th><th>Fréquence</th>
            <th>Dernière exécution</th><th>Utilisateur</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(e, idx) in dashboard.entretien" :key="idx">
            <td>{{ e.position }}</td><td>{{ e.action }}</td><td>{{ e.frequence }}</td>
            <td>{{ formatDate(e.derniere_date) }}</td><td>{{ e.utilisateur }}</td>
          </tr>
        </tbody>
      </table>
    </div>

  </template>
</template>

<style scoped>
/* ── KPI ──────────────────────────────────────────────────────── */
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 1rem;
  margin-bottom: 1.5rem;
}

/* Compacité générale du dashboard */
:deep(.card) { padding: 0.875rem; margin-bottom: 0.75rem; }
:deep(.card-header) { margin-bottom: 0.625rem; padding-bottom: 0.5rem; }
:deep(th), :deep(td) { padding: 0.4rem 0.75rem; font-size: 0.8125rem; }

.kpi-grid { margin-bottom: 0.75rem; gap: 0.75rem; }

.kpi-card {
  background: white;
  border-radius: 12px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04);
  padding: 0.875rem;
  display: flex;
  align-items: center;
  gap: 1rem;
}

.kpi-icon {
  width: 2.75rem;
  height: 2.75rem;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.25rem;
  flex-shrink: 0;
}

.kpi-value { font-size: 1.75rem; font-weight: 700; color: #0f172a; line-height: 1; }
.kpi-label { font-size: 0.8125rem; color: #64748b; margin-top: 0.25rem; }

/* ── Répartition ──────────────────────────────────────────────── */
.section-title {
  font-size: 0.8125rem;
  font-weight: 700;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  margin: 0 0 1rem 0;
}

.repartition-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.rep-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.4rem 0.875rem;
  border-radius: 20px;
  font-size: 0.8125rem;
  font-weight: 500;
  border: 1.5px solid transparent;
}

.rep-icon { font-size: 0.875rem; }
.rep-label { font-weight: 600; }
.rep-count {
  font-weight: 700;
  font-size: 0.875rem;
  margin-left: 0.2rem;
  background: rgba(0,0,0,0.1);
  border-radius: 10px;
  padding: 0 0.4rem;
}

/* ── Deux colonnes ────────────────────────────────────────────── */
.two-col {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.75rem;
  margin-bottom: 0.75rem;
}

/* Les .card dans .two-col ne doublent pas leur margin-bottom */
.two-col .card { margin-bottom: 0; }

/* OF en police réduite */
:deep(.td-lots) { font-size: 0.7rem; color: #64748b; }

@media (max-width: 1100px) {
  .kpi-grid { grid-template-columns: repeat(2, 1fr); }
  .two-col  { grid-template-columns: 1fr; }
}
</style>
