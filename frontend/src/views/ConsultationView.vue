<script setup>
import { ref, computed, onMounted } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
  DataZoomComponent,
} from 'echarts/components'
import VChart from 'vue-echarts'
import api from '../api'
import { stationLabel, CATEGORY_LABELS, CATEGORY_ORDER } from '../constants'
import MultiSelectDropdown from '../components/MultiSelectDropdown.vue'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, LegendComponent, DataZoomComponent])

// ── Équipements ───────────────────────────────────────────────────
const fours             = ref([])
const selectedStations  = ref([])

const foursOptions = computed(() =>
  fours.value.map((f) => ({ id: f.station, label: stationLabel(f.station) }))
)

// ── Tags par catégorie : { temperature: [...], puissance: [...] }
const availableTags      = ref({})   // options enrichies avec .label
// Sélection par catégorie : { temperature: [id,...], puissance: [...] }
const categorySelections = ref({})

const selectedTagIds = computed(() =>
  Object.values(categorySelections.value).flat()
)

// ── Période ───────────────────────────────────────────────────────
const PERIODS = [
  { label: 'Dernière heure', key: '1h',  seconds: 3600 },
  { label: '24 h',           key: '24h', seconds: 86400 },
  { label: '7 jours',        key: '7d',  seconds: 7 * 86400 },
  { label: '30 jours',       key: '30d', seconds: 30 * 86400 },
  { label: 'Personnalisé',   key: 'custom' },
]
const activePeriod = ref('24h')
const customStart  = ref('')
const customEnd    = ref('')

function toDatetimeLocal(d) {
  return new Date(d - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16)
}

function setPeriod(key) {
  activePeriod.value = key
  if (key !== 'custom') {
    const p   = PERIODS.find((x) => x.key === key)
    const end = new Date()
    const start = new Date(end - p.seconds * 1000)
    customStart.value = toDatetimeLocal(start)
    customEnd.value   = toDatetimeLocal(end)
    loadSeries()
  }
}

// ── Données ───────────────────────────────────────────────────────
const seriesData = ref(null)
const loading    = ref(false)

async function loadFours() {
  const { data } = await api.get('/fours')
  fours.value = data
  if (data.length) {
    selectedStations.value = [data[0].station]
    await loadTags()
    setPeriod('24h')
  }
}

async function loadTags() {
  if (!selectedStations.value.length) return
  categorySelections.value = {}
  availableTags.value      = {}
  seriesData.value         = null
  const { data } = await api.get('/consultation/tags', {
    params: { stations: selectedStations.value.join(',') },
  })
  const multi = selectedStations.value.length > 1
  const grouped = {}
  for (const t of data) {
    const label = multi ? `${stationLabel(t.station)} · ${t.variable}` : t.variable
    ;(grouped[t.category] ??= []).push({ ...t, label })
  }
  availableTags.value = grouped
  for (const [cat, tags] of Object.entries(grouped)) {
    categorySelections.value[cat] = tags.map((t) => t.id)
  }
}

async function loadSeries() {
  if (!selectedStations.value.length || !selectedTagIds.value.length) return
  loading.value = true
  try {
    const { data } = await api.get('/consultation/series', {
      params: {
        tag_ids: selectedTagIds.value.join(','),
        start:   new Date(customStart.value).toISOString(),
        end:     new Date(customEnd.value).toISOString(),
      },
    })
    seriesData.value = data
  } finally {
    loading.value = false
  }
}

// ── Graphiques ────────────────────────────────────────────────────
const orderedCategories = computed(() => {
  if (!seriesData.value) return []
  const cats = Object.keys(seriesData.value.categories)
  return [
    ...CATEGORY_ORDER.filter((c) => cats.includes(c)),
    ...cats.filter((c) => !CATEGORY_ORDER.includes(c)),
  ]
})

const COLORS = ['#2563eb', '#f59e0b', '#10b981', '#ef4444', '#8b5cf6',
                '#0ea5e9', '#f97316', '#14b8a6', '#ec4899', '#84cc16']

function seriesLabel(tag) {
  return selectedStations.value.length > 1
    ? `${stationLabel(tag.station)} · ${tag.variable}`
    : tag.variable
}

