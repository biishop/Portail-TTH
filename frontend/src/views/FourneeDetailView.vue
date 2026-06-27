<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'
import { stationLabel, cycleIcon, cleanCycle } from '../constants'

function alarmLabel(code, description) {
  return description && description.trim() ? description : (code ?? '—')
}

// ── Non-conformités ────────────────────────────────────────────────
const ncList       = ref([])
const showNcForm   = ref(false)
const ncSubmitting = ref(false)
const ncForm = ref({ lot: '', nature: '', description: '', operateur: '' })

const NC_STATUT_LABELS = {
  ouverte:   { label: 'Ouverte',    cls: 'badge-danger'  },
  en_cours:  { label: 'En cours',   cls: 'badge-warning' },
  cloturee:  { label: 'Clôturée',   cls: 'badge-success' },
}

async function loadNc() {
  const { data } = await api.get(`/fournees/${props.charge}/nc`)
  ncList.value = data
}

async function submitNc() {
  if (!ncForm.value.nature.trim()) return
  ncSubmitting.value = true
  try {
    await api.post(`/fournees/${props.charge}/nc`, ncForm.value)
    ncForm.value = { lot: '', nature: '', description: '', operateur: '' }
    showNcForm.value = false
    await loadNc()
  } finally {
    ncSubmitting.value = false
  }
}

const props = defineProps({
  charge: { type: String, required: true },
})

const router = useRouter()
const fournee = ref(null)

function formatDate(s) {
  if (!s) return ''
  return s.replace('T', ' ').slice(0, 19)
}

function formatDuration(min) {
  if (min == null || min <= 0) return null
  const h = Math.floor(min / 60)
  const m = min % 60
  return h > 0 ? `${h}h${String(m).padStart(2, '0')}` : `${m}min`
}

function diffMin(a, b) {
  if (!a || !b) return null
  const d = Math.round((new Date(b) - new Date(a)) / 60000)
  return d > 0 ? d : null
}

// ── Timeline ──────────────────────────────────────────────────────

// Couleur du dot selon le statut
const STATUS_COLOR = {
  done:   '#22c55e',
  active: '#2563eb',
  todo:   '#94a3b8',
}

const timelineSteps = computed(() => {
  if (!fournee.value) return []

  // Source 1 : recette_plan (avec fait_ou_pas)
  if (fournee.value.recette_plan?.steps?.length) {
    return fournee.value.recette_plan.steps.map((step, idx, arr) => {
      const status = step.fait_ou_pas === 1 ? 'done'
                   : step.fait_ou_pas === 0 ? 'active' : 'todo'
      const prev = idx > 0 ? arr[idx - 1] : null
      const passage = fournee.value.passages.find(
        (p) => p.cycle === step.cycle && p.tps_deb === step.tps_deb,
      )
      const lbl = cleanCycle(step.cycle, passage?.station)
      return {
        label:        lbl,
        status,
        icon:         cycleIcon(lbl),
        color:        STATUS_COLOR[status],
        tps_deb:      step.tps_deb,
        tps_fin:      step.tps_fin,
        gap_min:      prev ? diffMin(prev.tps_fin, step.tps_deb) : null,
        duration_min: diffMin(step.tps_deb, step.tps_fin),
        passage_id:   passage?.id,
      }
    })
  }

  // Source 2 : passages (fallback — toujours disponible)
  return fournee.value.passages.map((p, idx, arr) => {
    const status = p.tps_fin ? 'done' : 'active'
    const prev = idx > 0 ? arr[idx - 1] : null
    return {
      label:        cleanCycle(p.cycle, p.station),
      sub:          stationLabel(p.station),
      status,
      icon:         cycleIcon(cleanCycle(p.cycle, p.station)),
      color:        STATUS_COLOR[status],
      tps_deb:      p.tps_deb,
      tps_fin:      p.tps_fin,
      gap_min:      prev ? diffMin(prev.tps_fin, p.tps_deb) : null,
      duration_min: diffMin(p.tps_deb, p.tps_fin),
      passage_id:   p.id,
    }
  })
})

