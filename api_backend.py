#!/usr/bin/env python3
"""
Backend API - Conclusions Médicales
Version FINALE avec toutes les fonctionnalités
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional
import httpx
import json
import re

# ===== CONFIGURATION =====
SUPABASE_URL = "https://bnlybntkwazgcuatuplb.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJubHlibnRrd2F6Z2N1YXR1cGxiIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjYwNjU0NjUsImV4cCI6MjA4MTY0MTQ2NX0.b876YQvlECMZWxSzQG6z5i9wcCRba6_PA9g-BW0RLik"

app = FastAPI(title="API Conclusions", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = httpx.AsyncClient(timeout=30.0)

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

# ===== MODÈLES =====
class Categorie(BaseModel):
    nom: str
    table_name: str
    ordre: int

class Motif(BaseModel):
    id: str
    nom_motif: str
    ordre: int

class Bulle(BaseModel):
    titre: str
    contenu: str

class Module(BaseModel):
    type: str
    titre: str
    icon: str
    lignes: List[str]
    bulles: List[Bulle]

class Ordonnance(BaseModel):
    titre: str
    lignes: List[str]
    bulles: List[Bulle]

class CodeCIM(BaseModel):
    code: str
    libelle: str

class FusionRequest(BaseModel):
    table_principale: str
    motif_principal_id: str
    motifs_secondaires: List[Dict[str, str]] = []

class FusionResponse(BaseModel):
    modules: List[Module]
    ordonnances: List[Ordonnance]
    codes_cim: List[CodeCIM]

# ===== CONFIGURATION MODULES =====
MODULES = {
    'diagnostic': {'titre': 'DIAGNOSTIC', 'icon': '🔍', 'ordre': 1},
    'signes_gravite': {'titre': 'SIGNES DE GRAVITÉ', 'icon': '⚠️', 'ordre': 2},
    'soins_urgences': {'titre': 'AUX URGENCES', 'icon': '🏥', 'ordre': 3},
    'conduite_tenir': {'titre': 'CONDUITE À TENIR', 'icon': '📋', 'ordre': 4},
    'conseils': {'titre': 'CONSEILS', 'icon': '💡', 'ordre': 5},
    'suivi': {'titre': 'SUIVI', 'icon': '📅', 'ordre': 6},
    'consignes_reconsultation': {'titre': 'CONSIGNES DE RECONSULTATION', 'icon': '🚨', 'ordre': 7}
}

# ===== FONCTIONS DE PARSING =====

def parse_bulles(texte: str) -> tuple[str, List[Bulle]]:
    """
    Extrait les bulles du format: BULLE : titre : contenu FIN
    Retourne: (texte_nettoyé, liste_bulles)
    """
    if not texte:
        return "", []
    
    bulles = []
    texte_clean = texte
    
    # Regex pour BULLE : titre : contenu FIN
    pattern = r'BULLE\s*:\s*([^:]+?)\s*:\s*(.*?)\s*FIN'
    
    for match in re.finditer(pattern, texte, re.IGNORECASE | re.DOTALL):
        titre = match.group(1).strip()
        contenu = match.group(2).strip()
        bulles.append(Bulle(titre=titre, contenu=contenu))
    
    # Supprimer toutes les bulles du texte
    texte_clean = re.sub(pattern, '', texte_clean, flags=re.IGNORECASE | re.DOTALL)
    texte_clean = ' '.join(texte_clean.split())  # Normaliser espaces
    
    return texte_clean, bulles

def extraire_lignes(texte: str) -> List[str]:
    """
    Sépare le texte en lignes distinctes.
    Critères: retour à la ligne OU point suivi d'espace
    """
    if not texte:
        return []
    
    lignes = []
    
    # Séparer d'abord par retours à la ligne
    parties = texte.split('\n')
    
    for partie in parties:
        partie = partie.strip()
        if not partie:
            continue
        
        # Si la partie contient des points, séparer par points
        if '.' in partie:
            # Split par point + espace ou point + fin
            sous_parties = re.split(r'\.\s+', partie)
            for sp in sous_parties:
                sp = sp.strip()
                if sp:
                    # Ajouter le point si manquant
                    if not sp.endswith('.'):
                        sp += '.'
                    lignes.append(sp)
        else:
            # Ajouter point si manquant
            if not partie.endswith('.'):
                partie += '.'
            lignes.append(partie)
    
    return lignes

def supprimer_doublons(lignes: List[str]) -> List[str]:
    """Supprime les lignes en double en préservant l'ordre"""
    vues = set()
    resultat = []
    
    for ligne in lignes:
        # Normaliser pour comparaison
        norm = ligne.lower().strip()
        if norm not in vues:
            vues.add(norm)
            resultat.append(ligne)
    
    return resultat

def parse_codes_cim(texte: str) -> List[CodeCIM]:
    """Parse les codes CIM-10"""
    if not texte:
        return []
    
    codes = []
    # Pattern: CODE : Libellé
    pattern = r'([A-Z]\d{2,3}(?:\.\d)?)\s*:\s*([^\n]+)'
    
    for match in re.finditer(pattern, texte):
        code = match.group(1).strip()
        libelle = match.group(2).strip()
        codes.append(CodeCIM(code=code, libelle=libelle))
    
    return codes

