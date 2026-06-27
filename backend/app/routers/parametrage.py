import fnmatch
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.db import get_conn


def _matches(cycle: str, pattern: str) -> bool:
    """Correspondance pattern/cycle.
    - Sans wildcard : recherche par contenance (C10-3 matche 300M-C10-3)
    - Avec * : glob standard (300M* matche 300M-C10-3, *C10-5 matche 300M-C10-5)
    """
    if '*' not in pattern:
        return pattern in cycle
    return fnmatch.fnmatch(cycle, pattern)

router = APIRouter()


class SeuilCreate(BaseModel):
    cycle_pattern: str
    tolerance_c: float
    description: Optional[str] = None


class SeuilUpdate(BaseModel):
    cycle_pattern: Optional[str] = None
    tolerance_c: float
    description: Optional[str] = None


def _resolve(cycle: str, conn) -> float:
    """Retourne la tolérance °C applicable pour un cycle donné."""
    with conn.cursor() as cur:
        # 1. Correspondance exacte
        cur.execute(
            "SELECT tolerance_c FROM param_seuils_temperature WHERE cycle_pattern = %s",
            [cycle],
        )
        row = cur.fetchone()
        if row:
            return row['tolerance_c']

        # 2. Toutes les règles non-défaut, plus long d'abord (plus spécifique)
        cur.execute("""
            SELECT cycle_pattern, tolerance_c
            FROM param_seuils_temperature
            WHERE cycle_pattern <> '*' AND cycle_pattern <> %s
            ORDER BY LENGTH(cycle_pattern) DESC
        """, [cycle])
        for r in cur.fetchall():
            if _matches(cycle, r['cycle_pattern']):
                return r['tolerance_c']

        # 3. Valeur par défaut
        cur.execute(
            "SELECT tolerance_c FROM param_seuils_temperature WHERE cycle_pattern = '*'"
        )
        row = cur.fetchone()
        return row['tolerance_c'] if row else 10.0


@router.get("/parametrage/seuils")
def list_seuils(conn=Depends(get_conn)):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT id, cycle_pattern, tolerance_c, description, updated_at
            FROM param_seuils_temperature
            ORDER BY CASE WHEN cycle_pattern = '*' THEN 1 ELSE 0 END,
                     LENGTH(cycle_pattern) DESC, cycle_pattern
        """)
        return cur.fetchall()


@router.get("/parametrage/seuils/resolve")
def resolve_seuil(cycle: str, conn=Depends(get_conn)):
    """Retourne la tolérance applicable pour le cycle donné."""
    return {"cycle": cycle, "tolerance_c": _resolve(cycle, conn)}


@router.post("/parametrage/seuils", status_code=201)
def create_seuil(body: SeuilCreate, conn=Depends(get_conn)):
    with conn.cursor() as cur:
        try:
            cur.execute("""
                INSERT INTO param_seuils_temperature (cycle_pattern, tolerance_c, description)
                VALUES (%s, %s, %s)
            """, [body.cycle_pattern, body.tolerance_c, body.description])
            conn.commit()
            row_id = cur.lastrowid
            cur.execute("SELECT * FROM param_seuils_temperature WHERE id = %s", [row_id])
            return cur.fetchone()
        except Exception as e:
            raise HTTPException(status_code=409,
                                detail=f"Ce motif existe déjà : {body.cycle_pattern}")


@router.put("/parametrage/seuils/{seuil_id}")
def update_seuil(seuil_id: int, body: SeuilUpdate, conn=Depends(get_conn)):
    with conn.cursor() as cur:
        # Protéger la règle par défaut '*' : on ne peut pas changer son motif
        cur.execute("SELECT cycle_pattern FROM param_seuils_temperature WHERE id = %s", [seuil_id])
        row = cur.fetchone()
        new_pattern = body.cycle_pattern or (row['cycle_pattern'] if row else None)
        if row and row['cycle_pattern'] == '*':
            new_pattern = '*'
        cur.execute("""
            UPDATE param_seuils_temperature
            SET cycle_pattern = %s, tolerance_c = %s, description = %s
            WHERE id = %s
        """, [new_pattern, body.tolerance_c, body.description, seuil_id])
        conn.commit()
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Règle introuvable")
        cur.execute("SELECT * FROM param_seuils_temperature WHERE id = %s", [seuil_id])
        return cur.fetchone()


# ── Paliers configurés par cycle ───────────────────────────────────

class PaliersCreate(BaseModel):
    cycle_pattern: str
    consignes: str       # ex: "760,871"
    description: Optional[str] = None


class PaliersUpdate(BaseModel):
    cycle_pattern: Optional[str] = None
    consignes: str
    description: Optional[str] = None


def _parse_consignes(s: str) -> list[float]:
    """'760, 871' → [760.0, 871.0]"""
    return [float(x.strip()) for x in s.split(',') if x.strip()]


@router.get("/parametrage/paliers")
def list_paliers(conn=Depends(get_conn)):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT id, cycle_pattern, consignes, description, updated_at
            FROM param_paliers_cycle
            ORDER BY LENGTH(cycle_pattern) DESC, cycle_pattern
        """)
        return cur.fetchall()


