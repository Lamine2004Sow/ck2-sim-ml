# Problématique de recherche — L'IA historien face à une histoire alternative

> **Question centrale** : quand les documents qu'on fournit à un LLM contredisent
> ce qu'il a appris pendant son entraînement, à qui fait-il confiance ?
> Et de quoi dépend ce choix ?

---

## 1. Contexte

Les systèmes de **RAG** (*Retrieval-Augmented Generation*) et les **agents à
outils** sont censés ancrer les réponses d'un LLM dans des sources fournies.
Mais un LLM possède aussi une **connaissance paramétrique**, apprise pendant
son entraînement. Quand les deux se contredisent, on parle de
**conflit de connaissances** (*knowledge conflict*). Le modèle peut alors :

- suivre le contexte fourni (*context adherence*) ;
- le remplacer par ce qu'il « sait » (*parametric override*), ce qui est une
  hallucination déguisée ;
- mélanger les deux, ou s'abstenir.

C'est un problème concret : documentation interne qui contredit le web, données
d'entreprise mises à jour, scénarios fictifs ou contrefactuels…

### Le verrou méthodologique
Pour étudier ces conflits, la littérature **fabrique** généralement des
contradictions : on remplace une entité par une autre dans un passage, par
exemple « La capitale de la France est Lyon ». Ces substitutions sont
artificielles, isolées et souvent incohérentes avec le reste du texte. Le
modèle peut donc les détecter comme fausses.

## 2. L'idée : Crusader Kings II comme générateur d'histoires alternatives

En mode observation, CK2 simule environ 20 000 personnages pilotés par l'IA, de
1066 à 1453. Chaque partie part de **l'histoire réelle**, puis **diverge
progressivement** et de manière **cohérente** : mariages, successions, guerres
et effondrements s'enchaînent logiquement.

Ce que ça apporte :

| Propriété | Pourquoi c'est précieux |
|---|---|
| **Conflits naturels** | Les contradictions ne sont pas fabriquées : elles émergent de la simulation et restent cohérentes entre elles. |
| **Divergence graduelle** | En 1066, simulation et réalité coïncident ; l'écart grandit avec le temps. On peut donc mesurer l'effet de l'intensité du conflit. |
| **Vérité terrain exacte** | Chaque réponse est vérifiable dans les données extraites (titres, règnes, guerres, généalogie). |
| **Reproductible et multipliable** | Plusieurs parties indépendantes donnent plusieurs histoires alternatives, ce qui permet de mesurer la variance. |
| **Entités réelles** | Les mêmes noms (France, Byzance, Saint-Empire) sont fortement ancrés dans la mémoire des LLM : c'est là que le conflit est le plus fort. |

**Aucune base d'histoire réelle n'est nécessaire.** On mesure directement ce
que le modèle croit : on lui pose la question *sans contexte*
(*closed-book*). Une question est en conflit si sa réponse sans contexte
diffère de la vérité de la simulation.

## 3. Questions de recherche

- **RQ1 — Ampleur.** À quelle fréquence un LLM remplace-t-il l'histoire
  simulée fournie par sa connaissance paramétrique ?
- **RQ2 — Intensité du conflit.** Ce taux d'override augmente-t-il avec :
  - la **notoriété** de l'entité (royaume de France contre comté obscur) ;
  - la **distance temporelle** depuis 1066, c'est-à-dire l'écart entre
    simulation et réalité ;
  - la **confiance** du modèle dans sa réponse sans contexte ?
- **RQ3 — Architecture.** L'override diffère-t-il entre un RAG vectoriel
  (passages narratifs) et un agent qui interroge des données structurées
  (SQL, graphe) ?
- **RQ4 — Atténuation.** Quelles interventions le réduisent : consigne
  explicite (« ce monde est fictif »), obligation de citer ses sources,
  vérification a posteriori ?
- **RQ5 — Modèles.** Comment ces effets varient-ils selon la famille et la
  taille du modèle (DeepSeek, Qwen local) ?

### Hypothèses
- **H1** : l'override est plus fréquent pour les entités célèbres que pour les
  entités obscures.
- **H2** : l'override diminue quand la divergence est grande (le contexte paraît
  « clairement autre ») mais il est maximal pour les petites divergences
  plausibles.
- **H3** : l'agent avec outils (réponses tirées d'un résultat SQL exact) résiste
  mieux que le RAG vectoriel (passages en langage naturel).
- **H4** : une consigne de fictionnalisation réduit l'override, au prix d'un
  peu plus d'abstentions.

