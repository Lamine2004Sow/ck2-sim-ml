# Outils du projet — rôle et utilité

Légende du statut : ✅ déjà en place · 📦 à installer · 🔜 phase ultérieure
· ⭕ optionnel.

Principe de choix : **le plus simple qui suffit**. Chaque outil doit répondre à
un besoin précis du projet. On n'en ajoute pas pour remplir le CV : un
recruteur repère vite un empilement d'outils sans justification.

---

## 1. Simulation et collecte des données

| Outil | Statut | Utilité dans le projet |
|---|---|---|
| **Crusader Kings II** (v3.3.3, mode `-debug_mod` + `observe`) | ✅ | Le simulateur : génère des histoires alternatives cohérentes à partir de 1066. |
| **Sauvegarde annuelle non compressée** (`settings.txt` : `autosave="YEARLY"`, `compress_autosaves=no`) | ✅ | Produit un instantané lisible de tout le monde simulé chaque année. |
| **`scripts/collect_snapshots.sh`** (bash + gzip) | ✅ | Copie et compresse chaque sauvegarde (75 → 14 Mo) et s'arrête à l'année voulue. |

## 2. Données : extraction, stockage, requêtes

| Outil | Statut | Utilité |
|---|---|---|
| **Python 3.12** | ✅ | Langage de tout le projet. |
| **`ck2sim` (parseur maison, bibliothèque standard seule)** | ✅ | Transforme les sauvegardes en 8 tables CSV (personnages, titres, règnes, royaumes, guerres, batailles, provinces, liens). |
| **DuckDB** | 📦 | Base SQL dans un simple fichier, sans serveur. Charge les CSV et sert à la fois à l'analyse et aux **outils SQL de l'agent historien**. Plus rapide et plus simple que PostgreSQL ici. |
| **Parquet** (via DuckDB ou pyarrow) | 📦 | Format de stockage compressé et typé, 5 à 10 fois plus petit que le CSV. Indispensable quand il y aura plusieurs parties et des centaines de copies. |
| **pandas** | 📦 | Manipulation des tables dans les notebooks et pour les statistiques. |
| **pandera** ⭕ ou tests maison | 📦 | **Validation automatique des données** : schémas, valeurs manquantes, cohérence. Par exemple « `pregnant` ⇒ femme », que j'ai vérifié à la main. |

## 3. Volet ML

| Outil | Statut | Utilité |
|---|---|---|
| **scikit-learn** | 📦 | Clustering (profils de royaumes et de guerres), classification, prétraitement. |
| **mlxtend** | 📦 | Règles d'association (**Apriori**) sur les traits des personnages. |
| **lifelines** | 📦 | **Analyse de survie** : durée des règnes, des dynasties et des royaumes (Kaplan-Meier, modèle de Cox). |
| **NetworkX** | 📦 | Graphes de parenté et de vassalité : centralité, communautés. Sert aussi à l'outil `family_tree` de l'agent. |
| **PyTorch Geometric** ⭕ | 🔜 | Réseaux de neurones sur graphes, si on va jusqu'à prédire des liens (assassinats, défections). Lourd sur processeur seul : à n'ajouter que si NetworkX ne suffit plus. |
| **LightGBM** ⭕ | 🔜 | Prévision tabulaire (évolution des royaumes), souvent meilleure qu'un réseau de neurones sur ce type de données. |

## 4. Volet IA : l'historien

