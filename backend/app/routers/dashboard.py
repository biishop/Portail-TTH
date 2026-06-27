from fastapi import APIRouter, Depends

from app.db import get_conn
from app.models import DashboardResponse

router = APIRouter()

JOURS = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']
MAR_ARR_ATT = {0: 'Marche', 1: 'Arrêt', 2: 'Attente'}


def with_cum_pct(rows, key, total):
    cum = 0
    result = []
    for row in rows:
        cum += row[key]
        result.append({**row, 'cum_pct': round(cum / total * 100, 1) if total else None})
    return result


def format_frequence(frequence_jour, frequence_mois):
    if frequence_jour == 1:
        return 'Quotidien'
    if frequence_jour == 7:
        return 'Hebdomadaire'
    if frequence_jour:
        return f'Tous les {frequence_jour} jours'
    if frequence_mois == 3:
        return 'Trimestriel'
    if frequence_mois == 6:
        return 'Semestriel'
    if frequence_mois == 12:
        return 'Annuel'
    if frequence_mois:
        return f'Tous les {frequence_mois} mois'
    return None


@router.get("/dashboard", response_model=DashboardResponse)
def get_dashboard(conn=Depends(get_conn)):
    with conn.cursor() as cur:
        # ── KPIs ─────────────────────────────────────────────────────
        cur.execute("""
            SELECT COUNT(DISTINCT charge) AS n FROM sup_histo
            WHERE DATE(tps_deb) = CURDATE()
        """)
        charges_aujourd_hui = cur.fetchone()['n']

        cur.execute("""
            SELECT COUNT(DISTINCT charge) AS n FROM sup_histo
            WHERE tps_fin IS NULL
              AND tps_deb >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
              AND cycle <> 'LAVAGE_LONG' AND cycle NOT LIKE '%%*%%'
        """)
        charges_en_cours = cur.fetchone()['n']

        cur.execute("""
            SELECT COUNT(DISTINCT station, tps_deb, cycle) AS n FROM sup_histo
            WHERE tps_deb >= DATE_SUB(CURDATE(), INTERVAL WEEKDAY(CURDATE()) DAY)
              AND cycle NOT LIKE '%%*%%'
        """)
        passages_semaine = cur.fetchone()['n']

        cur.execute("""
            SELECT AVG(duree) AS avg_min FROM (
                SELECT TIMESTAMPDIFF(MINUTE, MIN(tps_deb), MAX(tps_fin)) AS duree
                FROM sup_histo
                WHERE tps_fin IS NOT NULL
                  AND tps_deb >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
                  AND cycle NOT LIKE '%%*%%' AND cycle <> 'LAVAGE_LONG'
                GROUP BY station, tps_deb, cycle
                HAVING duree > 0
            ) d
        """)
        duree_moy = cur.fetchone()['avg_min']

        kpis = {
            'charges_aujourd_hui': charges_aujourd_hui,
            'charges_en_cours':    charges_en_cours,
            'passages_semaine':    passages_semaine,
            'duree_moy_min':       round(duree_moy, 1) if duree_moy else None,
        }

        # ── Répartition cycles en cours ───────────────────────────────
        cur.execute("""
            SELECT cycle, COUNT(DISTINCT charge) AS nb FROM sup_histo
            WHERE tps_fin IS NULL
              AND tps_deb >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
              AND cycle IS NOT NULL AND cycle <> '' AND cycle <> 'LAVAGE_LONG'
              AND cycle NOT LIKE '%%*%%'
            GROUP BY cycle
            ORDER BY nb DESC
        """)
        repartition_etapes = cur.fetchall()

        # ── Dernières charges ─────────────────────────────────────────
        cur.execute("""
            SELECT h.charge,
                   (SELECT date_creat FROM sup_charge
                    WHERE charge = h.charge ORDER BY id DESC LIMIT 1) AS date_creat,
                   GROUP_CONCAT(DISTINCT h.station ORDER BY h.station SEPARATOR ', ') AS stations,
                   GROUP_CONCAT(DISTINCT h.lot ORDER BY h.lot SEPARATOR ', ') AS lots,
                   COUNT(DISTINCT h.lot) AS nb_of,
                   COALESCE(
                     (SELECT pg.cycle FROM sup_plt_gen pg
                      WHERE pg.charge = h.charge AND pg.fait_ou_pas = 0
                      ORDER BY pg.bloc LIMIT 1),
                     (SELECT sh.cycle FROM sup_histo sh
                      WHERE sh.charge = h.charge AND sh.tps_fin IS NULL
                      ORDER BY sh.tps_deb DESC LIMIT 1)
                   ) AS cycle_en_cours,
                   CASE
                     WHEN SUM(CASE WHEN h.tps_fin IS NULL AND h.cycle <> 'LAVAGE_LONG' THEN 1 ELSE 0 END) > 0
                          OR COALESCE((SELECT SUM(CASE WHEN pg.fait_ou_pas = 0 AND pg.cycle <> 'LAVAGE_LONG'
                                                       THEN 1 ELSE 0 END)
                                       FROM sup_plt_gen pg WHERE pg.charge = h.charge), 0) > 0
                          THEN 'en_cours'
                     WHEN SUM(CASE WHEN h.tps_fin IS NULL AND h.cycle = 'LAVAGE_LONG' THEN 1 ELSE 0 END) > 0
                          OR COALESCE((SELECT SUM(CASE WHEN pg.fait_ou_pas = 0 AND pg.cycle = 'LAVAGE_LONG'
                                                       THEN 1 ELSE 0 END)
                                       FROM sup_plt_gen pg WHERE pg.charge = h.charge), 0) > 0
                          THEN 'lavage'
                     ELSE 'termine'
                   END AS statut
            FROM sup_histo h
            GROUP BY h.charge
            ORDER BY h.charge + 0 DESC
            LIMIT 10
        """)
        dernieres_charges = cur.fetchall()

        # Top 10 references pieces les plus representees parmi les OF (sup_lot),
        # en normalisant le bourrage de '-' en fin de reference.
        cur.execute("""
            SELECT TRIM(TRAILING '-' FROM l.piece) AS piece,
                   COUNT(*) AS nb_lots,
                   MAX(p.denomination) AS denomination,
                   MAX(p.nuance) AS nuance
            FROM sup_lot l
            LEFT JOIN sup_piece p ON p.piece = l.piece
            WHERE l.piece IS NOT NULL AND l.piece <> ''
            GROUP BY piece
            ORDER BY nb_lots DESC
            LIMIT 10
        """)
        top_pieces_rows = cur.fetchall()

        cur.execute("""
            SELECT COUNT(*) AS total FROM sup_lot WHERE piece IS NOT NULL AND piece <> ''
        """)
        total_lots = cur.fetchone()['total']
        top_pieces = with_cum_pct(top_pieces_rows, 'nb_lots', total_lots)

        # Top 10 recettes (cycles four) les plus utilisees, hors LAVAGE_LONG
        # et hors valeurs de bourrage ('***************').
        cur.execute("""
            SELECT cycle AS recette, COUNT(*) AS nb_utilisations
            FROM sup_histo
            WHERE cycle IS NOT NULL AND cycle <> '' AND cycle <> 'LAVAGE_LONG'
              AND cycle NOT LIKE '%*%'
            GROUP BY cycle
            ORDER BY nb_utilisations DESC
            LIMIT 10
        """)
        top_recettes_rows = cur.fetchall()

        cur.execute("""
            SELECT COUNT(*) AS total
            FROM sup_histo
            WHERE cycle IS NOT NULL AND cycle <> '' AND cycle <> 'LAVAGE_LONG'
              AND cycle NOT LIKE '%*%'
        """)
        total_cycles = cur.fetchone()['total']
        top_recettes = with_cum_pct(top_recettes_rows, 'nb_utilisations', total_cycles)

        # Programme hebdomadaire (sup_hebdo). mar_arr_att et jour decodes
        # litteralement d'apres le nom des champs (MARche/ARRet/ATTente,
        # jour de la semaine 0=Lundi).
        cur.execute("""
            SELECT station, jour, hh, mn, mar_arr_att, genre_enr, cons1, cons2
            FROM sup_hebdo
            ORDER BY station, jour, hh, mn
        """)
        hebdo = []
        for row in cur.fetchall():
            hebdo.append({
                'station': row['station'],
                'jour': JOURS[row['jour']] if row['jour'] is not None and 0 <= row['jour'] < 7 else None,
                'heure': f"{row['hh']:02d}:{row['mn']:02d}" if row['hh'] is not None and row['mn'] is not None else None,
                'mar_arr_att': MAR_ARR_ATT.get(row['mar_arr_att']),
                'genre_enr': row['genre_enr'],
                'cons1': row['cons1'],
                'cons2': row['cons2'],
            })

        # Top 10 du plan d'entretien (sup_entretien), les plus "importants"
        # = les plus frequents (quotidien/hebdomadaire avant trimestriel...).
        cur.execute("""
            SELECT position, num, action_francais, frequence_jour, frequence_mois,
                   derniere_date, utilisateur
            FROM sup_entretien
            ORDER BY
                CASE WHEN frequence_jour > 0 THEN frequence_jour ELSE frequence_mois * 30 END ASC,
                position, num
            LIMIT 10
        """)
        entretien = []
        for row in cur.fetchall():
            entretien.append({
                'position': row['position'],
                'num': row['num'],
                'action': row['action_francais'],
                'frequence': format_frequence(row['frequence_jour'], row['frequence_mois']),
                'derniere_date': row['derniere_date'],
                'utilisateur': row['utilisateur'],
            })

    return {
        "kpis": kpis,
        "repartition_etapes": repartition_etapes,
        "dernieres_charges": dernieres_charges,
        "top_pieces": top_pieces,
        "top_recettes": top_recettes,
        "hebdo": hebdo,
        "entretien": entretien,
    }