function buildChartOption(tags) {
  return {
    tooltip:  { trigger: 'axis' },
    legend:   { data: tags.map(seriesLabel), top: 0, type: 'scroll' },
    grid:     { top: 40, left: 60, right: 30, bottom: 60 },
    xAxis:    { type: 'time' },
    yAxis:    { type: 'value' },
    dataZoom: [{ type: 'inside' }, { type: 'slider' }],
    series: tags.map((t, i) => ({
      name:       seriesLabel(t),
      type:       'line',
      showSymbol: false,
      color:      COLORS[i % COLORS.length],
      data:       t.points,
    })),
  }
}

onMounted(loadFours)
</script>

<template>
  <h1 class="page-title">Consultation</h1>

  <!-- ─── Contrôles ──────────────────────────────────────────────── -->
  <div class="card">

    <!-- Sélecteurs alignés : Équipement + une liste multiple par catégorie -->
    <div class="selectors-row">
      <label class="sel-label">
        Équipement
        <MultiSelectDropdown
          :options="foursOptions"
          v-model="selectedStations"
          @close="loadTags"
        />
      </label>

      <template v-for="cat in CATEGORY_ORDER" :key="cat">
        <label class="sel-label" v-if="availableTags[cat]">
          {{ CATEGORY_LABELS[cat] || cat }}
          <MultiSelectDropdown
            :options="availableTags[cat]"
            v-model="categorySelections[cat]"
          />
        </label>
      </template>
    </div>

    <!-- Période -->
    <div class="period-row">
      <span class="period-label">Période</span>
      <div class="period-btns">
        <button
          v-for="p in PERIODS"
          :key="p.key"
          class="btn"
          :class="activePeriod === p.key ? 'btn-primary' : 'btn-secondary'"
          @click="setPeriod(p.key)"
        >{{ p.label }}</button>
      </div>
    </div>

    <!-- Plage date/heure + bouton Afficher -->
    <div class="range-row">
      <label class="sel-label">
        Du
        <input type="datetime-local" v-model="customStart" />
      </label>
      <label class="sel-label">
        Au
        <input type="datetime-local" v-model="customEnd" />
      </label>
      <button
        class="btn btn-primary afficher-btn"
        :disabled="!selectedTagIds.length || loading"
        @click="loadSeries"
      >Afficher</button>
    </div>

  </div>

  <!-- ─── Graphiques ─────────────────────────────────────────────── -->
  <p v-if="loading" class="loading">Chargement des données…</p>

  <template v-else-if="seriesData">
    <div class="card" v-for="cat in orderedCategories" :key="cat">
      <h2>{{ CATEGORY_LABELS[cat] || cat }}</h2>
      <v-chart
        :option="buildChartOption(seriesData.categories[cat])"
        autoresize
        style="height: 320px;"
      />
    </div>
    <p v-if="!orderedCategories.length">Aucune donnée pour la sélection et la période choisies.</p>
  </template>
</template>

<style scoped>
/* ─── Ligne de sélecteurs ─────────────────────────────────────── */
.selectors-row {
  display: flex;
  gap: 1rem;
  align-items: end;
  flex-wrap: wrap;
  margin-bottom: 1.25rem;
}

.sel-label {
  display: flex;
  flex-direction: column;
  font-size: 0.8125rem;
  font-weight: 600;
  color: #475569;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  gap: 0.375rem;
}

.sel-label select,
.sel-label input[type="datetime-local"] {
  padding: 0.5rem 0.75rem;
  border: 1.5px solid #e2e8f0;
  border-radius: 8px;
  font-size: 0.875rem;
  font-family: inherit;
  background: white;
  color: #0f172a;
  transition: border-color 0.2s, box-shadow 0.2s;
}

.sel-label select:focus,
.sel-label input[type="datetime-local"]:focus {
  outline: none;
  border-color: #2563eb;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
}

/* ─── Période ─────────────────────────────────────────────────── */
.period-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
  padding: 1rem 0;
  border-top: 1px solid #f1f5f9;
}

.period-label {
  font-size: 0.8125rem;
  font-weight: 600;
  color: #475569;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.period-btns { display: flex; gap: 0.5rem; flex-wrap: wrap; }

/* ─── Plage + Afficher ────────────────────────────────────────── */
.range-row {
  display: flex;
  align-items: end;
  gap: 1rem;
  flex-wrap: wrap;
  padding-top: 0.25rem;
}

.afficher-btn { align-self: end; }
</style>
