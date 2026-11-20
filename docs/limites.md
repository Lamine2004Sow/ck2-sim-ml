# Limites connues et contrôles qualité

Ce document recense les défauts trouvés en contrôlant les tables de `run_001` (94 sauvegardes, 1230 → 1330),
leur cause quand elle est établie, leur impact et la correction prévue. Ils ne sont **pas encore corrigés** :
le but est de savoir précisément ce que valent les données avant de s'en servir.

Chaque point indique si la cause est **vérifiée** (lue dans le code ou dans la sauvegarde) ou **supposée** (à confirmer).

## Synthèse

| # | Table | Problème | Lignes touchées | Gravité | Cause |
|---|---|---|---|---|---|
| 1 | `title_history` | `holder` contient une liste Python au lieu d'un identifiant | 114 / 68 275 (0,17 %) | haute | vérifiée |
| 2 | `battles` | effectif initial à 0 alors que les pertes sont positives | 1 186 / 4 747 (25 %) | haute | supposée |
| 3 | `edges` | liens d'un personnage vers lui-même | 5 003 / 424 899 (1,2 %) | moyenne | vérifiée en partie |
| 4 | `wars` | `n_battles` différent du nombre de lignes de `battles` | 1 / 2 639 | faible | supposée |
| 5 | toutes | instantanés irréguliers au début de la partie | 3 premiers instantanés | moyenne | vérifiée |
| 6 | `wars` | guerres vues dans un seul instantané, ou jamais vues | 1 152 / 2 639 (44 %) vues une fois | moyenne | vérifiée |
| 7 | `provinces` | `county` ou `realm` vide | 15 et 19 provinces par instantané | faible | vérifiée en partie |
| 8 | `characters` | état final seulement, pas d'historique des attributs | toutes | conception | vérifiée |

---

## 1. `title_history` : titulaires multiples à la même date

**Constat.** 114 lignes ont un `holder` illisible, par exemple
`[{'who': '2723321', 'type': 'inheritance'}, {'who': '2721871', 'type': 'grant'}]`, et un `change_type` vide.