# ===== ENDPOINTS =====

@app.get("/")
async def root():
    return {
        "service": "API Conclusions Médicales",
        "version": "1.0.0",
        "status": "running"
    }

@app.get("/health")
async def health():
    try:
        r = await client.get(f"{SUPABASE_URL}/rest/v1/vue_categories?select=count", headers=HEADERS)
        if r.status_code == 200:
            return {"status": "healthy", "database": "connected"}
        return {"status": "degraded"}
    except:
        return {"status": "unhealthy"}

@app.get("/categories", response_model=List[Categorie])
async def get_categories():
    try:
        r = await client.get(
            f"{SUPABASE_URL}/rest/v1/vue_categories?select=*&order=ordre.asc",
            headers=HEADERS
        )
        r.raise_for_status()
        return r.json()
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/motifs/{table_name}", response_model=List[Motif])
async def get_motifs(table_name: str):
    try:
        r = await client.get(
            f"{SUPABASE_URL}/rest/v1/{table_name}?select=id,nom_motif,ordre&order=ordre.asc",
            headers=HEADERS
        )
        r.raise_for_status()
        return r.json()
    except Exception as e:
        raise HTTPException(500, str(e))

async def get_motif_complet(table: str, id: str) -> Dict:
    """Récupère un motif avec tous ses champs"""
    try:
        r = await client.get(
            f"{SUPABASE_URL}/rest/v1/{table}?id=eq.{id}&select=*",
            headers=HEADERS
        )
        r.raise_for_status()
        data = r.json()
        if not data:
            raise HTTPException(404, "Motif introuvable")
        return data[0]
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/fusion", response_model=FusionResponse)
async def fusion(req: FusionRequest):
    """Fusionne les motifs et génère la conclusion"""
    try:
        # Récupérer motif principal
        motif_principal = await get_motif_complet(req.table_principale, req.motif_principal_id)
        
        tous_motifs = [motif_principal]
        
        # Récupérer motifs secondaires
        for ms in req.motifs_secondaires:
            motif = await get_motif_complet(ms['table'], ms['id'])
            tous_motifs.append(motif)
        
        # === FUSION DES MODULES ===
        modules_result = []
        
        for module_type, config in MODULES.items():
            toutes_lignes = []
            toutes_bulles = []
            
            for idx, motif in enumerate(tous_motifs):
                is_principal = (idx == 0)
                
                # Diagnostic et signes_gravite : fusion de tous
                if module_type in ['diagnostic', 'signes_gravite']:
                    if motif.get(module_type):
                        texte = motif[module_type]
                        texte_clean, bulles = parse_bulles(texte)
                        lignes = extraire_lignes(texte_clean)
                        toutes_lignes.extend(lignes)
                        toutes_bulles.extend(bulles)
                
                # Autres modules : uniquement principal
                elif is_principal and motif.get(module_type):
                    texte = motif[module_type]
                    texte_clean, bulles = parse_bulles(texte)
                    lignes = extraire_lignes(texte_clean)
                    toutes_lignes.extend(lignes)
                    toutes_bulles.extend(bulles)
            
            # Supprimer doublons
            lignes_uniques = supprimer_doublons(toutes_lignes)
            
            if lignes_uniques:
                modules_result.append(Module(
                    type=module_type,
                    titre=config['titre'],
                    icon=config['icon'],
                    lignes=lignes_uniques,
                    bulles=toutes_bulles
                ))
        
        # === FUSION DES ORDONNANCES ===
        ordonnances_result = []
        ordos_vues = set()
        
        for motif in tous_motifs:
            if not motif.get('ordonnances'):
                continue
            
            ordos = motif['ordonnances']
            if isinstance(ordos, str):
                try:
                    ordos = json.loads(ordos)
                except:
                    continue
            
            for titre, contenu in ordos.items():
                if not contenu or not str(contenu).strip():
                    continue
                
                contenu_str = str(contenu)
                texte_clean, bulles = parse_bulles(contenu_str)
                lignes = extraire_lignes(texte_clean)
                
                # Clé unique
                key = f"{titre}_{texte_clean[:30]}"
                
                if key not in ordos_vues:
                    ordos_vues.add(key)
                    ordonnances_result.append(Ordonnance(
                        titre=titre.replace('_', ' ').title(),
                        lignes=lignes,
                        bulles=bulles
                    ))
        
        # === CODES CIM ===
        codes_result = []
        codes_vus = set()
        
        for motif in tous_motifs:
            if motif.get('codage_cim10'):
                codes = parse_codes_cim(motif['codage_cim10'])
                for code in codes:
                    if code.code not in codes_vus:
                        codes_vus.add(code.code)
                        codes_result.append(code)
        
        return FusionResponse(
            modules=modules_result,
            ordonnances=ordonnances_result,
            codes_cim=codes_result
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Erreur: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    print("🚀 Démarrage API Conclusions Médicales")
    print(f"📊 Supabase: {SUPABASE_URL}")
    uvicorn.run(app, host="0.0.0.0", port=8000)
