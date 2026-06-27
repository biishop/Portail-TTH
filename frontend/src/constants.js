export const STATION_LABELS = {
  3:  'C10-3',
  4:  'Bac huile',
  5:  'C10-5',
  6:  'Lavage',
  7:  'C6-7',
  95: 'Four 7',
  96: 'Four 4',
  97: '653',
  98: 'Cuve trempe alu',
  99: '36',
}

export function stationLabel(id) {
  return STATION_LABELS[+id] ?? `Four ${id}`
}

// "3, 4, 7"  →  "C10-3, Bac huile, C6-7"
export function stationsLabel(str) {
  if (!str) return ''
  return str.split(',').map((s) => stationLabel(s.trim())).join(', ')
}

export const CATEGORY_LABELS = {
  temperature: 'Température',
  puissance:   'Potentiel carbone',
  atmosphere:  'Sondes à oxygène',
}

// Ordre d'affichage des graphiques de série temporelle
export const CATEGORY_ORDER = ['temperature', 'puissance', 'atmosphere']

// Labels des équipements externes qui n'ont pas de nom de cycle (type EXT_*)
const STAR_STATION_LABELS = {
   7: 'Revenu C6-7',         // four de revenu sur chaîne
  95: 'Revenu Four 7',       // four de revenu externe
  96: 'Revenu Four 4',       // four de revenu externe
  97: 'Traitement air liquide',
  98: 'Trempe alu',
  99: 'Étuve — dégazage H₂',
}

// Remplace les cycles sans nom (***...) par un libellé lisible
// Accepte optionnellement la station pour les équipements externes connus
export function cleanCycle(cycle, station) {
  if (!cycle || !cycle.trim()) return 'Cycle non identifié'
  if (/^\*+$/.test(cycle.trim())) {
    const lbl = station !== undefined && station !== null
      ? STAR_STATION_LABELS[+station] : null
    return lbl || 'Cycle non identifié'
  }
  return cycle
}

// Icône selon la nature de l'opération (matching sur le nom du cycle)
export function cycleIcon(name) {
  if (!name) return '🔥'
  const u = name.toUpperCase()
  if (u.includes('LAVAGE'))                           return '🚿'
  if (u.includes('TREMPE'))                           return '💧'
  if (u.includes('REVENU'))                           return '♨️'
  if (u.includes('ETUVE') || u.includes('ÉTUVE'))     return '🌡️'
  if (u.includes('NITRU'))                            return '💨'
  if (u.includes('RECUIT') || u.includes('RECUISS'))  return '🔁'
  if (u.includes('CEMET') || u.includes('CARB'))      return '⚡'
  if (u.includes('CRYO') || u.includes('FROID') || u.includes('AIR LIQUIDE')
      || u.includes('TREMPE_AIR') || u.includes('TREMPE-AIR'))  return '❄️'
  if (u.includes('ETUVE') || u.includes('ÉTUVE') || u.includes('DEGAZAGE') || u.includes('DÉGAZAGE') || u.includes('SECHAGE') || u.includes('SÉCHAGE')) return '🌡️'
  if (u.includes('ESSAI') || u.includes('TEST'))      return '🧪'
  if (u.includes('CONTROL') || u.includes('CTRL'))    return '🔬'
  if (u.includes('ATTENTE') || u.includes('HEURES') || u.includes('-MIN') || u.includes('-MM') || u.includes('-H'))
                                                      return '⏱️'
  return '🔥'
}