async function load() {
  const { data } = await api.get(`/fournees/${props.charge}`)
  fournee.value = data
}

// ── Certificats ────────────────────────────────────────────────────
const certLoading = ref(false)
const pdfModal = ref({ open: false, lot: '', url: '', loading: false })

async function openPdf(lot) {
  pdfModal.value = { open: true, lot, url: '', loading: true }
  try {
    const resp = await api.get(
      `/fournees/${props.charge}/certificat/${encodeURIComponent(lot)}`,
      { responseType: 'blob' },
    )
    pdfModal.value.url = URL.createObjectURL(
      new Blob([resp.data], { type: 'application/pdf' }),
    )
  } finally {
    pdfModal.value.loading = false
  }
}

function closePdf() {
  if (pdfModal.value.url) URL.revokeObjectURL(pdfModal.value.url)
  pdfModal.value = { open: false, lot: '', url: '', loading: false }
}

async function downloadCerts() {
  certLoading.value = true
  try {
    const resp = await api.get(`/fournees/${props.charge}/certificats`, {
      responseType: 'blob',
    })
    const url  = URL.createObjectURL(new Blob([resp.data], { type: 'application/zip' }))
    const link = document.createElement('a')
    link.href     = url
    link.download = `Certificats_charge_${props.charge}.zip`
    link.click()
    URL.revokeObjectURL(url)
  } finally {
    certLoading.value = false
  }
}

// ── Alarmes ────────────────────────────────────────────────────────
const alarmes      = ref([])
const showAlarmes  = ref(false)

async function loadAlarmes() {
  const { data } = await api.get(`/fournees/${props.charge}/alarmes`)
  alarmes.value = data
}

function formatDureeAlarm(s) {
  if (s == null) return '—'
  if (s < 60)   return `${s}s`
  const m = Math.floor(s / 60), sec = s % 60
  if (m < 60)   return `${m}m${sec > 0 ? String(sec).padStart(2,'0') + 's' : ''}`
  const h = Math.floor(m / 60), min = m % 60
  return `${h}h${String(min).padStart(2, '0')}`
}

onMounted(() => { load(); loadNc(); loadAlarmes() })
</script>

