from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class Four(BaseModel):
    station: int
    nom_station: Optional[str] = None


class FourneeSummary(BaseModel):
    charge: str
    tps_deb: Optional[datetime] = None
    tps_fin: Optional[datetime] = None
    nb_passages: int = 0
    stations: Optional[str] = None
    nb_of: int = 0
    lots: Optional[str] = None
    statut: Optional[str] = None
    cycle_en_cours: Optional[str] = None
    has_nc: bool = False
    recette: Optional[str] = None
    recette_cycles: Optional[str] = None
    portique: Optional[int] = None


class FourneeListResponse(BaseModel):
    total: int
    items: list[FourneeSummary]


class RecetteStep(BaseModel):
    recette: Optional[str] = None
    bloc: Optional[int] = None
    type: Optional[int] = None
    cycle: Optional[str] = None
    deb_valid: Optional[datetime] = None
    fin_valid: Optional[datetime] = None


class RecettePlanStep(BaseModel):
    bloc: int
    type: Optional[int] = None
    cycle: Optional[str] = None
    fait_ou_pas: Optional[int] = None
    tps_deb: Optional[datetime] = None
    tps_fin: Optional[datetime] = None


class RecettePlan(BaseModel):
    recette: str
    terminee: bool
    steps: list[RecettePlanStep] = []


class OfAttache(BaseModel):
    lot: str
    piece: Optional[str] = None
    nuance: Optional[str] = None
    denomination: Optional[str] = None
    poids: Optional[float] = None
    tonnage: Optional[float] = None
    nbre: Optional[int] = None
    piece_recette: Optional[str] = None


class Passage(BaseModel):
    id: int
    station: Optional[int] = None
    tps_deb: Optional[datetime] = None
    tps_fin: Optional[datetime] = None
    cycle: Optional[str] = None


class FourneeDetail(BaseModel):
    charge: str

    charge_operateur: Optional[str] = None
    charge_date_creat: Optional[str] = None
    charge_numero: Optional[int] = None
    charge_portique: Optional[int] = None
    charge_nbre: Optional[int] = None

    of_list: list[OfAttache] = []
    passages: list[Passage] = []
    recette_steps: list[RecetteStep] = []
    recette_plan: Optional[RecettePlan] = None


class SeriesTag(BaseModel):
    tag_id: int
    name: str
    variable: str
    points: list[tuple[datetime, float]]


class SeriesResponse(BaseModel):
    station: int
    tps_deb: datetime
    tps_fin: datetime
    cycle: Optional[str] = None
    categories: dict[str, list[SeriesTag]]


class DerniereCharge(BaseModel):
    charge: str
    date_creat: Optional[str] = None
    stations: Optional[str] = None
    lots: Optional[str] = None
    nb_of: int = 0
    statut: Optional[str] = None
    cycle_en_cours: Optional[str] = None


class TopPiece(BaseModel):
    piece: str
    denomination: Optional[str] = None
    nuance: Optional[str] = None
    nb_lots: int = 0
    cum_pct: Optional[float] = None


class TopRecette(BaseModel):
    recette: str
    nb_utilisations: int = 0
    cum_pct: Optional[float] = None


class HebdoEntry(BaseModel):
    station: int
    jour: Optional[str] = None
    heure: Optional[str] = None
    mar_arr_att: Optional[str] = None
    genre_enr: Optional[int] = None
    cons1: Optional[int] = None
    cons2: Optional[int] = None


class EntretienItem(BaseModel):
    position: Optional[int] = None
    num: Optional[int] = None
    action: Optional[str] = None
    frequence: Optional[str] = None
    derniere_date: Optional[datetime] = None
    utilisateur: Optional[str] = None


class KpiData(BaseModel):
    charges_aujourd_hui: int = 0
    charges_en_cours: int = 0
    passages_semaine: int = 0
    duree_moy_min: Optional[float] = None


class RepartitionEtape(BaseModel):
    cycle: str
    nb: int = 0


class DashboardResponse(BaseModel):
    kpis: Optional[KpiData] = None
    repartition_etapes: list[RepartitionEtape] = []
    dernieres_charges: list[DerniereCharge] = []
    top_pieces: list[TopPiece] = []
    top_recettes: list[TopRecette] = []
    hebdo: list[HebdoEntry] = []
    entretien: list[EntretienItem] = []


class CycleSummary(BaseModel):
    cycle: str
    nb_occurrences: int = 0
    derniere_execution: Optional[datetime] = None


class CyclesResponse(BaseModel):
    items: list[CycleSummary] = []


class OverlayVariable(BaseModel):
    variable: str
    name: str
    points: list[tuple[float, float]]


class OverlayPassage(BaseModel):
    passage_id: int
    charge: str
    tps_deb: datetime
    tps_fin: datetime
    variables: list[OverlayVariable] = []


class OverlayResponse(BaseModel):
    station: int
    cycle: str
    passages: list[OverlayPassage] = []


class AlarmeItem(BaseModel):
    id: int
    code: Optional[str] = None
    description: Optional[str] = None
    tps_apparition: Optional[datetime] = None
    tps_disparition: Optional[datetime] = None
    duree_s: Optional[int] = None
    type_alarme: Optional[str] = None


class AlarmeListResponse(BaseModel):
    total: int
    items: list[AlarmeItem] = []


class NcDeclaration(BaseModel):
    id: int
    charge: str
    lot: Optional[str] = None
    date_declaration: Optional[datetime] = None
    nature: str
    description: Optional[str] = None
    operateur: Optional[str] = None
    statut: str = 'ouverte'
    action_corrective: Optional[str] = None
    date_cloture: Optional[datetime] = None


class NcCreate(BaseModel):
    lot: Optional[str] = None
    nature: str
    description: Optional[str] = None
    operateur: Optional[str] = None
