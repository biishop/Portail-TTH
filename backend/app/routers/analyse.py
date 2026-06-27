from fastapi import APIRouter, Depends, HTTPException, Query

from app.db import get_conn
from app.models import CyclesResponse, OverlayResponse

router = APIRouter()


@router.get("/analyse/cycles", response_model=CyclesResponse)
def list_cycles(station: int, conn=Depends(get_conn)):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT cycle, COUNT(DISTINCT tps_deb) AS nb_occurrences, MAX(tps_deb) AS derniere_execution
            FROM sup_histo
            WHERE station = %s
              AND cycle IS NOT NULL AND cycle <> '' AND cycle NOT LIKE '%%*%%'
              AND tps_deb IS NOT NULL AND tps_fin IS NOT NULL
            GROUP BY cycle
            ORDER BY nb_occurrences DESC
        """, [station])
        items = cur.fetchall()

    return {"items": items}


@router.get("/analyse/overlay", response_model=OverlayResponse)
def get_overlay(
    station: int,
    cycle: str,
    n: int = Query(10, ge=1, le=50),
    conn=Depends(get_conn),
):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT MIN(id) AS id, charge, tps_deb, MAX(tps_fin) AS tps_fin
            FROM sup_histo
            WHERE station = %s AND cycle = %s
              AND tps_deb IS NOT NULL AND tps_fin IS NOT NULL
            GROUP BY station, tps_deb, cycle
            ORDER BY tps_deb DESC
            LIMIT %s
        """, [station, cycle, n])
        passage_rows = cur.fetchall()
        if not passage_rows:
            raise HTTPException(status_code=404, detail="aucun passage pour ce cycle")

        cur.execute("""
            SELECT id, name, variable FROM tags
            WHERE equip_type = 'four' AND equip_id = %s AND category = 'temperature'
              AND variable NOT LIKE %s
            ORDER BY variable
        """, [station, '%secu%'])
        temp_tags = cur.fetchall()

        passages = []
        for p in passage_rows:
            tps_deb, tps_fin = p['tps_deb'], p['tps_fin']
            variables = []
            for tag in temp_tags:
                cur.execute("""
                    SELECT ts, ROUND(value, 1) AS value FROM mesures_temperature
                    WHERE tag_id = %s AND ts BETWEEN %s AND %s
                    ORDER BY ts
                """, [tag['id'], tps_deb, tps_fin])
                points = [
                    ((r['ts'] - tps_deb).total_seconds() / 60, r['value'])
                    for r in cur.fetchall()
                ]
                if points:
                    variables.append({'variable': tag['variable'], 'name': tag['name'], 'points': points})

            passages.append({
                'passage_id': p['id'],
                'charge': p['charge'],
                'tps_deb': tps_deb,
                'tps_fin': tps_fin,
                'variables': variables,
            })

    return {"station": station, "cycle": cycle, "passages": passages}


# ── Analyse portiques ──────────────────────────────────────────────

# ── Configuration des cycles ──────────────────────────────────────