<template>
  <template v-if="fournee">
    <div class="page-header">
      <button class="btn btn-secondary sm" @click="router.push({ name: 'fournees' })">&larr; Retour</button>
      <h1 class="page-title" style="margin:0">Charge {{ fournee.charge }}</h1>
      <button class="btn btn-primary sm cert-btn" @click="downloadCerts" :disabled="certLoading">
        <span v-if="certLoading">⏳ Génération…</span>
        <span v-else>📄 Certificats ({{ fournee.of_list.length }} OF)</span>
      </button>
    </div>

    <!-- Métadonnées + OF sur une ligne -->
    <div class="meta-row">
      <!-- Métadonnées -->
      <div class="card meta-card">
        <h2>Métadonnées</h2>
        <div class="info-list">
          <div class="info-row"><span>Charge</span><b>{{ fournee.charge }}</b></div>
          <div class="info-row"><span>Opérateur</span><b>{{ fournee.charge_operateur || '—' }}</b></div>
          <div class="info-row"><span>Date création</span><b>{{ fournee.charge_date_creat || '—' }}</b></div>
          <div class="info-row"><span>N° charge</span><b>{{ fournee.charge_numero ?? '—' }}</b></div>
          <div class="info-row"><span>Portique</span><b>{{ fournee.charge_portique ?? '—' }}</b></div>
        </div>
      </div>

      <!-- OF attachés -->
      <div class="card of-card" v-if="fournee.of_list.length">
        <h2>OF attachés <span class="count-badge">{{ fournee.of_list.length }}</span></h2>
        <table>
          <thead>
            <tr>
              <th>OF</th><th>Pièce</th><th>Nuance</th><th>Désignation</th>
              <th>Poids unit.</th><th>Poids tot.</th><th>Nb</th><th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="of in fournee.of_list" :key="of.lot"
                style="cursor:pointer" @click="openPdf(of.lot)"
                title="Cliquer pour voir le certificat de traitement">
              <td>{{ of.lot }}</td><td>{{ of.piece }}</td><td>{{ of.nuance }}</td>
              <td>{{ of.denomination }}</td><td>{{ of.poids }}</td>
              <td>{{ of.tonnage }}</td><td>{{ of.nbre }}</td>
              <td class="td-cert">📄</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Timeline exécution recette -->
    <div class="card" v-if="timelineSteps.length">
      <div class="tl-header">
        <h2 style="margin:0">
          🔄 Exécution
          <span class="recette-name"
                v-if="fournee.recette_plan?.recette || fournee.recette_steps[0]?.recette">
            — {{ fournee.recette_plan?.recette || fournee.recette_steps[0]?.recette }}
          </span>
        </h2>
        <span v-if="fournee.recette_plan"
          :class="['badge', fournee.recette_plan.terminee ? 'badge-success' : 'badge-warning']">
          {{ fournee.recette_plan.terminee ? 'Terminée' : 'En cours' }}
        </span>
      </div>

      <div class="timeline">
        <div v-for="(step, idx) in timelineSteps" :key="idx" class="tl-item">
          <!-- Colonne gauche : dot + ligne verticale -->
          <div class="tl-left">
            <div class="tl-dot" :style="`background:${step.color}`">{{ step.icon }}</div>
            <div class="tl-line" v-if="idx < timelineSteps.length - 1"></div>
          </div>

          <!-- Corps -->
          <div class="tl-body">
            <!-- Pilule de délai depuis l'étape précédente -->
            <div class="tl-gap" v-if="step.gap_min">
              <span class="gap-pill">+{{ formatDuration(step.gap_min) }}</span>
            </div>

            <div
              class="tl-card"
              :class="{ 'tl-card-active': step.status === 'active', 'tl-card-todo': step.status === 'todo' }"
              :style="step.passage_id ? 'cursor:pointer' : ''"
              @click="step.passage_id && router.push({ name: 'passage-detail', params: { charge: props.charge, passageId: step.passage_id } })"
            >
              <div class="tl-card-header">
                <div>
                  <span class="tl-label">{{ step.label }}</span>
                  <span class="tl-sub" v-if="step.sub"> · {{ step.sub }}</span>
                </div>
                <div class="tl-right">
                  <span class="step-dur" v-if="step.duration_min">{{ formatDuration(step.duration_min) }}</span>
                  <span class="badge badge-warning" v-if="step.status === 'active'">En cours</span>
                  <span class="badge badge-secondary" v-if="step.status === 'todo'">À faire</span>
                  <span class="tl-nav" v-if="step.passage_id">›</span>
                </div>
              </div>

              <div class="tl-dates" v-if="step.tps_deb || step.tps_fin">
                <span v-if="step.tps_deb" class="tl-date">
                  <span class="date-lbl">Début</span> {{ formatDate(step.tps_deb) }}
                </span>
                <span v-if="step.tps_fin" class="tl-date">
                  <span class="date-lbl">Fin</span> {{ formatDate(step.tps_fin) }}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Non-conformités -->
    <div class="card nc-card">
      <div class="nc-header">
        <h2 style="margin:0">
          ⚠️ Non-conformités
          <span class="count-badge" v-if="ncList.length">{{ ncList.length }}</span>
        </h2>
        <button class="btn btn-primary sm" @click="showNcForm = !showNcForm">
          {{ showNcForm ? '✕ Annuler' : '+ Déclarer une NC' }}
        </button>
      </div>

      <!-- Formulaire de déclaration -->
      <form v-if="showNcForm" class="nc-form" @submit.prevent="submitNc">
        <div class="nc-form-row">
          <label class="nc-form-label">
            Lot concerné
            <select v-model="ncForm.lot" class="nc-input">
              <option value="">Toute la charge</option>
              <option v-for="of in fournee.of_list" :key="of.lot" :value="of.lot">
                {{ of.lot }}{{ of.piece ? ' — ' + of.piece : '' }}
              </option>
            </select>
          </label>
          <label class="nc-form-label">
            Opérateur
            <input v-model="ncForm.operateur" type="text" class="nc-input" placeholder="Nom opérateur" />
          </label>
        </div>
        <label class="nc-form-label">
          Nature de la NC <span class="nc-required">*</span>
          <input v-model="ncForm.nature" type="text" class="nc-input" required
                 placeholder="Ex : Dépassement consigne température, Durée cycle incorrecte…" />
        </label>
        <label class="nc-form-label">
          Description
          <textarea v-model="ncForm.description" class="nc-input nc-textarea" rows="3"
                    placeholder="Détails observés, mesures, contexte…"></textarea>
        </label>
        <div class="nc-form-actions">
          <button type="submit" class="btn btn-primary" :disabled="!ncForm.nature.trim() || ncSubmitting">
            {{ ncSubmitting ? 'Enregistrement…' : 'Enregistrer la NC' }}
          </button>
        </div>
      </form>

      <!-- Liste NC existantes -->
      <div v-if="ncList.length" class="nc-list">
        <div v-for="nc in ncList" :key="nc.id" class="nc-item">
          <div class="nc-item-header">
            <span class="nc-nature">{{ nc.nature }}</span>
            <div class="nc-item-meta">
              <span class="badge" :class="NC_STATUT_LABELS[nc.statut]?.cls ?? 'badge-secondary'">
                {{ NC_STATUT_LABELS[nc.statut]?.label ?? nc.statut }}
              </span>
              <span class="nc-date">{{ nc.date_declaration?.replace('T', ' ').slice(0, 16) }}</span>
              <span class="nc-lot" v-if="nc.lot">Lot {{ nc.lot }}</span>
              <span class="nc-op" v-if="nc.operateur">{{ nc.operateur }}</span>
            </div>
          </div>
          <p class="nc-description" v-if="nc.description">{{ nc.description }}</p>
        </div>
      </div>
      <p v-else-if="!showNcForm" class="nc-empty">Aucune non-conformité déclarée pour cette charge.</p>
    </div>

    <!-- Alarmes CITECT pendant la charge -->
    <div class="card alarm-card" v-if="alarmes.length">
      <div class="alarm-header" @click="showAlarmes = !showAlarmes" style="cursor:pointer">
        <h2 style="margin:0">
          🔴 Alarmes CITECT
          <span class="count-badge" style="background:#fee2e2;color:#991b1b">{{ alarmes.length }}</span>
        </h2>
        <span class="alarm-toggle">{{ showAlarmes ? '▲' : '▼' }}</span>
      </div>

      <table v-if="showAlarmes" style="margin-top:0.875rem">
        <thead>
          <tr>
            <th>Apparition</th>
            <th>Disparition</th>
            <th>Durée</th>
            <th>Libellé</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="a in alarmes" :key="a.id">
            <td class="alarm-ts">{{ formatDate(a.tps_apparition) }}</td>
            <td class="alarm-ts">{{ a.tps_disparition ? formatDate(a.tps_disparition) : '—' }}</td>
            <td class="alarm-dur">{{ formatDureeAlarm(a.duree_s) }}</td>
            <td>
              <div class="alarm-lbl">{{ alarmLabel(a.code, a.description) }}</div>
              <span class="alarm-code">{{ a.code }}</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Définition recette -->
    <div class="card" v-if="fournee.recette_steps.length">
      <h2>Définition recette — {{ fournee.recette_steps[0].recette }}</h2>
      <table>
        <thead><tr><th>Bloc</th><th>Type</th><th>Cycle</th></tr></thead>
        <tbody>
          <tr v-for="step in fournee.recette_steps" :key="step.bloc">
            <td>{{ step.bloc }}</td><td>{{ step.type }}</td><td>{{ step.cycle }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </template>

  <!-- ── Modal visualiseur PDF ─────────────────────────────────── -->
  <Teleport to="body">
    <div v-if="pdfModal.open" class="pdf-overlay" @click.self="closePdf">
      <div class="pdf-modal">
        <div class="pdf-modal-header">
          <span class="pdf-modal-title">
            📄 Certificat OF <strong>{{ pdfModal.lot }}</strong>
            — Charge {{ props.charge }}
          </span>
          <button class="pdf-close" @click="closePdf" title="Fermer">✕</button>
        </div>
        <div v-if="pdfModal.loading" class="pdf-loading">Génération du certificat…</div>
        <iframe v-else-if="pdfModal.url" :src="pdfModal.url" class="pdf-iframe" />
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
/* ── Header page compact ────────────────────────────────────────── */
.page-header {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-bottom: 1rem;
}

.cert-btn { margin-left: auto; }

.btn.sm {
  padding: 0.35rem 0.875rem;
  font-size: 0.8125rem;
}

/* ── Ligne Métadonnées + OF ─────────────────────────────────────── */
.meta-row {
  display: grid;
  grid-template-columns: 240px 1fr;
  gap: 1rem;
  margin-bottom: 1rem;
}

.meta-card,
.of-card {
  margin-bottom: 0;
  padding: 1rem;
}

.meta-card h2,
.of-card h2 {
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

.info-list { display: flex; flex-direction: column; gap: 0; }

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

.info-row span {
  color: #94a3b8;
  font-size: 0.75rem;
  font-weight: 500;
  flex-shrink: 0;
}

.info-row b {
  color: #1e293b;
  font-weight: 600;
  text-align: right;
}

.count-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: #e2e8f0;
  color: #475569;
  font-size: 0.75rem;
  font-weight: 700;
  border-radius: 10px;
  padding: 0 0.45rem;
  min-width: 1.4rem;
  height: 1.4rem;
}

/* OF table plus compacte */
.of-card table th,
.of-card table td {
  padding: 0.5rem 0.75rem;
  font-size: 0.8125rem;
}

/* ── Cartes timeline compactes ──────────────────────────────────── */
.card { padding: 1.25rem; margin-bottom: 1rem; }

.tl-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 1.5rem;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.recette-name {
  font-size: 0.875rem;
  font-weight: 600;
  color: #2563eb;
  font-style: normal;
}

/* ── Timeline ───────────────────────────────────────────────────── */
.timeline { display: flex; flex-direction: column; }

.tl-item {
  display: flex;
  gap: 0;
}

.tl-left {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 44px;
  flex-shrink: 0;
}

.tl-dot {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1rem;
  flex-shrink: 0;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.15);
  z-index: 1;
}

