<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'
import { stationLabel, stationsLabel, cycleIcon } from '../constants'

function statutIcon(statut, cycle) {
  if (statut === 'termine') return '✅'
  return cycleIcon(cycle)
}

const router = useRouter()

const fours   = ref([])
const items   = ref([])
const total   = ref(0)
const loading = ref(false)

const filters = reactive({
  station: '',
  date_from: '',
  date_to: '',
  q: '',
})
const limit = 50
const offset = ref(0)

function formatDate(s) {
  if (!s) return ''
  return s.replace('T', ' ').slice(0, 19)
}

async function loadFours() {
  const { data } = await api.get('/fours')
  fours.value = data
}

async function loadFournees() {
  loading.value = true
  try {
    const params = { limit, offset: offset.value }
    if (filters.station) params.station = filters.station
    if (filters.date_from) params.date_from = filters.date_from
    if (filters.date_to) params.date_to = filters.date_to
    if (filters.q) params.q = filters.q
    const { data } = await api.get('/fournees', { params })
    items.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

function applyFilters() {
  offset.value = 0
  loadFournees()
}

function prevPage() {
  offset.value = Math.max(0, offset.value - limit)
  loadFournees()
}
function nextPage() {
  if (offset.value + limit < total.value) {
    offset.value += limit
    loadFournees()
  }
}

function openDetail(charge) {
  router.push({ name: 'fournee-detail', params: { charge } })
}

onMounted(() => {
  loadFours()
  loadFournees()
})
</script>

<template>
  <h1>Fournées</h1>
  <div class="filters">
    <label>
      Four
      <select v-model="filters.station">
        <option value="">Tous</option>
        <option v-for="f in fours" :key="f.station" :value="f.station">
          {{ stationLabel(f.station) }}
        </option>
      </select>
    </label>
    <label>
      Du
      <input type="date" v-model="filters.date_from" />
    </label>
    <label>
      Au
      <input type="date" v-model="filters.date_to" />
    </label>
    <label>
      Recherche (lot, pièce, cycle, charge)
      <input type="text" v-model="filters.q" @keyup.enter="applyFilters" />
    </label>
    <button class="btn btn-primary" @click="applyFilters">Filtrer</button>
  </div>

  <div class="pagination">
    <button class="btn btn-secondary" @click="prevPage" :disabled="offset === 0">Précédent</button>
    <span>{{ total === 0 ? 0 : offset + 1 }} - {{ Math.min(offset + limit, total) }} / {{ total }}</span>
    <button class="btn btn-secondary" @click="nextPage" :disabled="offset + limit >= total">Suivant</button>
  </div>

  <div class="table-wrap" :class="{ 'is-loading': loading }">
  <div class="loading-bar" v-if="loading">Chargement…</div>
  <table>
    <thead>
      <tr>
        <th class="th-icon"></th>
        <th>Charge</th>
        <th class="th-icon"></th>
        <th>Début</th>
        <th>Fin</th>
        <th>Portique</th>
        <th>Recette</th>
        <th>Nb OF</th>
        <th>OF attachés</th>
      </tr>
    </thead>
    <tbody>
      <tr v-for="item in items" :key="item.charge" @click="openDetail(item.charge)" style="cursor: pointer;">
        <td class="td-icon">{{ statutIcon(item.statut, item.cycle_en_cours) }}</td>
        <td>{{ item.charge }}</td>
        <td class="td-icon">
          <span v-if="item.has_nc" title="Non-conformité déclarée">⚠️</span>
        </td>
        <td>{{ formatDate(item.tps_deb) }}</td>
        <td>{{ formatDate(item.tps_fin) }}</td>
        <td>{{ item.portique || '—' }}</td>
        <td class="td-recette"
            :title="item.recette_cycles || (item.recette ? '' : stationsLabel(item.stations))">
          <span v-if="item.recette">{{ item.recette }}</span>
          <span v-else class="td-recette-ext"
                :title="stationsLabel(item.stations)">— ext.</span>
        </td>
        <td>{{ item.nb_of }}</td>
        <td class="td-lots">{{ item.lots }}</td>
      </tr>
    </tbody>
  </table>
  </div>

  <div class="pagination">
    <button class="btn btn-secondary" @click="prevPage" :disabled="offset === 0">Précédent</button>
    <span>{{ total === 0 ? 0 : offset + 1 }} - {{ Math.min(offset + limit, total) }} / {{ total }}</span>
    <button class="btn btn-secondary" @click="nextPage" :disabled="offset + limit >= total">Suivant</button>
  </div>
</template>

<style scoped>
/* Wrapper loading */
.table-wrap { position: relative; }

.table-wrap.is-loading table {
  opacity: 0.4;
  pointer-events: none;
  transition: opacity 0.15s ease;
}

.loading-bar {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.875rem;
  font-weight: 600;
  color: #2563eb;
  z-index: 2;
  background: rgba(241, 245, 249, 0.6);
  border-radius: 8px;
  gap: 0.5rem;
}

.loading-bar::before {
  content: '';
  width: 1rem;
  height: 1rem;
  border: 2px solid #bfdbfe;
  border-top-color: #2563eb;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

@keyframes spin { to { transform: rotate(360deg); } }

/* Table compacte */
table th, table td { padding: 0.4rem 0.75rem; font-size: 0.8125rem; }

.td-recette {
  font-size: 0.8rem;
  font-weight: 600;
  color: #1e293b;
  max-width: 220px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  cursor: help;
}

.td-recette-ext {
  font-weight: 400;
  color: #94a3b8;
  font-style: italic;
  cursor: help;
}

/* OF : police petite et couleur atténuée */
.td-lots { font-size: 0.7rem; color: #64748b; max-width: 200px; }
</style>