@router.get("/parametrage/paliers/resolve")
def resolve_paliers(cycle: str, conn=Depends(get_conn)):
    """Retourne les consignes configurées pour ce cycle (null = détection auto)."""
    with conn.cursor() as cur:
        # Exact match
        cur.execute(
            "SELECT consignes FROM param_paliers_cycle WHERE cycle_pattern = %s", [cycle]
        )
        row = cur.fetchone()
        if row:
            return {"cycle": cycle, "consignes": _parse_consignes(row['consignes'])}

        # Match (plus spécifique = plus long en premier)
        cur.execute("""
            SELECT cycle_pattern, consignes FROM param_paliers_cycle
            ORDER BY LENGTH(cycle_pattern) DESC
        """)
        for r in cur.fetchall():
            if _matches(cycle, r['cycle_pattern']):
                return {"cycle": cycle, "consignes": _parse_consignes(r['consignes'])}

    return {"cycle": cycle, "consignes": None}   # détection automatique


@router.post("/parametrage/paliers", status_code=201)
def create_paliers(body: PaliersCreate, conn=Depends(get_conn)):
    _parse_consignes(body.consignes)   # validation format
    with conn.cursor() as cur:
        try:
            cur.execute("""
                INSERT INTO param_paliers_cycle (cycle_pattern, consignes, description)
                VALUES (%s, %s, %s)
            """, [body.cycle_pattern,
                  ','.join(str(int(v)) for v in _parse_consignes(body.consignes)),
                  body.description])
            conn.commit()
            row_id = cur.lastrowid
            cur.execute("SELECT * FROM param_paliers_cycle WHERE id = %s", [row_id])
            return cur.fetchone()
        except Exception:
            raise HTTPException(status_code=409, detail=f"Ce motif existe déjà : {body.cycle_pattern}")


@router.put("/parametrage/paliers/{palier_id}")
def update_paliers(palier_id: int, body: PaliersUpdate, conn=Depends(get_conn)):
    _parse_consignes(body.consignes)
    with conn.cursor() as cur:
        cur.execute("SELECT cycle_pattern FROM param_paliers_cycle WHERE id = %s", [palier_id])
        row = cur.fetchone()
        new_pattern = body.cycle_pattern or (row['cycle_pattern'] if row else None)
        cur.execute("""
            UPDATE param_paliers_cycle
            SET cycle_pattern = %s, consignes = %s, description = %s WHERE id = %s
        """, [new_pattern,
              ','.join(str(int(v)) for v in _parse_consignes(body.consignes)),
              body.description, palier_id])
        conn.commit()
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Règle introuvable")
        cur.execute("SELECT * FROM param_paliers_cycle WHERE id = %s", [palier_id])
        return cur.fetchone()


@router.delete("/parametrage/paliers/{palier_id}", status_code=204)
def delete_paliers(palier_id: int, conn=Depends(get_conn)):
    with conn.cursor() as cur:
        cur.execute("DELETE FROM param_paliers_cycle WHERE id = %s", [palier_id])
        conn.commit()
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Règle introuvable")


@router.delete("/parametrage/seuils/{seuil_id}", status_code=204)
def delete_seuil(seuil_id: int, conn=Depends(get_conn)):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT cycle_pattern FROM param_seuils_temperature WHERE id = %s", [seuil_id]
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Règle introuvable")
        if row['cycle_pattern'] == '*':
            raise HTTPException(status_code=400, detail="La règle par défaut ne peut pas être supprimée")
        cur.execute("DELETE FROM param_seuils_temperature WHERE id = %s", [seuil_id])
        conn.commit()
