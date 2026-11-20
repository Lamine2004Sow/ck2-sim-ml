# Formats : des sauvegardes CK2 aux tables CSV

Ce document décrit le format d'entrée (une sauvegarde Crusader Kings II) et le format de sortie (8 tables CSV),
avec les règles de transformation entre les deux. Les exemples et les volumes viennent de la partie `run_001`
(94 sauvegardes annuelles, de 1230 à 1330).

```
autosave.ck2 (texte, ~75 Mo, ~4,7 M lignes)
   │  scripts/collect_snapshots.sh : copie à chaque nouvelle année de jeu, gzip (75 → 14 Mo)
   ▼
save_1230.1.1.ck2.gz … save_1330.1.1.ck2.gz        (94 instantanés)
   │  ck2sim.parser : lit seulement 5 sections de premier niveau
   │  ck2sim.gamedata : traits, dynasties, provinces → comtés (fichiers du jeu)
   ▼
data/processed/run_001/*.csv                        (8 tables, 258 Mo)
```

---

## 1. Le format des sauvegardes

### 1.1 Syntaxe (format texte « Clausewitz » de Paradox)

Une sauvegarde non compressée est un fichier texte en **windows-1252**, qui commence par l'en-tête `CK2txt`.
Toute la structure repose sur trois constructions :

| Syntaxe | Exemple | Représentation après parsing (`ck2sim/parser.py`) |
|---|---|---|
| `clé=valeur` | `culture="german"`, `fat=2704242` | entrée de `dict`, valeur toujours en `str` |
| `clé={ … }` avec des `=` | `dynasties={ 1000101154={ … } }` | `dict` imbriqué |
| `clé={ … }` sans `=` | `att={4 6 1 6 7}` | `list` |
| clé répétée dans un bloc | plusieurs `law="…"` | `Multi` (une sous-classe de `list`) |

Pièges du format, gérés par le parseur :
- **Pas de type** : `yes`/`no`, nombres, dates (`1230.1.1`) et identifiants sont tous du texte. La conversion se fait à l'extraction.
- **Clés répétées** : une même clé peut apparaître une ou plusieurs fois (`law=`, `active_war=`). `as_list()` ramène les deux cas à une liste.
- **Clés numériques** : les identifiants (personnages, dynasties) et les dates (`769.1.1=`) servent de clés de bloc.
- **Encodage** : décodé en `latin-1`, qui ne peut jamais échouer sur un octet, contrairement à `utf-8`.
- **Commentaires** `#…` ignorés.

### 1.2 Sections utilisées

Une sauvegarde contient une soixantaine de sections de premier niveau. L'extraction n'en analyse que 5 :
le parseur repère leurs bornes, puis ne tokenise que ces tranches, ce qui ramène le traitement à ~13 s par sauvegarde.

| Section | Contenu | Début dans `save_1230.1.1.ck2` | Tables alimentées |
|---|---|---|---|
| `dynasties` | dynasties créées pendant la partie (nom, culture, religion) | ligne 1 361 | `characters` |
| `character` | tous les personnages, vivants et morts | ligne 174 328 | `characters`, `edges`, `realms` |
| `provinces` | les 1 755 provinces (nom, culture, religion, baronnies) | ligne 3 601 044 | `provinces`, `realms` |
| `title` | tous les titres (baronnie → empire), lois, historique des titulaires | ligne 3 860 855 | `titles`, `title_history`, `realms` |
| `active_war` | une section par guerre en cours (59 dans ce fichier), batailles comprises | ligne 4 622 327 | `wars`, `battles`, `realms` |

Sections ignorées, entre autres : `delayed_event` (2 405 blocs), `relation`, `bloodline`, `active_plot`, `active_faction`, `disease_outbreak`, `artifacts`.

### 1.3 Extraits réels

Un personnage (section `character`) : les clés sont abrégées.

```
2707334=
{
    bn="Abdul-Hasan"          # nom (birth name)
    b_d="1209.11.24"          # date de naissance
    fat=2704242               # père          → edges (father)
    mot=2689311               # mère          → edges (mother)
    spouse=2706106            # conjoint      → edges (spouse)
    att={4 6 1 6 7}           # diplomatie, martial, intendance, intrigue, savoir
    tr={4 107 76 83 82 22 }   # traits, en positions dans l'ordre de chargement du jeu
    g_cul="maghreb_arabic"    # culture
    dnt=1000109911            # dynastie
    prs=43.609                # prestige
    piety=-0.439
    wealth=0.49987
    emp=2704242               # employeur     → edges (employer)
    ...
}
```

Un titre (section `title`) : lois répétées et historique des titulaires.

