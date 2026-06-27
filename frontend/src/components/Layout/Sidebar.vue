<script setup>
import { ref } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const expanded = ref(false)

function isActive(path) {
  if (path === '/') return route.path === '/'
  return route.path.startsWith(path)
}
</script>

<template>
  <aside class="sidebar" :class="{ expanded }" @mouseenter="expanded = true" @mouseleave="expanded = false">
    <div class="sidebar-content">
      <nav class="menu">
        <router-link to="/"         class="menu-item" :class="{ active: isActive('/') }"        title="Tableau de bord">
          <span class="menu-icon">📊</span>
          <span class="menu-label">Tableau de bord</span>
        </router-link>
        <router-link to="/fournees" class="menu-item" :class="{ active: isActive('/fournees') }" title="Fournées">
          <span class="menu-icon">🔥</span>
          <span class="menu-label">Fournées</span>
        </router-link>
        <router-link to="/alarmes" class="menu-item" :class="{ active: isActive('/alarmes') }" title="Alarmes">
          <span class="menu-icon">🔴</span>
          <span class="menu-label">Alarmes</span>
        </router-link>
        <router-link to="/consultation" class="menu-item" :class="{ active: isActive('/consultation') }" title="Consultation">
          <span class="menu-icon">🔍</span>
          <span class="menu-label">Consultation</span>
        </router-link>
        <router-link to="/analyse"  class="menu-item" :class="{ active: isActive('/analyse') }"  title="Analyse">
          <span class="menu-icon">🔬</span>
          <span class="menu-label">Analyse</span>
        </router-link>
        <router-link to="/parametrage" class="menu-item" :class="{ active: isActive('/parametrage') }" title="Paramétrage">
          <span class="menu-icon">⚙️</span>
          <span class="menu-label">Paramétrage</span>
        </router-link>
      </nav>
    </div>
  </aside>
</template>

<style scoped>
.sidebar {
  position: relative;
  width: 68px;
  min-width: 68px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  background: linear-gradient(180deg, #1a2744 0%, #0f172a 100%);
  box-shadow: 2px 0 10px rgba(0, 0, 0, 0.1);
  overflow: hidden;
  transition: width 0.25s cubic-bezier(0.4, 0, 0.2, 1),
              min-width 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}

.sidebar.expanded {
  width: 260px;
  min-width: 260px;
}

.sidebar-content {
  display: flex;
  flex-direction: column;
  height: 100%;
  width: 260px;
}

.menu {
  flex: 1;
  padding: 0.75rem 0;
  overflow-y: auto;
  overflow-x: hidden;
}

.menu-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem;
  margin: 0.2rem 0.5rem;
  color: #94a3b8;
  text-decoration: none;
  transition: all 0.2s ease;
  border-radius: 10px;
  font-size: 0.9375rem;
  white-space: nowrap;
}

.sidebar.expanded .menu-item {
  padding: 0.75rem 1rem;
  margin: 0.2rem 0.6rem;
}

.menu-item:hover {
  background: rgba(255, 255, 255, 0.08);
  color: white;
  text-decoration: none;
}

.menu-item.active {
  background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
  color: white;
  font-weight: 600;
  box-shadow: 0 4px 12px rgba(37, 99, 235, 0.3);
}

.menu-icon {
  font-size: 1.25rem;
  width: 1.75rem;
  min-width: 1.75rem;
  display: flex;
  align-items: center;
  justify-content: center;
}

.menu-label {
  opacity: 0;
  transition: opacity 0.2s ease;
  overflow: hidden;
}

.sidebar.expanded .menu-label {
  opacity: 1;
}
</style>
