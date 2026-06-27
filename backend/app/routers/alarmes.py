from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.db import get_conn
from app.models import AlarmeItem, AlarmeListResponse

router = APIRouter()


@router.get("/alarmes", response_model=AlarmeListResponse)
def list_alarmes(
    code: Optional[str] = None,
    q: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    conn=Depends(get_conn),
):
    where = ["type_alarme = 'CiAdvancedAlarmState'"]
    params: list = []

    if code:
        where.append("code = %s")
        params.append(code)
    if q:
        like = f"%{q}%"
        where.append("(code LIKE %s OR description LIKE %s)")
        params.extend([like, like])
    if date_from:
        where.append("tps_apparition >= %s")
        params.append(date_from)
    if date_to:
        where.append("tps_apparition < %s")
        params.append(date_to + timedelta(days=1))

    where_sql = " AND ".join(where)

    with conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) AS n FROM alarmes WHERE {where_sql}", params)
        total = cur.fetchone()['n']

        cur.execute(f"""
            SELECT id, code, description,
                   tps_apparition, tps_disparition, duree_s, type_alarme
            FROM alarmes
            WHERE {where_sql}
            ORDER BY tps_apparition DESC
            LIMIT %s OFFSET %s
        """, params + [limit, offset])
        items = cur.fetchall()

    return {"total": total, "items": items}


@router.get("/alarmes/codes")
def list_codes(conn=Depends(get_conn)):
    """Liste des codes d'alarme distincts (CiAdvancedAlarmState uniquement)."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT code, MAX(description) AS description,
                   COUNT(*) AS nb, MAX(tps_apparition) AS derniere
            FROM alarmes
            WHERE code IS NOT NULL
              AND type_alarme = 'CiAdvancedAlarmState'
            GROUP BY code
            ORDER BY nb DESC
        """)
        return cur.fetchall()


@router.get("/alarmes/stats")
def alarm_stats(conn=Depends(get_conn)):
    """Statistiques globales + données graphiques pour le tableau de bord alarmes."""
    with conn.cursor() as cur:
        # KPI globaux
        cur.execute("""
            SELECT COUNT(*) AS total,
                   ROUND(AVG(duree_s))  AS duree_moy,
                   MAX(duree_s)         AS duree_max
            FROM alarmes
            WHERE type_alarme = 'CiAdvancedAlarmState'
        """)
        overview = cur.fetchone()

        # Top 5 codes par occurrence (Pareto)
        cur.execute("""
            SELECT code, MAX(description) AS description,
                   COUNT(*)             AS nb,
                   ROUND(AVG(duree_s))  AS duree_moy,
                   MAX(duree_s)         AS duree_max
            FROM alarmes
            WHERE code IS NOT NULL
              AND type_alarme = 'CiAdvancedAlarmState'
            GROUP BY code
            ORDER BY nb DESC
            LIMIT 5
        """)
        top5 = cur.fetchall()

        # 5 dernieres alarmes
        cur.execute("""
            SELECT code, description, tps_apparition, tps_disparition, duree_s
            FROM alarmes
            WHERE tps_apparition IS NOT NULL
              AND type_alarme = 'CiAdvancedAlarmState'
            ORDER BY tps_apparition DESC
            LIMIT 5
        """)
        dernieres = cur.fetchall()

        # Taux journalier (bar chart)
        cur.execute("""
            SELECT DATE(tps_apparition) AS jour, COUNT(*) AS nb
            FROM alarmes
            WHERE tps_apparition IS NOT NULL
              AND type_alarme = 'CiAdvancedAlarmState'
            GROUP BY jour
            ORDER BY jour
        """)
        par_jour = cur.fetchall()

        # Timeline scatter — top 10 codes seulement (lisibilite)
        cur.execute("""
            SELECT a.code, a.tps_apparition, a.duree_s
            FROM alarmes a
            JOIN (
                SELECT code FROM alarmes
                WHERE code IS NOT NULL
                  AND type_alarme = 'CiAdvancedAlarmState'
                GROUP BY code
                ORDER BY COUNT(*) DESC
                LIMIT 10
            ) top ON top.code = a.code
            WHERE a.tps_apparition IS NOT NULL
              AND a.type_alarme = 'CiAdvancedAlarmState'
            ORDER BY a.tps_apparition
        """)
        timeline = cur.fetchall()

    return {
        "total":      overview['total'],
        "duree_moy":  overview['duree_moy'],
        "duree_max":  overview['duree_max'],
        "top5":       top5,
        "dernieres":  dernieres,
        "par_jour":   par_jour,
        "timeline":   timeline,
    }
