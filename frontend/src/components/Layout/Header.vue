<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import logoIcon from '../../assets/logo-icon.png'
import api from '../../api'

const online = ref(false)
const dateStr = ref('')

const updateDate = () => {
  dateStr.value = new Date().toLocaleDateString('fr-FR', {
    weekday: 'long', day: '2-digit', month: 'long', year: 'numeric',
  })
}

const checkHealth = async () => {
  try {
    await api.get('/fours')
    online.value = true
  } catch {
    online.value = false
  }
}

let timer
onMounted(() => {
  updateDate()
  checkHealth()
  timer = setInterval(checkHealth, 30000)
})
onUnmounted(() => clearInterval(timer))
</script>

<template>
  <header class="header">
    <div class="header-left">
      <div class="logo-col">
        <img :src="logoIcon" alt="TTH" class="logo-img" />
      </div>
      <div class="logo-text">
        <span class="logo-title">Portail Traitement Thermique</span>
      </div>
    </div>
    <div class="header-center">
      <div class="status-dot" :class="online ? 'online' : 'offline'"></div>
      <span class="status-label">{{ online ? 'Base de données connectée' : 'Hors ligne' }}</span>
    </div>
    <div class="header-right">
      <span class="date-label">{{ dateStr }}</span>
    </div>
  </header>
</template>

<style scoped>
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 1.5rem 0 0;
  height: 60px;
  background: linear-gradient(135deg, #0f172a 0%, #1e3a5f 100%);
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  flex-shrink: 0;
}

.header-left { display: flex; align-items: center; }

.logo-col {
  width: 68px;
  min-width: 68px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.logo-img {
  width: 2.75rem;
  height: 2.75rem;
  object-fit: contain;
  border-radius: 8px;
  filter: drop-shadow(0 2px 8px rgba(37, 99, 235, 0.5));
}

.logo-text { display: flex; flex-direction: column; }

.logo-title {
  font-size: 1rem;
  font-weight: 700;
  color: white;
  letter-spacing: -0.3px;
  line-height: 1.2;
}

.header-center {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.status-dot.online  { background: #22c55e; box-shadow: 0 0 6px #22c55e; }
.status-dot.offline { background: #ef4444; }

.status-label {
  font-size: 0.8125rem;
  color: #64748b;
}

.date-label {
  font-size: 0.8125rem;
  color: #64748b;
  text-transform: capitalize;
}
</style>