# Tables de configuration avec métadonnées par colonne
CYCLE_SOURCES = {
    'cementation': {
        'table': 'sup_cement',
        'label': 'Cémentation',
        'has_bloc': True,
        'params': {
            'p2': ('Vitesse montée', '°C/min'),
            'p3': ('Température consigne', '°C'),
            'p5': ('Potentiel carbone', '%C'),
            'p7': ('Durée totale (bloc 0)', 's'),
            'p8': ('Mode atmosphère', ''),
            'p9': ('Type étape', ''),
        },
    },
    'revenu': {
        'table': 'sup_revenu',
        'label': 'Revenu',
        'has_bloc': True,
        'params': {
            'p2': ('Vitesse montée', '°C/min'),
            'p3': ('Température', '°C'),
            'p5': ('Durée (bloc 0)', 's'),
        },
    },
    'trempe': {
        'table': 'sup_trempe',
        'label': 'Trempe',
        'has_bloc': True,
        'params': {
            'p2': ('Durée ou débit', ''),
            'p3': ('Température', '°C'),
        },
    },
    'attente': {
        'table': 'sup_cycle_attente',
        'label': 'Attente',
        'has_bloc': False,
        'params': {
            'p1': ('Durée', 's'),
        },
    },
    'lavage': {
        'table': 'sup_lavage',
        'label': 'Lavage',
        'has_bloc': False,
        'params': {
            'p1': ('Paramètre 1', ''),
            'p2': ('Paramètre 2', ''),
            'p3': ('Paramètre 3', ''),
            'vit': ('Vitesse', ''),
        },
    },
    'n2hp': {
        'table': 'sup_cycle_n2hp',
        'label': 'N₂ HP',
        'has_bloc': True,
        'params': {
            'p1': ('Paramètre 1', ''),
            'p5': ('Pression', 'bar'),
        },
    },
    'cryogenique': {
        'table': 'sup_cycle_froid',
        'label': 'Cryogénique (air liquide)',
        'has_bloc': False,
        'params': {
            'p1': ('Durée', 's'),
        },
    },
    'prelavage': {
        'table': 'sup_cycle_prelav',
        'label': 'Pré-lavage',
        'has_bloc': False,
        'params': {
            'p1': ('Paramètre 1', ''),
            'p2': ('Paramètre 2', ''),
            'p3': ('Paramètre 3', ''),
        },
    },
    'lav_rev': {
        'table': 'sup_lav_rev',
        'label': 'Lavage + Revenu',
        'has_bloc': True,
        'params': {
            'p2': ('Vitesse montée', '°C/min'),
            'p3': ('Température', '°C'),
            'p5': ('Durée', 's'),
        },
    },
}


@router.get("/analyse/config-cycles/sources")
def config_sources(conn=Depends(get_conn)):
    """Liste des sources de configuration disponibles avec leur nombre de cycles actifs."""
    result = []
    with conn.cursor() as cur:
        for sid, meta in CYCLE_SOURCES.items():
            table = meta['table']
            try:
                cur.execute(
                    f"SELECT COUNT(DISTINCT cycle) n FROM `{table}` WHERE fin_valid IS NULL"
                )
                n = cur.fetchone()['n']
                if n > 0:
                    result.append({'id': sid, 'label': meta['label'],
                                   'table': table, 'nb_cycles': n})
            except Exception:
                pass
    return result


@router.get("/analyse/config-cycles/{source}")
def config_cycles(source: str, conn=Depends(get_conn)):
    """Cycles actifs pour une source de configuration."""
    meta = CYCLE_SOURCES.get(source)
    if not meta:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Source inconnue")
    table = meta['table']
    with conn.cursor() as cur:
        cur.execute(f"""
            SELECT DISTINCT cycle FROM `{table}`
            WHERE fin_valid IS NULL AND cycle IS NOT NULL AND cycle <> ''
            ORDER BY cycle
        """)
        cycles = [r['cycle'] for r in cur.fetchall()]
    return {'source': source, 'label': meta['label'],
            'params_meta': meta['params'], 'cycles': cycles}


@router.get("/analyse/config-cycles/{source}/{cycle}")
def config_cycle_detail(source: str, cycle: str, conn=Depends(get_conn)):
    """Paramètres d'un cycle spécifique."""
    meta = CYCLE_SOURCES.get(source)
    if not meta:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Source inconnue")
    table = meta['table']
    order = 'bloc,' if meta['has_bloc'] else ''
    with conn.cursor() as cur:
        cur.execute(f"""
            SELECT * FROM `{table}`
            WHERE cycle = %s AND fin_valid IS NULL
            ORDER BY {order} deb_valid DESC
        """, [cycle])
        rows = cur.fetchall()
    return {'source': source, 'cycle': cycle,
            'params_meta': meta['params'], 'rows': rows}