```
c_steiermark=
{
    liege=d_osterreich
    holder=2695618
    succession=gavelkind
    gender=cognatic
    law="cognatic_succession"     # clé répétée → Multi
    law="succ_gavelkind"
    ...
    last_change="1226.11.7"
    history=
    {
        769.1.1= { holder=260392 }                                   # titulaire seul
        ...
        1247.3.3= { holder={ who=2723321 type=inheritance } }        # titulaire + mode d'acquisition
    }
}
```

Une province (section `provinces`) :

```
1=
{
    name="Vesturland"
    culture=norwegian
    religion=catholic
    max_settlements=1
    modifier= { modifier="trade_route" date="1245.4.23" }    # clé répétée
    ...
}
```

### 1.4 Données statiques du jeu (`ck2sim/gamedata.py`)

Trois informations ne sont pas dans la sauvegarde et sont lues dans les fichiers du jeu :

| Besoin | Fichiers | Règle |
|---|---|---|
| Nom des traits | `common/traits/*.txt` | l'identifiant d'un trait est sa position (à partir de 1) dans l'ordre de chargement : fichiers triés par nom, puis ordre des définitions |
| Dynasties historiques | `common/dynasties` | la sauvegarde ne stocke que les dynasties créées en jeu ; un personnage omet sa culture et sa religion quand elles sont celles de sa dynastie, d'où la fusion des deux sources |
| Province → comté | `history/provinces/*.txt` | le numéro de province est en tête du nom de fichier, le comté dans `title = c_…` |

---

## 2. Le format des tables

Toutes les tables sont en CSV (UTF-8, séparateur `,`, en-tête sur la première ligne), dans `data/processed/<run_id>/`.
Chaque ligne porte `run_id` ; les tables par instantané portent aussi `snapshot_date`.

Conventions communes :
- **Dates** : deux formes, la date du jeu (`1247.3.3`) et une année décimale (`year`, `start_year` : `1247.172`) pour trier et calculer des durées.
- **Identifiants** : `id` de personnage (entier), identifiant de titre préfixé par son rang (`b_` baronnie, `c_` comté, `d_` duché, `k_` royaume, `e_` empire).
- **Booléens** : `True` / `False`. **Listes** : valeurs séparées par `;` (`traits`, `laws`). **Valeur absente** : champ vide.

### 2.1 Vue d'ensemble

| Table | Grain (une ligne = …) | Clé | Lignes (`run_001`) | Colonnes |
|---|---|---|---|---|
| `characters` | un personnage, vivant ou mort, dans la dernière sauvegarde | `id` | 165 881 | 34 |
| `edges` | un lien orienté entre deux personnages | (`src`, `dst`, `type`) | 424 899 | 5 |
| `title_history` | un changement de titulaire d'un titre | (`title`, `date`, `holder`) | 68 275 | 7 |
| `titles` | un titre dans un instantané | (`snapshot_date`, `title`) | 791 994 | 11 |
| `realms` | un royaume indépendant dans un instantané | (`snapshot_date`, `realm`) | 11 390 | 78 |
| `provinces` | une province dans un instantané | (`snapshot_date`, `province`) | 164 970 | 12 |
| `wars` | une guerre, sur toute sa période d'observation | `war_id` | 2 639 | 25 |
| `battles` | une bataille | (`war_id`, `date`, `location`) | 4 747 | 15 |

`characters`, `edges` et `title_history` sont **cumulatives** dans le jeu (morts et anciens titulaires restent dans la sauvegarde) :
elles sont donc extraites de la dernière sauvegarde seulement (option `--characters all` pour les extraire de chaque sauvegarde).
Les autres sont des **instantanés** : une copie par sauvegarde.

### 2.2 `characters`

| Colonnes | Contenu |
|---|---|
| `id`, `name`, `female`, `nickname` | identité |
| `birth`, `death`, `alive`, `age` | dates du jeu ; `age` en années à la date de l'instantané ou du décès |
| `dynasty`, `dynasty_name`, `culture`, `religion`, `government` | culture et religion complétées par la dynastie quand la sauvegarde les omet |
| `father`, `mother`, `real_father`, `liege`, `killer` | identifiants de personnages (repris dans `edges`) |
| `job`, `n_titles`, `top_tier` | poste au conseil, nombre de titres, plus haut rang détenu |
| `prestige`, `piety`, `wealth`, `health`, `fertility` | valeurs numériques |
| `traits` | noms des traits, décodés depuis les positions (`brilliant_strategist;brave;…`) |
| `diplomacy`, `martial`, `stewardship`, `intrigue`, `learning` | les 5 attributs, depuis `att={…}` |

### 2.3 `edges`

`src`, `dst`, `type` : un lien orienté du personnage `src` vers `dst`.

