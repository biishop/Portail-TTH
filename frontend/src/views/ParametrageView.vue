<script setup>
import { ref, onMounted } from 'vue'
import api from '../api'

// ── Seuils ────────────────────────────────────────────────────────
const seuils       = ref([])
const editId       = ref(null)
const showForm     = ref(false)
const form         = ref({ cycle_pattern: '', tolerance_c: 10, description: '' })
const saving       = ref(false)
const error        = ref('')

async function load() {
  const { data } = await api.get('/parametrage/seuils')
  seuils.value = data
}

// ── Paliers configurés ────────────────────────────────────────────
const paliers       = ref([])
const palierEditId  = ref(null)
const showPalierForm = ref(false)
const palierForm    = ref({ cycle_pattern: '', consignes: '', description: '' })
const palierSaving  = ref(false)
const palierError   = ref('')

async function loadPaliers() {
  const { data } = await api.get('/parametrage/paliers')
  paliers.value = data
}

function openAddPalier() {
  palierEditId.value   = null
  palierForm.value     = { cycle_pattern: '', consignes: '', description: '' }
  showPalierForm.value = true
  palierError.value    = ''
}

function openEditPalier(row) {
  palierEditId.value   = row.id
  palierForm.value     = { cycle_pattern: row.cycle_pattern,
                            consignes: row.consignes,
                            description: row.description || '' }
  showPalierForm.value = true
  palierError.value    = ''
}

function cancelPalier() {
  showPalierForm.value = false
  palierError.value    = ''
}

function validateConsignes(str) {
  const parts = str.split(',').map(s => s.trim()).filter(Boolean)
  if (!parts.length) return false
  return parts.every(p => !isNaN(parseFloat(p)) && parseFloat(p) > 0)
}

async function savePalier() {
  if (!palierForm.value.cycle_pattern.trim() && !palierEditId.value) {
    palierError.value = 'Le motif est obligatoire.'; return
  }
  if (!validateConsignes(palierForm.value.consignes)) {
    palierError.value = 'Entrez des températures valides séparées par des virgules (ex: 760, 871).'; return
  }
  palierSaving.value = true
  palierError.value  = ''
  try {
    if (palierEditId.value) {
      await api.put(`/parametrage/paliers/${palierEditId.value}`, {
        cycle_pattern: palierForm.value.cycle_pattern || null,
        consignes:     palierForm.value.consignes,
        description:   palierForm.value.description || null,
      })
    } else {
      await api.post('/parametrage/paliers', {
        cycle_pattern: palierForm.value.cycle_pattern,
        consignes:     palierForm.value.consignes,
        description:   palierForm.value.description || null,
      })
    }
    showPalierForm.value = false
    await loadPaliers()
  } catch (e) {
    palierError.value = e.response?.data?.detail || 'Erreur lors de l\'enregistrement.'
  } finally {
    palierSaving.value = false
  }
}

async function removePalier(id, pattern) {
  if (!confirm(`Supprimer la règle pour "${pattern}" ?`)) return
  await api.delete(`/parametrage/paliers/${id}`)
  await loadPaliers()
}

function formatConsignes(str) {
  return str.split(',').map(s => s.trim()).filter(Boolean).map(v => `${v} °C`).join('  ·  ')
}

function openAdd() {
  editId.value    = null
  form.value      = { cycle_pattern: '', tolerance_c: 10, description: '' }
  showForm.value  = true
  error.value     = ''
}

function openEdit(row) {
  editId.value    = row.id
  form.value      = { cycle_pattern: row.cycle_pattern, tolerance_c: row.tolerance_c,
                      description: row.description || '' }
  showForm.value  = true
  error.value     = ''
}

function cancel() {
  showForm.value = false
  error.value    = ''
}

async function save() {
  if (!form.value.cycle_pattern.trim() && editId.value === null) {
    error.value = 'Le motif est obligatoire.'
    return
  }
  if (form.value.tolerance_c <= 0) {
    error.value = 'La tolérance doit être > 0.'
    return
  }
  saving.value = true
  error.value  = ''
  try {
    if (editId.value) {
      await api.put(`/parametrage/seuils/${editId.value}`, {
        cycle_pattern: form.value.cycle_pattern || null,
        tolerance_c:   form.value.tolerance_c,
        description:   form.value.description || null,
      })
    } else {
      await api.post('/parametrage/seuils', {
        cycle_pattern: form.value.cycle_pattern,
        tolerance_c:   form.value.tolerance_c,
        description:   form.value.description || null,
      })
    }
    showForm.value = false
    await load()
  } catch (e) {
    error.value = e.response?.data?.detail || 'Erreur lors de l\'enregistrement.'
  } finally {
    saving.value = false
  }
}