| Outil | Statut | Utilité |
|---|---|---|
| **API DeepSeek** (format compatible OpenAI) | ✅ clé dispo | **LLM principal évalué** : l'historien qui répond aux questions et appelle les outils. Clé dans la variable `DEEPSEEK_API_KEY`, jamais dans le code. |
| **Ollama + `qwen35-local`** | ✅ | **Deuxième famille de modèles**, locale et gratuite. Permet de comparer les familles (RQ5). Lent sans GPU : à faire tourner la nuit. |
| **SDK `openai` (Python)** | 📦 | Client unique pour DeepSeek et Ollama, qui exposent tous les deux ce format. C'est la base de la couche commune : changer de modèle se fait en une ligne de configuration. |
| **Appels d'outils (*function calling*)** | — | Mécanisme qui permet à l'agent d'appeler `query_sql`, `family_tree`, `war_details`… C'est le cœur de la condition « agent » (RQ3). |
| **sentence-transformers** (modèle d'embeddings local) | 📦 | Transforme les chroniques générées en vecteurs pour la **condition RAG vectoriel**. En local, donc gratuit et reproductible. |
| **LanceDB** ou **FAISS** | 📦 | Index de recherche vectorielle. LanceDB tient dans un fichier, comme DuckDB, et ne demande aucun serveur. |
| **Jinja2** | 📦 | Modèles de texte pour générer les questions et les chroniques à partir des tables. Ils sont **versionnés** pour que l'expérience soit reproductible. |

> Pas de LangChain ni de LlamaIndex : la boucle de l'agent fait environ
> 50 lignes. L'écrire soi-même montre qu'on comprend le mécanisme, et facilite
> le débogage et la mesure fine des coûts.

## 5. Évaluation (le point clé pour la recherche)

| Outil | Statut | Utilité |
|---|---|---|
| **Générateur de questions-réponses maison** | 🔜 | Produit des centaines de questions avec leur **réponse exacte**, annotées (notoriété, distance à 1066, conflit ou non). |
| **Correcteur automatique** | 🔜 | Compare identifiants, dates et nombres sans LLM, donc gratuit et sans biais. |
| **LLM juge** (DeepSeek) | 🔜 | Note les réponses en texte libre qu'on ne peut pas vérifier automatiquement. |
| **Interface d'annotation humaine** (simple CSV ou petit outil Streamlit) | 🔜 | Tu annotes environ 150 réponses : ça **valide le juge**. |
| **scipy / statsmodels** | 📦 | Kappa de Cohen (accord humain–juge), tests de McNemar (comparaison de conditions), régressions (effet de la notoriété et du temps). |
| **Bootstrap** (numpy) | 📦 | Intervalles de confiance sur chaque métrique. |
| **Journal des appels** (JSONL) | 🔜 | Chaque appel enregistré : question, consigne, modèle, réponse, tokens, coût, latence. Permet de rejouer et d'auditer les résultats. |
| **Cache des réponses** (disque) | 🔜 | Ne jamais repayer deux fois la même question. Réduit le coût et rend les résultats rejouables. |

## 6. Suivi des expériences et reproductibilité

| Outil | Statut | Utilité |
|---|---|---|
| **MLflow** (en local) | 📦 | Enregistre chaque expérience (paramètres, métriques, fichiers produits) et compare les conditions. Standard reconnu en ML et IA. |
| **Fichiers de configuration YAML** | 🔜 | Une expérience = un fichier : modèle, consigne, condition, graine. On relance à l'identique. |
| **Graines aléatoires fixées** | 🔜 | Tirage des questions et séparations reproductibles. |
| **DVC** ⭕ | 🔜 | Versionnage des datasets. Utile seulement si tu publies plusieurs versions du dataset ; sinon, un fichier de sommes de contrôle suffit. |

## 7. Ingénierie logicielle

| Outil | Statut | Utilité |
|---|---|---|
| **git** | ✅ | Historique du projet. |
| **GitHub + `gh`** | ✅ (connexion à faire) | Dépôt public, vitrine du CV. |
| **uv** (ou pip + venv) | 📦 | Environnement Python isolé et dépendances figées (`uv.lock`) pour une installation reproductible. |
| **pytest** | 📦 | Tests : parseur, extracteur, outils de l'agent, correcteur. 6 tests existent déjà (avec unittest). |
| **ruff** | 📦 | Formatage et vérification du style, en une seule commande. |
| **pre-commit** | 📦 | Lance ruff et les tests avant chaque commit. |
| **GitHub Actions** | 🔜 | Intégration continue : tests à chaque push, avec un badge sur le README. |
| **Makefile** | 🔜 | Commandes simples : `make extract`, `make eval`, `make report`. |
| **python-dotenv** | 📦 | Charge `DEEPSEEK_API_KEY` depuis un fichier `.env`, exclu de git. |

## 8. Démonstration et restitution

| Outil | Statut | Utilité |
|---|---|---|
| **Streamlit** | 🔜 | Démo de l'historien : on pose une question, on voit la réponse, les outils appelés et les sources. Idéal à montrer en entretien. |
| **FastAPI** ⭕ | 🔜 | API de l'historien, si tu veux montrer le déploiement d'un service. |
| **Docker** ⭕ | 🔜 | Lancer la démo n'importe où en une commande. |
| **matplotlib / seaborn** | 📦 | Figures du rapport : taux d'override selon la notoriété ou le temps, comparaison des conditions. |
| **Jupyter** | 📦 | Exploration et analyse. Le code définitif va dans `ck2sim/`, pas dans les notebooks. |
| **Markdown ou LaTeX** | — | Rapport au format mini-article. Ton CV est déjà en LaTeX, tu as donc la chaîne de compilation. |
| **Hugging Face Datasets** ⭕ | 🔜 | Publier le dataset de questions-réponses : visible, citable, valorisant. Conditions d'utilisation de Paradox à vérifier avant. |

---

## Ordre d'installation conseillé

1. **Maintenant** : `uv`, `duckdb`, `pandas`, `pyarrow`, `pytest`, `ruff`.
   C'est le socle données et qualité.
2. **Volet IA** : `openai`, `python-dotenv`, `jinja2`, puis
   `sentence-transformers` et `lancedb` pour la condition RAG.
3. **Évaluation** : `scipy`, `statsmodels`, `mlflow`.
4. **Volet ML** : `scikit-learn`, `mlxtend`, `lifelines`, `networkx`.
5. **Restitution** : `streamlit`, `matplotlib`, puis GitHub Actions.

## Contraintes matérielles connues

- **Pas de GPU NVIDIA**, 15 Go de RAM, 8 cœurs. Les embeddings et un petit
  modèle local passent sur processeur. Il faut éviter l'entraînement de gros
  réseaux de neurones et les modèles locaux de plus de 7 à 8 milliards de
  paramètres.
- **Disque** : environ 3 Go par partie collectée chaque année jusqu'en 1453
  (environ 1,3 Go jusqu'en 1330).
