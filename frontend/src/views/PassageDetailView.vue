<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
  DataZoomComponent,
  MarkLineComponent,
} from 'echarts/components'
import VChart from 'vue-echarts'
import api from '../api'
import { stationLabel, CATEGORY_LABELS, CATEGORY_ORDER, cleanCycle } from '../constants'



use([
  CanvasRenderer,
  LineChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  DataZoomComponent,
  MarkLineComponent,
])

const props = defineProps({
  charge: { type: String, required: true },
  passageId: { type: [String, Number], required: true },
})

const router = useRouter()

const series              = ref(null)
const chargeMeta          = ref(null)
const toleranceC          = ref(10.0)    // tolérance en °C, depuis config
const configuredConsignes = ref(null)    // null = auto | [760, 871] = filtré

function formatDate(s) {
  if (!s) return ''
  return s.replace('T', ' ').slice(0, 19)
}

function formatDuration(ms) {
  if (ms === null || ms === undefined || ms < 0) return '-'
  const totalMin = Math.round(ms / 60000)
  const h = Math.floor(totalMin / 60)
  const m = totalMin % 60
  return `${h}h${String(m).padStart(2, '0')}`
}

// Detection des paliers de consigne et calcul du temps de maintien jusqu'a la fin du traitement
// La tolérance est chargée depuis param_seuils_temperature (en °C absolus)
const TEMP_PALIER_MIN_DURATION_MS = 10 * 60 * 1000
const TEMP_PALIER_MIN_VALUE = 50

const temperaturePaliers = computed(() => {
  if (!series.value) return []
  const tempTags = series.value.categories.temperature || []
  const consTag = tempTags.find((t) => t.variable === 'cons_temp')
  if (!consTag || !consTag.points.length) return []

  const measureTags = tempTags.filter(
    (t) => t.variable !== 'cons_temp'
  )
  if (!measureTags.length) return []

  const tpsFin = new Date(series.value.tps_fin).getTime()

  const points = consTag.points
  const paliers = []
  let i = 0
  while (i < points.length) {
    const value = points[i][1]
    const tolerance = toleranceC.value
    let j = i
    while (j + 1 < points.length && Math.abs(points[j + 1][1] - value) <= tolerance) {
      j++
    }
    const tStart = new Date(points[i][0]).getTime()
    const tEnd = new Date(points[j][0]).getTime()
    if (value >= TEMP_PALIER_MIN_VALUE && tEnd - tStart >= TEMP_PALIER_MIN_DURATION_MS) {
      paliers.push({ value, tStart })
    }
    i = j + 1
  }

  const results = paliers.map((palier) => {
    const tolerance = toleranceC.value
    let tAtteinte = null
    let tAtteinteStr = null
    let allReached = true
    for (const tag of measureTags) {
      const reached = tag.points.find(
        (p) => new Date(p[0]).getTime() >= palier.tStart && p[1] >= palier.value - tolerance
      )
      if (!reached) {
        allReached = false
        break
      }
      const t = new Date(reached[0]).getTime()
      if (tAtteinte === null || t > tAtteinte) {
        tAtteinte = t
        tAtteinteStr = reached[0]
      }
    }
    return {
      consigne: Math.round(palier.value),
      atteinte: allReached ? tAtteinteStr : null,
      atteinteMs: allReached ? tAtteinte : null,
      duree: allReached ? tpsFin - tAtteinte : null,
    }
  })

  return results.map((p, idx) => {
    let interPalier = null
    if (p.atteinteMs !== null) {
      const next = results[idx + 1]
      const nextMs = next ? next.atteinteMs : tpsFin
      if (nextMs !== null) {
        interPalier = nextMs - p.atteinteMs
      }
    }
    return { consigne: p.consigne, atteinte: p.atteinte, duree: p.duree, interPalier }
  }).filter((p) => {
    // Pas de règle configurée = pas de paliers affichés
    if (configuredConsignes.value === null) return false
    return configuredConsignes.value.some((c) => Math.abs(c - p.consigne) <= toleranceC.value)
  })
})

const chartOptions = computed(() => {
  if (!series.value) return {}
  const options = {}
  const categories = Object.keys(series.value.categories)
  const orderedCategories = [
    ...CATEGORY_ORDER.filter((c) => categories.includes(c)),
    ...categories.filter((c) => !CATEGORY_ORDER.includes(c)),
  ]
  for (const category of orderedCategories) {
    const tags = series.value.categories[category]
    const filteredTags =
      tags
    const chartSeries = filteredTags.map((t) => ({
      name: t.variable,
      type: 'line',
      showSymbol: false,
      data: t.points,
    }))

    if (category === 'temperature' && chartSeries.length) {
      const markData = temperaturePaliers.value
        .filter((p) => p.atteinte)
        .map((p) => ({
          xAxis: p.atteinte,
          label: { formatter: `${p.consigne}°C\n${formatDuration(p.duree)}` },
        }))
      if (markData.length) {
        chartSeries[0].markLine = {
          symbol: 'none',
          animation: false,
          lineStyle: { type: 'dashed', color: '#e53e3e' },
          label: { color: '#e53e3e', position: 'insideEndTop' },
          data: markData,
        }
      }
    }

    options[category] = {
      tooltip: { trigger: 'axis' },
      legend: { data: filteredTags.map((t) => t.variable), top: 0 },
      grid: { top: 40, left: 60, right: 30, bottom: 60 },
      xAxis: { type: 'time' },
      yAxis: { type: 'value' },
      dataZoom: [{ type: 'inside' }, { type: 'slider' }],
      series: chartSeries,
    }
  }
  return options
})