| `type` | Clé source | Lignes |
|---|---|---|
| `liege` | `lge` | 129 061 |
| `spouse` | `spouse` | 88 754 |
| `father` | `fat` | 84 804 |
| `mother` | `mot` | 77 242 |
| `killer` | `killer` | 18 401 |
| `employer` | `emp` | 17 906 |
| `real_father` | `rfat` | 5 980 |
| `guardian` | `guardian` | 2 029 |
| `lover` | `lover` | 562 |
| `consort_of` | `consort_of` | 160 |

### 2.4 `title_history`

`title`, `date`, `year`, `holder`, `change_type` : chaque entrée `history` des titres.
`change_type` vient de `holder={ who=… type=… }` ; il est vide pour les titulaires historiques de départ, écrits `holder=…`.

| `change_type` | Lignes | `change_type` | Lignes |
|---|---|---|---|
| (vide) | 28 062 | `holy_war` | 733 |
| `inheritance` | 26 121 | `invasion` | 604 |
| `election` | 5 143 | `revolt` | 290 |
| `grant` | 4 072 | `faction_demand` | 141 |
| `claim` | 1 022 | `host` | 112 |
| `revoke` | 1 000 | `usurp` | 49 |
| `created` | 901 | `duel` | 25 |

### 2.5 `titles`

`title`, `tier` (barony … empire), `holder`, `liege_title` (suzerain réel), `de_jure_liege` (suzerain de droit),
`succession`, `gender_law`, `laws` (liste `;`), `last_change`.

### 2.6 `realms` (78 colonnes)

Un royaume indépendant = un titre de plus haut rang sans suzerain, avec tout ce qui en dépend, calculé à chaque instantané.

| Groupe | Colonnes |
|---|---|
| Taille et structure | `tier`, `n_counties`, `n_duchies`, `n_kingdoms`, `n_baronies`, `n_provinces`, `n_holdings`, `demesne_counties`, `demesne_share`, `n_vassals`, `n_direct_vassals` |
| Diversité | `n_cultures`, `n_religions`, `culture_entropy`, `religion_entropy` (entropie de Shannon, en bits, des cultures et religions des provinces), `main_culture`, `main_religion`, `ruler_culture_share`, `ruler_religion_share` |
| Bâtiments | `n_trade_posts`, `n_hospitals` |
| Lois | `succession`, `gender_law`, `law_*` (centralisation, statut des femmes, guerres entre vassaux, impôts…) |
| Souverain et dynastie | `holder` et `holder_*` (âge, sexe, culture, religion, attributs, traits), `government`, `holder_dynasty`, `dynasty_alive_members`, `holder_children`, `wealth`, `prestige`, `piety` |
| Durées | `title_first_year`, `reign_start_year`, `reign_years`, `years_observed` |
| Guerres | `wars_as_attacker`, `wars_as_defender` |
| Évolution sur 10 ans | `has_past_10y`, `*_change_10y`, `n_counties_growth_10y`, `same_holder_10y`, `same_dynasty_10y`, `holder_changes_10y`, `wars_attacker_mean_10y`, `wars_defender_mean_10y` |

Règle des colonnes d'évolution : elles ne lisent **que des instantanés antérieurs**. L'instantané de référence est le plus proche
de 10 ans avant (à ±1,5 an près) ; s'il n'existe pas, `has_past_10y` vaut `False` et les colonnes restent vides.
La fenêtre se règle avec `--window`. Ce comportement est couvert par `tests/test_evolution.py`.

### 2.7 `provinces`

`province`, `name`, `county`, `realm` (royaume indépendant qui la contrôle), `culture`, `religion`,
`n_holdings`, `max_settlements`, `has_trade_post`, `has_hospital`.

### 2.8 `wars` et `battles`

Une guerre apparaît dans toutes les sauvegardes où elle est active ; `wars` la réduit à **une ligne**,
avec `first_seen` et `last_seen` (premier et dernier instantané où elle est vue).
`war_id` = `run_id:date_de_début:attaquant:défenseur`, stable d'une sauvegarde à l'autre.

| Table | Colonnes |
|---|---|
| `wars` | `name`, `casus_belli`, `target_title`, `start`, `start_year`, `attacker_*` et `defender_*` (id, culture, religion, gouvernement, royaume), `same_culture`, `same_religion`, `n_attackers`, `n_defenders`, `n_battles`, `observed` |
| `battles` | `date`, `year`, `location` (province), `attacker_won`, `attacker_owner`, `defender_owner`, `attacker_leader`, `defender_leader`, `attacker_troops`, `attacker_losses`, `defender_troops`, `defender_losses`, `score` |

Troupes et pertes : la sauvegarde donne, pour chaque type de troupe, une paire `{pertes effectif_initial}` ; les deux valeurs sont additionnées sur tous les types (`li`, `hi`, `pi`, `lc`, `hc`, `ar`, `ha`, `ca`, `wa`, `gs`).