async function remove(id, pattern) {
  if (!confirm(`Supprimer la règle "${pattern}" ?`)) return
  await api.delete(`/parametrage/seuils/${id}`)
  await load()
}

onMounted(() => { load(); loadPaliers() })
</script>

<template>
  <h1 class="page-title">Paramétrage</h1>

  <!-- ── Section seuils ────────────────────────────────────────── -->
  <div class="card">
    <div class="section-header">
      <div>
        <h2 class="section-title">🎯 Détection automatique des seuils de température</h2>
        <p class="section-desc">
          Tolérance d'atteinte de consigne utilisée pour le calcul des paliers sur les graphiques
          et dans les certificats de traitement. Exprimée en <b>± °C absolus</b>.<br>
          La règle la plus spécifique (motif le plus long) prend la priorité.
          La règle <code>*</code> s'applique à tous les cycles non couverts.
        </p>
      </div>
      <button class="btn btn-primary" @click="openAdd">+ Ajouter une règle</button>
    </div>

    <!-- Formulaire inline -->
    <div class="form-box" v-if="showForm">
      <div class="form-row">
        <label class="form-lbl">
          Motif de cycle
          <input
            v-model="form.cycle_pattern"
            class="form-input"
            placeholder="ex: 300M*, TREMPE*, * (défaut)"
          />
          <span class="form-hint">Préfixe + * ou nom exact. * = tous les cycles.</span>
        </label>
        <label class="form-lbl">
          Tolérance ± °C
          <div class="tol-wrap">
            <span class="tol-pm">±</span>
            <input v-model.number="form.tolerance_c" type="number" min="0.1" step="0.5"
                   class="form-input tol-input" />
            <span class="tol-unit">°C</span>
          </div>
        </label>
        <label class="form-lbl">
          Description
          <input v-model="form.description" class="form-input"
                 placeholder="optionnel" />
        </label>
      </div>
      <div class="form-actions">
        <span class="form-error" v-if="error">{{ error }}</span>
        <button class="btn btn-secondary" @click="cancel">Annuler</button>
        <button class="btn btn-primary" :disabled="saving" @click="save">
          {{ saving ? 'Enregistrement…' : (editId ? 'Mettre à jour' : 'Ajouter') }}
        </button>
      </div>
    </div>

    <!-- Tableau -->
    <table>
      <thead>
        <tr>
          <th>Motif de cycle</th>
          <th>Tolérance</th>
          <th>Description</th>
          <th>Modifié le</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="s in seuils" :key="s.id"
            :class="{ 'row-default': s.cycle_pattern === '*' }">
          <td>
            <code class="pattern-badge"
                  :class="s.cycle_pattern === '*' ? 'pattern-default' : 'pattern-custom'">
              {{ s.cycle_pattern === '*' ? '* (défaut)' : s.cycle_pattern }}
            </code>
          </td>
          <td class="tol-cell">± {{ s.tolerance_c }} °C</td>
          <td class="desc-cell">{{ s.description || '—' }}</td>
          <td class="date-cell">{{ s.updated_at?.replace('T',' ').slice(0,16) }}</td>
          <td class="actions-cell">
            <button class="btn-icon" @click="openEdit(s)" title="Modifier">✏️</button>
            <button class="btn-icon" v-if="s.cycle_pattern !== '*'"
                    @click="remove(s.id, s.cycle_pattern)" title="Supprimer">🗑️</button>
          </td>
        </tr>
      </tbody>
    </table>
  </div>

  <!-- ── Bloc 2 : Paliers configurés par cycle ────────────────── -->
  <div class="card">
    <div class="section-header">
      <div>
        <h2 class="section-title">🌡️ Paliers de consigne par cycle</h2>
        <p class="section-desc">
          Définit les températures de consigne officielles à détecter pour chaque cycle.
          Sans règle : tous les paliers stables sont détectés automatiquement.
          Avec règle : seules les consignes listées apparaissent dans les graphiques et les certificats.<br>
          <em>Exemple : cycle <code>C10-5*</code> → paliers à 760 °C et 871 °C.</em>
        </p>
      </div>
      <button class="btn btn-primary" @click="openAddPalier">+ Ajouter une règle</button>
    </div>

    <!-- Formulaire inline -->
    <div class="form-box" v-if="showPalierForm">
      <div class="form-row">
        <label class="form-lbl">
          Motif de cycle
          <input v-model="palierForm.cycle_pattern"
                 class="form-input" placeholder="ex: C10-5*, 300M-C10-3, TREMPE*" />
          <span class="form-hint">Préfixe + * ou nom exact.</span>
        </label>
        <label class="form-lbl">
          Consignes (°C)
          <input v-model="palierForm.consignes" class="form-input"
                 placeholder="ex: 760, 871" />
          <span class="form-hint">Températures séparées par des virgules.</span>
        </label>
        <label class="form-lbl">
          Description
          <input v-model="palierForm.description" class="form-input" placeholder="optionnel" />
        </label>
      </div>
      <div class="form-actions">
        <span class="form-error" v-if="palierError">{{ palierError }}</span>
        <button class="btn btn-secondary" @click="cancelPalier">Annuler</button>
        <button class="btn btn-primary" :disabled="palierSaving" @click="savePalier">
          {{ palierSaving ? 'Enregistrement…' : (palierEditId ? 'Mettre à jour' : 'Ajouter') }}
        </button>
      </div>
    </div>

    <!-- Tableau des règles -->
    <table v-if="paliers.length">
      <thead>
        <tr>
          <th>Motif de cycle</th>
          <th>Paliers de consigne</th>
          <th>Description</th>
          <th>Modifié le</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="p in paliers" :key="p.id">
          <td><code class="pattern-badge pattern-custom">{{ p.cycle_pattern }}</code></td>
          <td class="consignes-cell">{{ formatConsignes(p.consignes) }}</td>
          <td class="desc-cell">{{ p.description || '—' }}</td>
          <td class="date-cell">{{ p.updated_at?.replace('T',' ').slice(0,16) }}</td>
          <td class="actions-cell">
            <button class="btn-icon" @click="openEditPalier(p)" title="Modifier">✏️</button>
            <button class="btn-icon" @click="removePalier(p.id, p.cycle_pattern)" title="Supprimer">🗑️</button>
          </td>
        </tr>
      </tbody>
    </table>
    <p v-else class="empty-hint">
      Aucune règle configurée — détection automatique de tous les paliers stables.
    </p>
  </div>
