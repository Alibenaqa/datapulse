# DataPulse — Plateforme ML Temps Réel

> Projet complet de Data Engineering + Machine Learning + API, construit session par session.

---

## Table des matières

1. [C'est quoi ce projet ?](#cest-quoi-ce-projet-)
2. [Lexique — comprendre les termes](#lexique--comprendre-les-termes)
3. [Architecture globale](#architecture-globale)
4. [Session 1 — Kafka : l'ingestion de données](#session-1--kafka--lingestion-de-données)
5. [Session 2 — Feature Store : préparer les données pour le ML](#session-2--feature-store--préparer-les-données-pour-le-ml)
6. [Session 3 — ML Pipeline : entraîner et sauvegarder un modèle](#session-3--ml-pipeline--entraîner-et-sauvegarder-un-modèle)
7. [Session 4 — FastAPI : exposer le modèle via une API](#session-4--fastapi--exposer-le-modèle-via-une-api)
8. [Session 5 — Monitoring : surveillance du drift](#session-5--monitoring--surveillance-du-drift)
9. [Session 6 — LLM Layer : insights IA avec Claude](#session-6--llm-layer--insights-ia-avec-claude)
10. [Installation et lancement](#installation-et-lancement)
11. [Structure des fichiers](#structure-des-fichiers)

---

## C'est quoi ce projet ?

DataPulse simule ce que font les équipes Data/ML dans une vraie entreprise fintech :

1. Des **prix boursiers** arrivent en temps réel (toutes les secondes)
2. On **calcule des indicateurs** financiers automatiquement
3. Un **modèle ML prédit** si le prix va monter ou baisser
4. Une **API** répond à ces prédictions en quelques millisecondes
5. On **surveille** que le modèle ne se dégrade pas dans le temps
6. Un **LLM (Claude)** analyse les alertes et génère des recommandations en langage naturel

---

## Lexique — comprendre les termes

### ML (Machine Learning)
**Abréviation de Machine Learning = Apprentissage Automatique**

C'est la capacité d'un programme à **apprendre à partir de données** sans être explicitement programmé pour chaque cas.

**Exemple concret :**
- Sans ML : tu codes manuellement "si SMA5 > SMA20 alors hausse"
- Avec ML : tu donnes au programme 10 000 exemples passés (indicateurs + résultat réel), et il apprend lui-même quelles règles fonctionnent le mieux

Dans DataPulse, le modèle ML apprend à partir de données historiques de prix pour prédire la direction future.

---

### RandomForest (Forêt Aléatoire)
C'est l'algorithme ML qu'on utilise dans ce projet.

**Imagine :**
- 1 arbre de décision = 1 expert qui pose des questions ("SMA5 > 190 ? volatilité < 1.5 ?") et arrive à une conclusion
- RandomForest = 100 experts qui votent → on prend la décision majoritaire

C'est plus fiable qu'un seul expert car les erreurs individuelles se compensent.

---

### Kafka
**Un système de messagerie en temps réel**, comme une file d'attente géante.

**Analogie :** Kafka c'est comme un réseau postal ultra-rapide :
- Le **producteur** (`producer.py`) = l'expéditeur qui envoie des lettres (ticks de prix)
- Le **topic** `stock-prices` = la boîte aux lettres
- Le **consommateur** (`consumer.py`) = le destinataire qui lit les lettres

Kafka garantit qu'aucun message n'est perdu, même si le consommateur est temporairement hors ligne.

---

### Feature (Indicateur)
Une **feature** = une variable calculée à partir des données brutes, utile pour le ML.

Dans notre cas, à partir des prix bruts on calcule :
- **SMA5** = moyenne des 5 derniers prix (lisse le bruit)
- **SMA20** = moyenne des 20 derniers prix (tendance plus longue)
- **Volatilité** = à quel point le prix fluctue (agitation du marché)
- **price_change_pct** = variation en % par rapport au tick précédent

Les modèles ML ne travaillent pas directement sur les prix bruts — ils ont besoin de ces indicateurs calculés.

---

### Feature Store
Un **entrepôt de features** — un endroit centralisé qui stocke les indicateurs calculés.

On a deux types de stockage :
- **Redis (online store)** = mémoire vive ultra-rapide → pour les prédictions en temps réel
- **DuckDB (offline store)** = base de données sur disque → pour l'entraînement des modèles

**Pourquoi deux stores ?**
- Redis répond en < 1ms (indispensable pour l'API)
- DuckDB peut stocker des millions de lignes et faire des requêtes complexes

---

### MLflow
Un **outil de suivi d'expériences ML**, comme un carnet de laboratoire numérique.

À chaque entraînement, MLflow enregistre automatiquement :
- Les **paramètres** utilisés (ex: 100 arbres, profondeur max 6)
- Les **métriques** (accuracy, F1, ROC-AUC)
- Le **modèle** sauvegardé sur disque
- Les **artefacts** (fichiers de log, graphiques)

Ainsi tu peux comparer tous tes entraînements et retrouver le meilleur modèle.

---

### API (Application Programming Interface)
Une **interface** qui permet à d'autres programmes de communiquer avec le modèle ML.

**Analogie :** L'API c'est comme le guichet d'une banque :
- Tu arrives avec une demande (les indicateurs d'une action)
- Le guichetier (FastAPI) consulte le modèle
- Il te répond avec une prédiction (UP ou DOWN)

Tout se passe via HTTP, le même protocole que ton navigateur web.

---

### A/B Testing
Comparer **deux versions d'un modèle** sur les mêmes données.

- **Modèle A** = version "production" (actuellement en service)
- **Modèle B** = version "staging" (nouveau candidat)

On compare leurs prédictions pour valider que le nouveau modèle est au moins aussi bon avant de le remplacer.

---

### Accuracy, F1, ROC-AUC
Des métriques pour mesurer la qualité d'un modèle de classification :

| Métrique | Ce qu'elle mesure | Interprétation |
|----------|-------------------|----------------|
| **Accuracy** | % de prédictions correctes | 0.53 = 53% de bonnes réponses |
| **F1** | Équilibre précision/rappel | Utile si les classes sont déséquilibrées |
| **ROC-AUC** | Capacité à distinguer UP/DOWN | 0.5 = hasard, 1.0 = parfait |

> Note : 53% d'accuracy sur des marchés financiers, c'est déjà significatif — les marchés sont proches du hasard.

---

## Architecture globale

```
Prix réels/simulés
        │
        ▼
┌───────────────┐     ┌────────────────┐
│   Kafka       │────▶│  Consumer      │──▶ data/raw/AAPL/2026-04-19.jsonl
│  (transport)  │     │  (Session 1)   │
└───────────────┘     └────────────────┘
        │
        ▼
┌───────────────────────────────────────┐
│         Feature Pipeline (Session 2)  │
│  Kafka → FeatureEngine → calcul SMA   │
│                 │              │      │
│                 ▼              ▼      │
│           Redis (online)  DuckDB      │
│           features:AAPL   (offline)   │
└───────────────────────────────────────┘
                                │
                                ▼
┌───────────────────────────────────────┐
│         ML Pipeline (Session 3)       │
│  DuckDB → RandomForest → MLflow       │
│                              │        │
│                    model registry     │
│                  (staging/production) │
└───────────────────────────────────────┘
                                │
                                ▼
┌───────────────────────────────────────┐
│         FastAPI (Session 4)           │
│  POST /predict → UP ou DOWN          │
│  GET  /ab-test → prod vs staging     │
└───────────────────────────────────────┘
                                │
                    ┌───────────┴────────────┐
                    ▼                        ▼
┌───────────────────────────┐  ┌────────────────────────────┐
│   Monitoring (Session 5)  │  │   LLM Layer (Session 6)    │
│  Evidently drift detect   │  │  RAG → alerts.jsonl        │
│  alerts.jsonl             │→ │  Claude API (streaming)    │
│  HTML reports             │  │  GET /insights/AAPL        │
└───────────────────────────┘  └────────────────────────────┘
```

---

## Session 1 — Kafka : l'ingestion de données

**Objectif :** recevoir des prix boursiers en temps réel et les sauvegarder.

### `ingestion/config.py`
Centralise toutes les variables de configuration (adresse Kafka, nom du topic, symboles...).
Utilise des variables d'environnement pour ne pas coder en dur des valeurs sensibles.

### `ingestion/producer.py`
**Le générateur de données.** Simule un flux de prix boursiers pour 6 actions (AAPL, GOOG, MSFT, AMZN, TSLA, NVDA).

Fonctions clés :
- `simulate_tick()` : génère un tick de marché via une **marche aléatoire gaussienne** (±0.5% par tick). C'est le modèle mathématique de base des prix financiers.
- `create_producer()` : crée la connexion Kafka avec retry automatique
- `run()` : boucle principale qui envoie 1 tick/seconde par symbole

### `ingestion/consumer.py`
**Le récepteur.** Lit les messages depuis Kafka et les écrit sur le disque.

Format de sortie : **JSONL** (JSON Lines) — un objet JSON par ligne, partitionné par symbole et par date :
```
data/raw/AAPL/2026-04-19.jsonl
data/raw/TSLA/2026-04-19.jsonl
```

Ce format est directement lisible par DuckDB en Session 2, sans transformation.

---

## Session 2 — Feature Store : préparer les données pour le ML

**Objectif :** transformer les prix bruts en indicateurs utiles pour le modèle.

### `feature_store/features.py`
Le **moteur de calcul des features**.

Classes :
- `SymbolBuffer` : maintient un buffer glissant des N derniers prix pour chaque symbole. Calcule :
  - `sma(window)` : moyenne simple sur `window` ticks
  - `volatility(window)` : écart-type sur `window` ticks (mesure l'agitation)
  - `price_change_pct()` : variation % par rapport au tick précédent
- `FeatureEngine` : instancie un buffer par symbole, produit un `FeatureVector` à chaque tick

`FeatureVector` : la structure de données qui contient toutes les features d'un tick.

### `feature_store/online_store.py`
**Redis — store temps réel.**

Stratégie de stockage :
- `features:AAPL` → Hash Redis avec les dernières features (TTL 1h)
- `features:history:AAPL` → Liste des 100 derniers vecteurs

Méthodes :
- `write(fv)` : écrit atomiquement via pipeline Redis
- `get_latest(symbol)` : récupère les dernières features en < 1ms
- `get_history(symbol, n)` : retourne les n derniers vecteurs
- `list_symbols()` : liste tous les symboles présents

### `feature_store/offline_store.py`
**DuckDB — store analytique.**

DuckDB peut lire directement les fichiers JSONL sans chargement :
```sql
SELECT * FROM read_json_auto('data/raw/AAPL/2026-04-19.jsonl')
```

Méthodes :
- `write(fv)` : persiste un FeatureVector dans la table SQL
- `query_raw(symbol, date)` : lit les ticks bruts depuis JSONL
- `get_training_dataset(symbol)` : retourne les données propres pour l'entraînement (sans lignes incomplètes)
- `stats()` : nombre de lignes et symboles stockés

### `feature_store/pipeline.py`
**Le chef d'orchestre.** Consomme Kafka → calcule les features → écrit dans Redis ET DuckDB en parallèle.

---

## Session 3 — ML Pipeline : entraîner et sauvegarder un modèle

**Objectif :** apprendre à partir des données historiques pour prédire la direction future.

### `ml/config.py`
Variables ML : URI MLflow, nom de l'expérience, hyperparamètres du RandomForest, seuil de promotion.

### `ml/data_prep.py`
**Préparation des données d'entraînement.**

Deux sources :
1. **DuckDB** (données réelles) si suffisamment de ticks disponibles (≥ 100)
2. **Synthétique** (marche aléatoire) en fallback pour les tests

Variable cible calculée :
```python
target = 1 si prix_suivant > prix_actuel  # hausse
target = 0 si prix_suivant ≤ prix_actuel  # baisse
```

Split temporel (pas de `train_test_split` aléatoire) :
- 80% premiers ticks → entraînement
- 20% derniers ticks → test

> **Pourquoi temporel ?** Mélanger les données passerait de futurs dans le passé (data leakage), ce qui gonflerait artificiellement les métriques.

### `ml/train.py`
**Le pipeline d'entraînement complet.**

Étapes dans un `mlflow.start_run()` :
1. Charge les données (`get_training_data`)
2. Entraîne un `RandomForestClassifier`
3. Évalue sur le set de test (accuracy, precision, recall, F1, ROC-AUC)
4. Logue tout dans MLflow (params + métriques + modèle)
5. Tag le run `ready_for_staging=True` si l'accuracy dépasse le seuil (0.52)

### `ml/registry.py`
**Gestion du cycle de vie du modèle.**

Utilise les **aliases MLflow** (nouveauté MLflow 3.x — remplace les stages dépréciés) :
- `staging` → modèle candidat, validé mais pas encore en prod
- `production` → modèle actif, servi par l'API

Fonctions :
- `promote_to_staging(run_id, metrics)` : promeut si accuracy ≥ seuil
- `promote_to_production()` : prend le staging et le met en prod
- `load_production_model()` : charge le modèle prod pour l'API
- `list_versions()` : liste toutes les versions avec leurs aliases

---

## Session 4 — FastAPI : exposer le modèle via une API

**Objectif :** permettre à n'importe quelle application d'obtenir une prédiction ML.

### `api/schemas.py`
**Les contrats de l'API** (via Pydantic).

Définit la forme exacte de chaque requête et réponse. FastAPI valide automatiquement les types et génère la documentation Swagger (`/docs`).

- `PredictRequest` : features envoyées par le client
- `Prediction` : résultat (direction, probabilité, confiance, version du modèle)
- `ABTestResponse` : résultat comparatif prod vs staging

### `api/predictor.py`
**Le moteur de prédiction.**

`ModelStore` : singleton qui charge les modèles **une seule fois** au démarrage (pas à chaque requête — trop lent).

La fonction `_predict_with()` :
1. Construit le vecteur de features dans le bon ordre
2. Appelle `model.predict()` → 0 ou 1
3. Appelle `model.predict_proba()` → probabilité de hausse
4. Calcule le niveau de confiance (high/medium/low)

### `api/main.py`
**L'application FastAPI avec ses 4 endpoints.**

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/health` | GET | Vérifie que tout est opérationnel |
| `/symbols` | GET | Liste les symboles dans Redis |
| `/predict` | POST | Prédiction depuis features manuelles |
| `/predict/{symbol}` | GET | Prédiction temps réel depuis Redis |
| `/ab-test/{symbol}` | GET | Comparaison prod vs staging |

Le **lifespan** FastAPI : fonction spéciale qui s'exécute au démarrage et à l'arrêt de l'API (charge les modèles MLflow en mémoire).

---

## Session 5 — Monitoring : surveillance du drift

**Objectif :** détecter automatiquement quand les données de production s'éloignent des données d'entraînement.

### Pourquoi surveiller le drift ?

Imagine que ton modèle ML a appris sur des données de marché "normal". Puis une crise économique arrive : les prix bougent différemment, la volatilité explose. Ton modèle ne sait pas que les règles ont changé → ses prédictions deviennent mauvaises.

Le **data drift** (dérive des données) détecte exactement ce phénomène statistiquement.

### Concepts clés

| Terme | Explication |
|-------|-------------|
| **Distribution** | La façon dont les valeurs se répartissent. Ex : "volatility_20 tourne d'habitude autour de 1.5 ± 0.3" |
| **Drift** | La distribution a changé. Ex : volatility_20 est maintenant à 4.5 en moyenne |
| **KS Test** | Test statistique qui compare deux distributions et calcule si elles viennent de la même "population" |
| **Drift share** | % de features qui ont drifté. 75% = 3 features sur 4 ont changé |
| **Reference data** | Données d'entraînement = la référence "normale" |
| **Current data** | Données récentes de production = ce qu'on observe maintenant |

### Niveaux d'alerte

```
OK       → 0% de drift       → Modèle stable, aucune action
WARNING  → drift < 50%       → Quelques features ont changé, surveiller
CRITICAL → drift ≥ 50%       → Majorité des features impactées, réentraîner
```

### Comment ça marche (Evidently)

Evidently est une bibliothèque Python spécialisée dans la surveillance de modèles ML. Elle calcule automatiquement des tests statistiques sur chaque feature.

```python
# On lui donne deux DataFrames : référence et courant
report = Report(metrics=[DatasetDriftMetric(), DataDriftTable()])
report.run(reference_data=df_reference, current_data=df_current)
# → Evidently calcule le test de Kolmogorov-Smirnov sur chaque feature
# → Génère un rapport HTML interactif
```

### Lancer le monitoring

```bash
# Simulation d'un drift (pour tester)
python monitoring/run.py --simulate-drift

# Analyser un symbole spécifique
python monitoring/run.py --symbol AAPL

# Les rapports sont sauvegardés dans monitoring/reports/
```

---

## Session 6 — LLM Layer : insights IA avec Claude

**Objectif :** utiliser un LLM (Large Language Model) pour analyser les alertes de drift et générer des recommandations en langage naturel.

### Qu'est-ce qu'un LLM ?

Un **LLM (Large Language Model)** est un modèle d'IA entraîné sur des milliards de textes. Il comprend et génère du langage naturel.

- **GPT-4** (OpenAI), **Claude** (Anthropic), **Gemini** (Google) sont des LLMs
- Dans DataPulse, on utilise **Claude Opus 4.6** d'Anthropic
- Au lieu de "apprendre" sur nos données, on lui donne nos données directement dans le prompt

### RAG — Retrieval-Augmented Generation

**RAG = Génération Augmentée par Récupération**

C'est une technique qui combine deux choses :
1. **Retrieval** (récupération) : on cherche les données pertinentes dans notre base
2. **Generation** (génération) : on les injecte dans le prompt pour que le LLM réponde avec ces données

```
Nos alertes JSONL          Prompt Claude
[alerte 1]  ──────────→  "Voici les 7 dernières alertes
[alerte 2]                 pour AAPL : [contenu]
[alerte 3]                 Analyse-les et donne des recommandations"
   ...
```

**Sans RAG :** Claude ne connaît pas nos données (il a une date de coupure de connaissance)
**Avec RAG :** On lui donne nos données en temps réel → il peut répondre dessus

### Prompt Caching

Le **prompt caching** est une optimisation économique :

- Le system prompt (instructions générales) est **stable** → Anthropic le met en cache 5 minutes
- Les appels répétés ne re-envoient pas ce texte → **~90% d'économie de tokens** sur le system prompt
- Seul le contenu variable (les alertes du jour) est envoyé à chaque fois

```python
system=[{
    "type": "text",
    "text": SYSTEM_PROMPT,  # ~500 tokens, stable
    "cache_control": {"type": "ephemeral"}  # mis en cache 5 min
}]
```

### Adaptive Thinking

Claude Opus 4.6 supporte le **thinking adaptatif** :

- Claude "réfléchit" silencieusement avant de répondre (comme un brouillon interne)
- Il décide lui-même combien réfléchir selon la complexité de la question
- Résultat : réponses plus précises et mieux raisonnées

```python
thinking={"type": "adaptive"}  # Claude décide lui-même de la profondeur
```

### Streaming

Au lieu d'attendre que Claude finisse sa réponse complète (qui peut prendre 10-30 secondes), le **streaming** envoie les tokens au fur et à mesure :

```
Sans streaming : ⏳⏳⏳⏳⏳⏳⏳⏳ → Réponse complète en 15s
Avec streaming : "L'analyse" → " montre" → " un drift" → " critique"... (token par token)
```

C'est comme lire une réponse qui s'écrit devant toi en temps réel.

### Architecture du module LLM

```
llm/
├── config.py      → modèle Claude, clé API, paramètres
├── rag.py         → charge les alertes JSONL, formate le contexte
├── analyzer.py    → appelle Claude API avec streaming + caching
└── insights.py    → CLI pour lancer l'analyse
```

### Utilisation

**Prérequis : avoir une clé API Anthropic**
```bash
export ANTHROPIC_API_KEY='sk-ant-api03-...'
```

**CLI (terminal) :**
```bash
# Analyse toutes les actions (streaming)
python llm/insights.py

# Analyse un symbole spécifique
python llm/insights.py --symbol AAPL

# Sans streaming (attend la réponse complète)
python llm/insights.py --symbol AAPL --no-stream
```

**Via l'API FastAPI :**
```bash
# Lancer l'API
uvicorn api.main:app --reload

# Appeler l'endpoint insights
curl http://localhost:8000/insights/AAPL
```

**Exemple de réponse Claude :**
```
Résumé de la situation :
• AAPL a connu 3 événements de drift critique au cours des dernières analyses
• 100% des features (sma_5, sma_20, volatility_20, price_change_pct) ont drifté
• Cela indique un changement de régime de marché significatif

Features les plus à risque :
• volatility_20 : fortement impactée → le marché est plus volatile qu'à l'entraînement
• price_change_pct : distribution très différente → les variations journalières ont changé

Évaluation du risque ML :
• ÉLEVÉ — les prédictions UP/DOWN ne sont plus fiables dans ce contexte
• Le modèle a été entraîné sur un régime de marché différent

Recommandations :
• Réentraîner immédiatement le modèle avec des données récentes (post-changement)
• Augmenter la fréquence de surveillance à 1h au lieu de 24h
• Envisager un modèle adaptatif qui se réentraîne automatiquement
```

### Nouveaux endpoints API

| Endpoint | Description |
|----------|-------------|
| `GET /insights/AAPL` | Analyse IA pour un symbole spécifique |
| `GET /insights` | Analyse IA globale (tous les symboles) |

---

## Installation et lancement

### Prérequis
- Python 3.12+
- Docker Desktop

### 1. Setup initial
```bash
cd ~/Desktop/datapulse
cp .env.example .env
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Démarrer l'infrastructure
```bash
docker compose up -d
```
Lance : Kafka, Zookeeper, Redis, Kafka UI (port 8081)

### 3. Lancer le pipeline de données (3 terminaux)
```bash
# Terminal 1 — ingestion brute
PYTHONPATH=. python ingestion/producer.py

# Terminal 2 — consumer (sauvegarde JSONL)
PYTHONPATH=. python ingestion/consumer.py

# Terminal 3 — feature pipeline (calcule les indicateurs)
PYTHONPATH=. python feature_store/pipeline.py
```

### 4. Entraîner un modèle
```bash
PYTHONPATH=. python ml/train.py
```

### 5. Promouvoir le modèle en production
```bash
PYTHONPATH=. python -c "
from ml.train import train
from ml.registry import promote_to_staging, promote_to_production
run_id, metrics = train()
promote_to_staging(run_id, metrics)
promote_to_production()
"
```

### 6. Lancer l'API
```bash
PYTHONPATH=. uvicorn api.main:app --reload --port 8000
```

### 7. Tester l'API
```bash
# Prédiction manuelle
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"symbol":"AAPL","sma_5":189.5,"sma_20":187.2,"volatility_20":1.42,"price_change_pct":0.31}'
```

Documentation interactive : `http://localhost:8000/docs`

### 8. Voir MLflow
```bash
PYTHONPATH=. mlflow ui --backend-store-uri mlruns --port 5001
```
Puis ouvre `http://localhost:5001`

---

## Structure des fichiers

```
datapulse/
│
├── ingestion/               # Session 1 — Kafka
│   ├── config.py            # Variables d'environnement
│   ├── producer.py          # Génère les prix simulés → Kafka
│   └── consumer.py          # Lit Kafka → sauvegarde JSONL
│
├── feature_store/           # Session 2 — Feature Store
│   ├── config.py            # Config Redis + DuckDB
│   ├── features.py          # Calcul SMA, volatilité, etc.
│   ├── online_store.py      # Redis — features temps réel
│   ├── offline_store.py     # DuckDB — features historiques
│   └── pipeline.py          # Kafka → features → Redis + DuckDB
│
├── ml/                      # Session 3 — ML Pipeline
│   ├── config.py            # Config MLflow + hyperparamètres
│   ├── data_prep.py         # Chargement + préparation des données
│   ├── train.py             # Entraînement + logging MLflow
│   └── registry.py          # Promotion staging/production
│
├── api/                     # Session 4 — API FastAPI
│   ├── schemas.py           # Structures de requêtes/réponses (+ InsightResponse)
│   ├── predictor.py         # Chargement modèle + prédiction
│   └── main.py              # Endpoints HTTP (+ /insights)
│
├── monitoring/              # Session 5 — Monitoring drift
│   ├── config.py            # Config Evidently + seuils
│   ├── drift_detector.py    # Détection drift (Evidently)
│   ├── alerts.py            # Système d'alertes JSONL
│   ├── reporter.py          # Rapports HTML + JSON
│   ├── run.py               # CLI monitoring
│   └── reports/             # Rapports générés (HTML + JSON + alerts.jsonl)
│
├── llm/                     # Session 6 — LLM Layer (Claude API)
│   ├── config.py            # Config modèle + clé API
│   ├── rag.py               # Récupération alertes (RAG)
│   ├── analyzer.py          # Appel Claude avec streaming + caching
│   └── insights.py          # CLI insights IA
│
├── data/
│   └── raw/                 # Ticks bruts JSONL (généré automatiquement)
│       └── AAPL/2026-04-19.jsonl
│
├── mlruns/                  # Expériences MLflow (généré automatiquement)
├── docker-compose.yml       # Kafka + Redis + Kafka UI
├── requirements.txt         # Dépendances Python
└── .env.example             # Variables d'environnement à copier
```
