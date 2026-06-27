<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  options:    { type: Array, default: () => [] },  // [{ id, variable }]
  modelValue: { type: Array, default: () => [] },  // ids sélectionnés
})
const emit = defineEmits(['update:modelValue', 'close'])

const open      = ref(false)
const container = ref(null)

function setOpen(val) {
  if (!val && open.value) emit('close')
  open.value = val
}

function onOutsideClick(e) {
  if (container.value && !container.value.contains(e.target)) setOpen(false)
}
onMounted(()  => document.addEventListener('mousedown', onOutsideClick))
onUnmounted(() => document.removeEventListener('mousedown', onOutsideClick))

function selectAll()  { emit('update:modelValue', props.options.map((o) => o.id)) }
function selectNone() { emit('update:modelValue', []) }

function toggle(id) {
  const next = props.modelValue.includes(id)
    ? props.modelValue.filter((x) => x !== id)
    : [...props.modelValue, id]
  emit('update:modelValue', next)
}

const triggerLabel = computed(() => {
  const n     = props.modelValue.length
  const total = props.options.length
  if (n === 0)     return 'Aucun'
  if (n === total) return `Tous (${n})`
  if (n === 1) {
    const opt = props.options.find((o) => o.id === props.modelValue[0])
    return opt?.label ?? '1 sélectionné'
  }
  return `${n} sélectionnés`
})
</script>

<template>
  <div class="ms" ref="container">
    <button type="button" class="ms-trigger" @click="setOpen(!open)">
      <span class="ms-trigger-label">{{ triggerLabel }}</span>
      <span class="ms-arrow">{{ open ? '▲' : '▼' }}</span>
    </button>

    <div class="ms-panel" v-if="open">
      <div class="ms-actions">
        <button type="button" @click="selectAll">Tout</button>
        <button type="button" @click="selectNone">Aucun</button>
      </div>
      <label
        v-for="opt in options"
        :key="opt.id"
        class="ms-option"
        :class="{ checked: modelValue.includes(opt.id) }"
      >
        <input
          type="checkbox"
          :checked="modelValue.includes(opt.id)"
          @change="toggle(opt.id)"
        />
        {{ opt.label }}
      </label>
    </div>
  </div>
</template>

<style scoped>
.ms {
  position: relative;
  display: inline-block;
}

.ms-trigger {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  min-width: 180px;
  padding: 0.5rem 0.75rem;
  border: 1.5px solid #e2e8f0;
  border-radius: 8px;
  background: white;
  color: #0f172a;
  font-size: 0.875rem;
  font-family: inherit;
  cursor: pointer;
  transition: border-color 0.2s, box-shadow 0.2s;
  text-align: left;
}

.ms-trigger:focus,
.ms-trigger:hover {
  outline: none;
  border-color: #2563eb;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
}

.ms-trigger-label { flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.ms-arrow         { font-size: 0.6rem; color: #94a3b8; flex-shrink: 0; }

.ms-panel {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  min-width: 100%;
  background: white;
  border: 1.5px solid #e2e8f0;
  border-radius: 8px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
  z-index: 200;
  padding: 0.375rem 0;
  max-height: 260px;
  overflow-y: auto;
}

.ms-actions {
  display: flex;
  gap: 0.5rem;
  padding: 0.375rem 0.75rem 0.5rem;
  border-bottom: 1px solid #f1f5f9;
}

.ms-actions button {
  font-size: 0.75rem;
  font-weight: 600;
  color: #2563eb;
  background: none;
  border: none;
  cursor: pointer;
  padding: 0;
  font-family: inherit;
}

.ms-actions button:hover { text-decoration: underline; }

.ms-option {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.4rem 0.75rem;
  font-size: 0.875rem;
  color: #475569;
  cursor: pointer;
  transition: background 0.1s;
}

.ms-option:hover   { background: #f8fafc; }
.ms-option.checked { color: #1e40af; background: #eff6ff; }

.ms-option input {
  accent-color: #2563eb;
  width: 14px;
  height: 14px;
  flex-shrink: 0;
  cursor: pointer;
}
</style>