async function load() {
  const [seriesResp, metaResp] = await Promise.all([
    api.get(`/fournees/${props.charge}/passages/${props.passageId}/series`),
    api.get(`/fournees/${props.charge}/meta`),
  ])
  series.value    = seriesResp.data
  chargeMeta.value = metaResp.data
  const data = seriesResp.data
  // Charger la tolérance et les paliers configurés pour ce cycle
  if (data.cycle) {
    try {
      const [tol, pal] = await Promise.all([
        api.get('/parametrage/seuils/resolve',  { params: { cycle: data.cycle } }),
        api.get('/parametrage/paliers/resolve', { params: { cycle: data.cycle } }),
      ])
      toleranceC.value          = tol.data.tolerance_c
      configuredConsignes.value = pal.data.consignes   // null ou [760, 871]
    } catch { /* garde les valeurs par défaut */ }
  }
}

onMounted(load)
</script>

<template>
  <button class="btn btn-secondary" @click="router.push({ name: 'fournee-detail', params: { charge: props.charge } })">
    &larr; Retour à la charge {{ props.charge }}
  </button>

  <template v-if="series">
    <h1>Passage — {{ cleanCycle(series.cycle, series.station) }} · {{ stationLabel(series.station) }}</h1>

    <div class="meta-row-passage">
      <!-- Métadonnées charge (répétées depuis la fournée) -->
      <div class="card" v-if="chargeMeta">
        <h2>Métadonnées charge <span class="charge-link" @click="router.push({ name: 'fournee-detail', params: { charge: props.charge } })">{{ props.charge }} ›</span></h2>
        <div class="info-list">
          <div class="info-row"><span>Opérateur</span><b>{{ chargeMeta.operateur || '—' }}</b></div>
          <div class="info-row"><span>Date création</span><b>{{ chargeMeta.date_creat || '—' }}</b></div>
          <div class="info-row"><span>N° charge</span><b>{{ chargeMeta.numero ?? '—' }}</b></div>
          <div class="info-row"><span>Portique</span><b>{{ stationLabel(chargeMeta.portique) }}</b></div>
        </div>
      </div>

      <!-- Métadonnées passage -->
      <div class="card">
        <h2>Passage</h2>
        <div class="info-list">
          <div class="info-row"><span>Équipement</span><b>{{ stationLabel(series.station) }}</b></div>
          <div class="info-row"><span>Cycle</span><b>{{ cleanCycle(series.cycle, series.station) }}</b></div>
          <div class="info-row"><span>Début</span><b>{{ formatDate(series.tps_deb) }}</b></div>
          <div class="info-row"><span>Fin</span><b>{{ formatDate(series.tps_fin) }}</b></div>
        </div>
      </div>
    </div>

    <template v-for="(option, category) in chartOptions" :key="category">
      <div class="card">
        <h2>{{ CATEGORY_LABELS[category] || category }}</h2>
        <v-chart :option="option" autoresize style="height: 350px;" />
      </div>
      <div class="card" v-if="category === 'temperature' && temperaturePaliers.length">
        <h2>Temps de maintien par palier</h2>
        <table>
          <thead>
            <tr>
              <th>Consigne</th>
              <th>Atteinte de la consigne</th>
              <th>Temps de traitement</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(p, idx) in temperaturePaliers" :key="idx">
              <td>{{ p.consigne }} °C</td>
              <td>{{ p.atteinte ? formatDate(p.atteinte) : 'Non atteinte' }}</td>
              <td>{{ formatDuration(p.duree) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
    <p v-if="Object.keys(series.categories).length === 0">
      Aucune donnée de série temporelle pour ce passage.
    </p>
  </template>
</template>

<style scoped>
.meta-row-passage {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
  margin-bottom: 1rem;
}

.meta-row-passage .card { margin-bottom: 0; padding: 1rem; }

.meta-row-passage h2 {
  font-size: 0.8125rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: #64748b;
  margin: 0 0 0.75rem 0;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.charge-link {
  font-size: 0.75rem;
  font-weight: 600;
  color: #2563eb;
  cursor: pointer;
  text-transform: none;
  letter-spacing: 0;
}
.charge-link:hover { text-decoration: underline; }

.info-list { display: flex; flex-direction: column; }

.info-row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  padding: 0.3rem 0;
  border-bottom: 1px solid #f1f5f9;
  font-size: 0.8125rem;
  gap: 0.5rem;
}
.info-row:last-child { border-bottom: none; }
.info-row span { color: #94a3b8; font-size: 0.75rem; font-weight: 500; flex-shrink: 0; }
.info-row b    { color: #1e293b; font-weight: 600; text-align: right; }
</style>