def _cycle_params(cycle: str, cur) -> dict:
    """Paramètres clés d'un cycle depuis les tables de config."""
    p = {}
    # Températures de palier (sup_cement)
    cur.execute("""
        SELECT p3 FROM sup_cement
        WHERE cycle = %s AND fin_valid IS NULL AND p3 > 0
        ORDER BY bloc
    """, [cycle])
    temps = list({round(r['p3']) for r in cur.fetchall() if r['p3'] > 0})
    if temps:
        p['temperatures'] = sorted(temps)

    # Potentiel carbone max (sup_cement)
    cur.execute("""
        SELECT MAX(p5) AS cp FROM sup_cement
        WHERE cycle = %s AND fin_valid IS NULL AND p5 > 0
    """, [cycle])
    r = cur.fetchone()
    if r and r['cp']:
        p['cp'] = r['cp']

    # Revenu — température (sup_revenu)
    if not temps:
        cur.execute("""
            SELECT p3 FROM sup_revenu
            WHERE cycle = %s AND fin_valid IS NULL AND p3 > 0 LIMIT 1
        """, [cycle])
        r = cur.fetchone()
        if r:
            p['temperatures'] = [round(r['p3'])]

    # Durée (sup_cycle_attente)
    cur.execute("""
        SELECT p1 FROM sup_cycle_attente
        WHERE cycle = %s AND fin_valid IS NULL LIMIT 1
    """, [cycle])
    r = cur.fetchone()
    if r and r['p1']:
        p['duree_s'] = int(r['p1'])

    return p


@router.get("/analyse/recettes")
def list_recettes(conn=Depends(get_conn)):
    """Retourne les recettes actives avec leurs étapes et paramètres de configuration."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT recette, bloc, type, cycle, deb_valid
            FROM sup_recette
            WHERE fin_valid IS NULL
              AND cycle IS NOT NULL AND cycle <> '' AND cycle NOT LIKE '%%*%%'
            ORDER BY recette, bloc
        """)
        rows = cur.fetchall()

        # Cache des paramètres par cycle
        cycles_seen = {r['cycle'] for r in rows}
        params_cache = {c: _cycle_params(c, cur) for c in cycles_seen}

    from collections import defaultdict
    recettes: dict = defaultdict(lambda: {'steps': [], 'deb_valid': None})
    for r in rows:
        nom = r['recette']
        recettes[nom]['deb_valid'] = recettes[nom]['deb_valid'] or r['deb_valid']
        recettes[nom]['steps'].append({
            'bloc':   r['bloc'],
            'cycle':  r['cycle'],
            'type':   r['type'],
            'params': params_cache.get(r['cycle'], {}),
        })

    return [
        {'recette': nom, 'deb_valid': v['deb_valid'], 'steps': v['steps']}
        for nom, v in sorted(recettes.items())
    ]


@router.get("/analyse/portiques")
def list_portiques(conn=Depends(get_conn)):
    """Liste des portiques avec leur nombre de fournées."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT portique, COUNT(DISTINCT charge) AS nb_charges
            FROM sup_charge
            WHERE portique IS NOT NULL AND portique > 0
            GROUP BY portique
            ORDER BY portique DESC
        """)
        return cur.fetchall()