**Cause (vérifiée).** Quand un titre change deux fois de main le même jour (un héritage suivi d'une concession), la sauvegarde écrit
deux clés `holder=` dans le même bloc de date. Le parseur les range dans une `Multi` (liste), mais `extract.py` ne prévoit
qu'un `dict` ou une valeur simple, et écrit donc la liste telle quelle.

**Impact.** Ces règnes très courts sont perdus, et la colonne `holder` n'est plus un entier partout : un chargement typé échoue.

**Correction prévue.** Parcourir `as_list(e["holder"])` et écrire une ligne par titulaire, dans l'ordre. Ajouter un test sur un bloc à deux `holder=`.

## 2. `battles` : effectifs initiaux à zéro

**Constat.** Dans 1 186 batailles, un camp a des pertes positives mais un effectif initial à 0 (le défenseur dans 1 183 cas).

**Cause (supposée).** La sauvegarde écrit les pertes par type de troupe, en général sous la forme `li={0.000 792.489}`,
lue comme `{pertes effectif_initial}`. Elle utilise aussi une forme à une seule valeur (`li=1.000`, 117 fois dans la sauvegarde de 1330) :
l'effectif vaut alors 0 par défaut. Cette forme n'explique pas à elle seule les 1 186 cas ; il faut aussi vérifier l'ordre des deux valeurs
et l'endroit où la sauvegarde stocke l'effectif du défenseur.

**Impact.** `defender_troops` n'est pas fiable, ni tout ratio pertes / effectif.

**Correction prévue.** Comparer 10 batailles de la sauvegarde avec la table, établir la règle, puis écrire l'effectif vide (et non 0) quand il est inconnu.

## 3. `edges` : boucles

**Constat.** 5 003 liens ont `src == dst` : 4 990 `employer` et 13 `killer`.

**Cause (vérifiée en partie).** Un souverain est noté comme son propre employeur (`emp`) : 4 951 des 4 990 boucles `employer` concernent un personnage qui détient au moins un titre. Pour `killer`, il s'agit probablement de suicides (supposé).

**Impact.** Fausse les degrés dans un graphe de cour ou de vassalité.

**Correction prévue.** Garder ces lignes mais ajouter une colonne `is_self` ; documenter le sens de chaque cas.

## 4. `wars` : un compte de batailles incohérent

**Constat.** Une guerre (`run_001:1318.9.7:2770472:2750255`) a `n_battles = 7` alors que `battles` contient 9 lignes pour elle.

**Cause (supposée).** `n_battles` vient de la dernière observation de la guerre, alors que `battles` cumule toutes les sauvegardes
(clé `war_id`, date, lieu). Des batailles qui disparaissent de l'historique entre deux sauvegardes expliqueraient l'écart.

**Correction prévue.** Calculer `n_battles` à partir de la table `battles` après dédoublonnage.

## 5. Instantanés irréguliers

**Constat.** Les trois premiers instantanés sont 1230, 1235 et 1239, puis la collecte est annuelle jusqu'en 1330.

**Cause (vérifiée).** La collecte a commencé en cours de partie. Les données ne disent pas cette irrégularité : elle se voit seulement dans `snapshot_date`.

**Impact.** Les colonnes d'évolution à 10 ans ne sont disponibles qu'à partir d'environ 1240 (`has_past_10y` faux sur 2 480 lignes de `realms`).
Tout calcul par instantané (moyennes annuelles, durées) doit tenir compte du pas réel.

**Correction prévue.** Écrire un fichier `snapshots.csv` (date, fichier source, taille, durée d'extraction) et un contrôle qui signale les trous.

## 6. Guerres courtes peu ou pas observées

**Constat.** 1 152 guerres sur 2 639 ne sont vues que dans un seul instantané. Une guerre qui commence et finit entre deux sauvegardes
n'apparaît jamais dans `active_war`.

**Cause (vérifiée).** C'est la limite d'un échantillonnage annuel : `first_seen` et `last_seen` encadrent la guerre à un an près.
La section `previous_war` de la sauvegarde ne contient qu'une liste d'identifiants numériques, sans date ni camp : elle ne permet pas de reconstituer les guerres terminées.

**Correction prévue.** Augmenter la fréquence de collecte (sauvegarde mensuelle) sur une partie de test pour mesurer combien de guerres l'échantillonnage annuel manque, puis choisir le pas.

## 7. Provinces sans comté ou sans royaume

**Constat.** À chaque instantané, 15 provinces n'ont pas de comté (déserts : Kyzylkoum, Rub al-Khali, Sahara…) et 19 ont un comté
mais pas de royaume (Ääninen, Gostynin, Istakhr…).

**Cause.** Vérifiée pour les déserts : provinces infranchissables sans fichier d'histoire. Supposée pour les 19 autres :
comtés sans titulaire au moment de la sauvegarde.

**Correction prévue.** Ajouter une colonne `province_type` (désert, sans titulaire) plutôt que de laisser des vides ambigus.

## 8. Choix de conception : un seul état par personnage

`characters` est lue dans la dernière sauvegarde : prestige, richesse, traits et attributs sont ceux de 1330 (ou du décès).
Rien ne dit comment ils ont évolué. `--characters all` existe, mais multiplie la table par 94.
Une table d'historique ne gardant que les **changements** (format SCD de type 2 : valeur, date de début, date de fin) serait plus compacte.

---

## Autres constats, normaux

- `dynasty` vide pour 69 056 personnages : personnes sans dynastie (roturiers), cas prévu par le jeu.
- `change_type` vide pour 28 062 lignes de `title_history` : titulaires historiques de départ, écrits `holder=…` sans mode d'acquisition.
- `culture` vide pour 23 personnages sur 165 881, et 0 pour `religion`, `birth` et `name`.
- Contrôles passés : aucun identifiant de personnage en double, aucun lien en double, aucun lien vers un personnage absent, mariages symétriques,
  aucune bataille rattachée à une guerre inconnue, aucun doublon (`snapshot_date`, `realm`).

## Évolutions prévues de la chaîne

1. **Tests de qualité automatiques** à chaque extraction : unicité des clés, types, intégrité référentielle, bornes (pertes ≤ effectif), avec un rapport.
2. **Stockage typé** (Parquet) : plus compact que le CSV et qui conserve les types, ce qui aurait fait échouer le point 1 dès l'écriture.
3. **Plusieurs parties** : un `run_id` par partie, et un fichier de métadonnées par partie (version du jeu, règles, années couvertes).
4. **Intégration continue** : tests à chaque push.