</template>

<style scoped>
.section-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1rem;
  flex-wrap: wrap;
}

.section-title {
  font-size: 1rem;
  font-weight: 700;
  color: #0f172a;
  margin: 0 0 0.4rem 0;
}

.section-desc {
  font-size: 0.8125rem;
  color: #64748b;
  line-height: 1.6;
  margin: 0;
  max-width: 680px;
}

/* Formulaire */
.form-box {
  background: #f8fafc;
  border: 1.5px solid #e2e8f0;
  border-radius: 10px;
  padding: 1rem;
  margin-bottom: 1rem;
}

.form-row {
  display: flex;
  gap: 1rem;
  flex-wrap: wrap;
  align-items: end;
}

.form-lbl {
  display: flex;
  flex-direction: column;
  font-size: 0.8125rem;
  font-weight: 600;
  color: #475569;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  gap: 0.3rem;
  flex: 1;
  min-width: 140px;
}

.form-input {
  padding: 0.5rem 0.75rem;
  border: 1.5px solid #e2e8f0;
  border-radius: 8px;
  font-size: 0.875rem;
  font-family: inherit;
  background: white;
  color: #0f172a;
}
.form-input:focus {
  outline: none;
  border-color: #2563eb;
  box-shadow: 0 0 0 3px rgba(37,99,235,0.1);
}
.form-input:disabled { background: #f1f5f9; color: #94a3b8; }

.form-hint { font-size: 0.7rem; color: #94a3b8; font-weight: 400; text-transform: none; }

.tol-wrap  { display: flex; align-items: center; gap: 0.25rem; }
.tol-pm    { font-size: 1.1rem; font-weight: 700; color: #2563eb; }
.tol-unit  { font-size: 0.875rem; color: #64748b; }
.tol-input { width: 80px; text-align: center; }

.form-actions {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-top: 0.875rem;
  justify-content: flex-end;
}

.form-error { color: #dc2626; font-size: 0.8125rem; margin-right: auto; }

/* Tableau */
.pattern-badge {
  font-family: monospace;
  font-size: 0.8rem;
  padding: 0.2rem 0.6rem;
  border-radius: 6px;
  font-weight: 700;
}
.pattern-default { background: #dbeafe; color: #1e40af; }
.pattern-custom  { background: #f1f5f9; color: #1e293b; }

.row-default td { background: #fafbff !important; }

.tol-cell   { font-weight: 700; color: #2563eb; white-space: nowrap; }
.desc-cell  { font-size: 0.8125rem; color: #64748b; }
.date-cell  { font-size: 0.75rem; color: #94a3b8; white-space: nowrap; }
.actions-cell { white-space: nowrap; }

.btn-icon {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 1rem;
  padding: 0.2rem 0.3rem;
  border-radius: 6px;
  transition: background 0.12s;
}
.btn-icon:hover { background: #f1f5f9; }

.consignes-cell {
  font-weight: 700;
  color: #dc2626;
  font-size: 0.875rem;
  letter-spacing: 0.02em;
}

.empty-hint {
  color: #94a3b8;
  font-size: 0.8125rem;
  margin: 0.5rem 0 0 0;
  font-style: italic;
}
</style>