@router.get("/analyse/portique/{portique_id}")
def get_portique_stats(portique_id: int, conn=Depends(get_conn)):
    """
    Statistiques de sollicitation d'un portique.

    Méthodologie (FEM 1.001 / ISO 4301) :
    - Chaque fournée = 1 cycle de levage
    - Tonnage = poids total des OF de la fournée (kg)
    - Indice de fatigue Miner relatif = Σ (Wi/Wmax)³
      (le cube de la charge relative — une charge double = 8× plus d'usure)
    """
    with conn.cursor() as cur:
        # Poids total par fournée (dédupliqué par charge-lot)
        cur.execute("""
            SELECT dl.charge, SUM(l.tonnage) AS total_poids
            FROM (
                SELECT DISTINCT sh.charge, sh.lot
                FROM sup_histo sh
                WHERE EXISTS (
                    SELECT 1 FROM sup_charge sc
                    WHERE sc.charge = sh.charge AND sc.portique = %s
                )
            ) dl
            JOIN sup_lot l ON l.lot = dl.lot
            WHERE l.tonnage IS NOT NULL AND l.tonnage > 0
            GROUP BY dl.charge
        """, [portique_id])
        poids_by_charge = {r['charge']: r['total_poids'] for r in cur.fetchall()}

        if not poids_by_charge:
            return {
                "portique": portique_id,
                "total_fournees": 0,
                "poids_cumule_kg": 0,
                "poids_moyen_kg": None,
                "poids_max_kg": None,
                "indice_fatigue": 0.0,
                "par_mois": [],
                "histogramme": [],
            }

        # Date de première utilisation par fournée
        cur.execute("""
            SELECT h.charge, MIN(h.tps_deb) AS date_debut
            FROM sup_histo h
            WHERE EXISTS (
                SELECT 1 FROM sup_charge sc
                WHERE sc.charge = h.charge AND sc.portique = %s
            ) AND h.tps_deb IS NOT NULL
            GROUP BY h.charge
        """, [portique_id])
        date_by_charge = {r['charge']: r['date_debut'] for r in cur.fetchall()}

    # ── Agrégation Python ──────────────────────────────────────────
    charges = [
        {'charge': c, 'date_debut': date_by_charge.get(c), 'total_poids': w}
        for c, w in poids_by_charge.items()
        if date_by_charge.get(c) is not None
    ]
    charges.sort(key=lambda x: x['date_debut'])

    poids_values = [c['total_poids'] for c in charges]
    total_fournees  = len(charges)
    poids_cumule    = sum(poids_values)
    poids_moyen     = poids_cumule / total_fournees if total_fournees else None
    poids_max       = max(poids_values) if poids_values else None

    # Indice de fatigue Miner relatif : Σ (Wi/Wmax)³
    indice_fatigue = sum((w / poids_max) ** 3 for w in poids_values) if poids_max else 0.0

    # ── Agrégation mensuelle ───────────────────────────────────────
    from collections import defaultdict
    monthly: dict = defaultdict(lambda: {'nb': 0, 'poids': 0.0})
    for c in charges:
        key = c['date_debut'].strftime('%Y-%m')
        monthly[key]['nb']    += 1
        monthly[key]['poids'] += c['total_poids']

    par_mois = [
        {'mois': k, 'nb_fournees': v['nb'], 'poids_kg': round(v['poids'], 1)}
        for k, v in sorted(monthly.items())
    ]

    # Cumulatif
    cum_fournees = 0
    cum_poids    = 0.0
    for m in par_mois:
        cum_fournees += m['nb_fournees']
        cum_poids    += m['poids_kg']
        m['cum_fournees'] = cum_fournees
        m['cum_poids_kg'] = round(cum_poids, 1)

    # ── Histogramme spectre de charge (10 buckets) ─────────────────
    if poids_max and poids_max > 0:
        bucket_size = poids_max / 10
        hist: dict = defaultdict(int)
        for w in poids_values:
            bucket = int(w / bucket_size)
            bucket = min(bucket, 9)  # dernier bucket inclus
            hist[bucket] += 1
        histogramme = [
            {
                'label':    f"{round(i * bucket_size / 1000, 1)}–{round((i + 1) * bucket_size / 1000, 1)} t",
                'poids_min': round(i * bucket_size),
                'poids_max': round((i + 1) * bucket_size),
                'nb':        hist.get(i, 0),
            }
            for i in range(10)
        ]
    else:
        histogramme = []

    return {
        "portique":       portique_id,
        "total_fournees": total_fournees,
        "poids_cumule_kg": round(poids_cumule, 1),
        "poids_moyen_kg":  round(poids_moyen, 1) if poids_moyen else None,
        "poids_max_kg":    round(poids_max, 1) if poids_max else None,
        "indice_fatigue":  round(indice_fatigue, 2),
        "par_mois":        par_mois,
        "histogramme":     histogramme,
    }