## 4. Méthode

### 4.1 Données
- **N parties** indépendantes de CK2 en observation (objectif : 3 à 5), même
  date de départ (1066), une copie par an.
- Extraction en tables (`characters`, `titles`, `title_history`, `realms`,
  `wars`, `battles`, `edges`) via `ck2sim.extract`.

### 4.2 Jeu de questions
Généré automatiquement depuis les tables, avec la réponse exacte :

| Catégorie | Exemple |
|---|---|
| Factuelle | Qui détenait `k_france` le 1er janvier 1240 ? |
| Temporelle | Quand X a-t-il commencé à régner ? |
| Agrégation | Combien de guerres religieuses ont eu lieu entre 1240 et 1260 ? |
| Multi-étapes | Qui était le père du roi d'Angleterre en 1250 ? |
| Comparaison | Quel royaume a le plus grandi entre 1230 et 1260 ? |
| Négative / piège | Louis IX était-il roi de France en 1240 ? (non, dans cette partie) |

Chaque question est annotée : notoriété de l'entité, distance à 1066, statut
du conflit (réponse sans contexte = vérité de la simulation ou non), partie.

### 4.3 Conditions expérimentales
1. **Closed-book** : aucun contexte. Mesure la croyance paramétrique.
2. **RAG vectoriel** : chroniques et biographies générées depuis les données,
   indexées avec des embeddings.
3. **Agent à outils** : SQL, arbre généalogique, chaîne de vassalité, guerres.
4. Variantes de consigne : neutre, « monde fictif », « cite tes sources ».

### 4.4 Métriques
- **Exactitude** par rapport à la vérité de la simulation.
- **Taux d'override** : la réponse égale la réponse sans contexte, mais diffère
  de la vérité de la simulation.
- **Fidélité des citations** : les identifiants cités soutiennent-ils
  réellement la réponse ?
- **Taux d'abstention** et **calibration**.
- **Coût** (tokens, €) et **latence** par question.

### 4.5 Évaluation rigoureuse
- **Correction automatique** quand c'est possible (identifiants, dates,
  nombres), sinon un **LLM juge**.
- **Validation humaine du juge** : environ 150 réponses annotées à la main,
  avec l'accord mesuré (kappa de Cohen).
- **Intervalles de confiance par bootstrap** et **tests appariés** (McNemar)
  entre conditions.
- **Séparation par partie** : les consignes et réglages sont mis au point sur
  une partie, puis évalués sur les autres.

## 5. Limites et menaces à la validité

- **Contamination** : des récits de parties de CK2 existent en ligne, mais pas
  *cette* partie. On contrôle en vérifiant que le taux de réussite sans
  contexte reste bas sur les faits post-divergence.
- **Noms et localisation** : les noms du jeu (en français ici) diffèrent
  parfois des noms historiques. Il faut normaliser les réponses (identifiants
  de titres plus noms).
- **Un seul moteur de simulation** : les conclusions portent sur l'histoire
  médiévale alternative ; leur généralisation à d'autres domaines reste une
  hypothèse.
- **Modèle local sur processeur** : la taille des modèles testables en local
  est limitée (pas de GPU).

## 6. Livrables

1. **Dataset** publié : questions, réponses et métadonnées de conflit.
2. **Banc d'évaluation** reproductible (`make eval`), avec coûts mesurés.
3. **Agent historien** : démo interactive avec réponses sourcées.
4. **Rapport** au format mini-article : résultats RQ1 à RQ5, figures, limites.

## 7. Positionnement CV

- **AI engineering** : RAG, agent à outils, couche multi-modèles (DeepSeek,
  Ollama), évaluation automatisée, suivi des coûts.
- **Recherche** : question originale (conflits naturels, divergence graduelle),
  protocole contrôlé, validation humaine, statistiques.
- **ML engineering** (volet 2 du projet) : pipeline de données à partir d'une
  simulation, modèles de survie, de graphe et de prévision.

## Références de départ (à vérifier et compléter)

- Longpre et al., 2021 — *Entity-Based Knowledge Conflicts in Question Answering*.
- Chen et al., 2022 — *Rich Knowledge Sources Bring Complex Knowledge Conflicts*.
- Xie et al., 2023 — *Adaptive Chameleon or Stubborn Sloth: Revealing the
  Behavior of Large Language Models in Knowledge Conflicts*.
- Xu et al., 2024 — *Knowledge Conflicts for LLMs: A Survey*.