.tl-line {
  flex: 1;
  width: 2px;
  background: #e2e8f0;
  min-height: 16px;
  margin: 4px 0;
}

.tl-body {
  flex: 1;
  padding-bottom: 8px;
  padding-left: 12px;
}

/* Pilule délai */
.tl-gap {
  display: flex;
  align-items: center;
  padding: 4px 0;
  min-height: 24px;
}

.gap-pill {
  font-size: 0.75rem;
  color: #94a3b8;
  background: #f1f5f9;
  padding: 0.15rem 0.6rem;
  border-radius: 20px;
  font-weight: 500;
}

/* Carte étape */
.tl-card {
  background: white;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 0.75rem 1rem;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
  transition: box-shadow 0.15s ease;
}

.tl-card:hover {
  box-shadow: 0 3px 8px rgba(0, 0, 0, 0.08);
}

.tl-card-active {
  border-color: #93c5fd;
  background: #eff6ff;
}

.tl-card-todo {
  border-color: #e2e8f0;
  background: #f8fafc;
  opacity: 0.7;
}

.tl-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.tl-label {
  font-size: 0.9rem;
  font-weight: 600;
  color: #1e293b;
}

.tl-sub {
  font-size: 0.8125rem;
  color: #64748b;
}

.tl-right {
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.step-dur {
  font-size: 0.8125rem;
  font-weight: 700;
  color: #2563eb;
  background: #eff6ff;
  padding: 0.15rem 0.6rem;
  border-radius: 20px;
}

.tl-nav {
  font-size: 1.1rem;
  color: #94a3b8;
  font-weight: 700;
}

.tl-dates {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  margin-top: 0.4rem;
}

.tl-date {
  font-size: 0.8125rem;
  color: #475569;
}

.date-lbl {
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: #94a3b8;
  font-weight: 600;
  margin-right: 0.25rem;
}

/* ── Alarmes ────────────────────────────────────────────────────── */
.alarm-card  { border-left: 4px solid #ef4444; }

.alarm-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  user-select: none;
}
.alarm-header:hover h2 { color: #dc2626; }
.alarm-toggle { font-size: 0.75rem; color: #94a3b8; }
.alarm-ts    { font-size: 0.8rem; color: #475569; white-space: nowrap; }
.alarm-dur   { font-size: 0.8rem; font-weight: 700; color: #dc2626; white-space: nowrap; }
.alarm-lbl   { font-size: 0.8125rem; font-weight: 600; color: #1e293b; }
.alarm-code  { font-size: 0.7rem; font-family: monospace; color: #94a3b8;
               display: inline-block; margin-top: 0.1rem; }

/* ── Non-conformités ────────────────────────────────────────────── */
.nc-card { border-left: 4px solid #f59e0b; }

.nc-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 1rem;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.nc-form {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 1rem;
  margin-bottom: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.nc-form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.75rem;
}

.nc-form-label {
  display: flex;
  flex-direction: column;
  font-size: 0.8125rem;
  font-weight: 600;
  color: #475569;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  gap: 0.3rem;
}

.nc-required { color: #ef4444; }

.nc-input {
  padding: 0.5rem 0.75rem;
  border: 1.5px solid #e2e8f0;
  border-radius: 8px;
  font-size: 0.875rem;
  font-family: inherit;
  background: white;
  color: #0f172a;
  transition: border-color 0.2s, box-shadow 0.2s;
}

.nc-input:focus {
  outline: none;
  border-color: #2563eb;
  box-shadow: 0 0 0 3px rgba(37,99,235,0.1);
}

.nc-textarea { resize: vertical; min-height: 4rem; }

.nc-form-actions { display: flex; justify-content: flex-end; }

/* Liste NC */
.nc-list { display: flex; flex-direction: column; gap: 0.5rem; }

.nc-item {
  background: #fffbeb;
  border: 1px solid #fde68a;
  border-radius: 8px;
  padding: 0.75rem 1rem;
}

.nc-item-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.nc-nature {
  font-size: 0.9rem;
  font-weight: 600;
  color: #1e293b;
}

.nc-item-meta {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.nc-date, .nc-lot, .nc-op {
  font-size: 0.75rem;
  color: #64748b;
}

.nc-description {
  margin: 0.5rem 0 0 0;
  font-size: 0.8125rem;
  color: #475569;
  white-space: pre-wrap;
}

.nc-empty {
  color: #94a3b8;
  font-size: 0.875rem;
  margin: 0;
}

/* Icône certificat dans le tableau OF */
.td-cert {
  width: 2rem;
  text-align: center;
  font-size: 0.9rem;
  color: #94a3b8;
  padding: 0.4rem 0.25rem !important;
}
tbody tr:hover .td-cert { color: #2563eb; }

/* ── Modal PDF ──────────────────────────────────────────────────── */
.pdf-overlay {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.7);
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1.5rem;
}

.pdf-modal {
  background: white;
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  width: min(90vw, 960px);
  height: min(90vh, 860px);
  box-shadow: 0 20px 60px rgba(0,0,0,0.35);
  overflow: hidden;
}

.pdf-modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.875rem 1.25rem;
  background: #0f172a;
  flex-shrink: 0;
}

.pdf-modal-title {
  font-size: 0.9rem;
  color: white;
  font-weight: 500;
}

.pdf-close {
  background: rgba(255,255,255,0.1);
  border: none;
  color: white;
  width: 2rem;
  height: 2rem;
  border-radius: 50%;
  cursor: pointer;
  font-size: 1rem;
  line-height: 1;
  transition: background 0.15s;
}
.pdf-close:hover { background: rgba(255,255,255,0.25); }

.pdf-loading {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #64748b;
  font-size: 0.9rem;
}

.pdf-iframe {
  flex: 1;
  border: none;
  width: 100%;
}
</style>
