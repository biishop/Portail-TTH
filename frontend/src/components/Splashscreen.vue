<script setup>
import { ref, onMounted } from 'vue'
import logoFull from '../assets/logo-full.png'

defineEmits(['done'])

const visible = ref(true)

const dismiss = () => { visible.value = false }

onMounted(() => {
  setTimeout(dismiss, 1800)
})
</script>

<template>
  <Transition name="splash" @after-leave="$emit('done')">
    <div class="splash" v-if="visible" @click="dismiss">
      <div class="splash-content">

        <div class="app-logo-wrap">
          <img :src="logoFull" alt="Portail TTH" class="app-logo" />
        </div>

        <div class="app-name">Portail Traitement Thermique</div>
        <div class="app-sub">TTH — Traitement Thermique</div>

        <div class="splash-divider"></div>

        <div class="safran-row">
          <img src="/safran.svg" alt="Safran" class="safran-logo" />
          <div class="safran-text">
            <div class="safran-line1">SLS Bidos</div>
            <div class="safran-line2">F4F / CCX</div>
          </div>
        </div>

      </div>
      <div class="splash-hint">Cliquer pour continuer</div>
    </div>
  </Transition>
</template>

<style scoped>
.splash {
  position: fixed;
  inset: 0;
  z-index: 9999;
  background: linear-gradient(160deg, #0a0f1e 0%, #0f2044 50%, #0a1628 100%);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  user-select: none;
}

.splash-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0;
}

/* Logo */
.app-logo-wrap {
  animation: logo-in 0.4s cubic-bezier(0.34, 1.56, 0.64, 1) both;
}

.app-logo {
  width: 160px;
  height: 160px;
  object-fit: contain;
  border-radius: 20px;
  filter: drop-shadow(0 0 32px rgba(37, 99, 235, 0.6));
}

/* Titre */
.app-name {
  margin-top: 1.75rem;
  font-size: 2rem;
  font-weight: 800;
  letter-spacing: -1px;
  text-align: center;
  background: linear-gradient(135deg, #60a5fa 0%, #2563eb 50%, #1d4ed8 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  animation: fade-up 0.35s 0.2s both;
}

/* Sous-titre */
.app-sub {
  margin-top: 0.5rem;
  font-size: 0.875rem;
  color: #64748b;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  animation: fade-up 0.35s 0.3s both;
}

/* Séparateur */
.splash-divider {
  width: 240px;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(255,255,255,0.1), transparent);
  margin: 2rem 0;
  animation: fade-up 0.35s 0.4s both;
}

/* Bloc Safran */
.safran-row {
  display: flex;
  align-items: center;
  gap: 1.25rem;
  animation: fade-up 0.35s 0.5s both;
}

.safran-logo {
  height: 40px;
  width: auto;
  filter: brightness(0) invert(1) opacity(0.85);
}

.safran-text {
  display: flex;
  flex-direction: column;
  border-left: 1px solid rgba(255, 255, 255, 0.15);
  padding-left: 1.25rem;
}

.safran-line1 {
  font-size: 1rem;
  font-weight: 700;
  color: #e2e8f0;
  letter-spacing: 0.05em;
}

.safran-line2 {
  font-size: 0.8125rem;
  color: #64748b;
  letter-spacing: 0.08em;
  margin-top: 0.2rem;
}

/* Hint */
.splash-hint {
  position: absolute;
  bottom: 2rem;
  font-size: 0.75rem;
  color: #334155;
  letter-spacing: 0.08em;
  animation: blink 2s 1.5s infinite;
}

/* Animations */
@keyframes logo-in {
  from { opacity: 0; transform: scale(0.6) translateY(20px); }
  to   { opacity: 1; transform: scale(1)   translateY(0); }
}

@keyframes fade-up {
  from { opacity: 0; transform: translateY(16px); }
  to   { opacity: 1; transform: translateY(0); }
}

@keyframes blink {
  0%, 100% { opacity: 0.3; }
  50%       { opacity: 0.8; }
}

.splash-enter-active { transition: opacity 0.3s ease; }
.splash-leave-active { transition: opacity 0.35s ease; }
.splash-enter-from, .splash-leave-to { opacity: 0; }
</style>
