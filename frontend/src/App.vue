<script setup>
import { ref } from 'vue'
import Header from './components/Layout/Header.vue'
import Sidebar from './components/Layout/Sidebar.vue'
import Splashscreen from './components/Splashscreen.vue'

const showSplash = ref(true)
</script>

<template>
  <Splashscreen v-if="showSplash" @done="showSplash = false" />

  <div class="app" v-else>
    <Header />
    <div class="app-body">
      <Sidebar />
      <main class="main-content">
        <router-view />
      </main>
    </div>
  </div>
</template>
