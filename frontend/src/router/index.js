import { createRouter, createWebHistory } from 'vue-router'
import DashboardView from '../views/DashboardView.vue'
import FourneesView from '../views/FourneesView.vue'
import FourneeDetailView from '../views/FourneeDetailView.vue'
import PassageDetailView from '../views/PassageDetailView.vue'
import AnalyseView from '../views/AnalyseView.vue'
import ConsultationView from '../views/ConsultationView.vue'
import AlarmsView from '../views/AlarmsView.vue'
import ParametrageView from '../views/ParametrageView.vue'

export default createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'dashboard', component: DashboardView },
    { path: '/fournees', name: 'fournees', component: FourneesView },
    { path: '/analyse', name: 'analyse', component: AnalyseView },
    { path: '/consultation', name: 'consultation', component: ConsultationView },
    { path: '/alarmes', name: 'alarmes', component: AlarmsView },
    { path: '/parametrage', name: 'parametrage', component: ParametrageView },
    { path: '/fournees/:charge', name: 'fournee-detail', component: FourneeDetailView, props: true },
    {
      path: '/fournees/:charge/passages/:passageId',
      name: 'passage-detail',
      component: PassageDetailView,
      props: true,
    },
  ],
})
