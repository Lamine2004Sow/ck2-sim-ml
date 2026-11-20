# Outils du projet — rôle et utilité

Principe de choix : **le plus simple qui suffit**. Chaque outil répond à un besoin précis de la chaîne de données.

## 1. Simulation et collecte

| Outil | Utilité dans le projet |
|---|---|
| **Crusader Kings II** (v3.3.3, mode `-debug_mod` + `observe`) | La source : environ 20 000 personnages pilotés par le jeu, de 1066 à 1453. En mode observation, la partie tourne seule. |
| **Sauvegarde annuelle non compressée** (`settings.txt` : `autosave="YEARLY"`, `compress_autosaves=no`) | Produit chaque année un instantané lisible de tout le monde simulé. |
| **`scripts/collect_snapshots.sh`** (Bash + gzip) | Attend que le jeu ait fini d'écrire (taille stable), copie et compresse chaque sauvegarde (75 → 14 Mo), s'arrête à l'année voulue. |

## 2. Extraction et transformation

| Outil | Utilité |
|---|---|
| **Python 3.12, bibliothèque standard seule** | Aucune dépendance à installer pour l'extraction : `re`, `gzip`, `csv`, `argparse`, `collections`. |
| **`ck2sim.parser`** (parseur maison) | Lit le format texte Clausewitz (`clé=valeur`, blocs, clés répétées) et ne tokenise que les 5 sections utiles : environ 13 s par sauvegarde. |
| **`ck2sim.gamedata`** | Lit dans les fichiers du jeu ce que la sauvegarde ne contient pas : noms des traits, dynasties historiques, comté de chaque province. |
| **`ck2sim.extract`** | Transforme chaque sauvegarde en 8 tables CSV, regroupe les guerres observées sur plusieurs instantanés, calcule les colonnes d'évolution des royaumes. |
| **`unittest`** | 6 tests : parseur (blocs, listes, clés répétées) et colonnes d'évolution (aucune lecture du futur). |

Formats d'entrée et de sortie : voir [formats.md](formats.md).

## 3. Volumes et contraintes

- Une partie de 1230 à 1330 : 94 sauvegardes, environ 1,3 Go compressé, 258 Mo de tables CSV.
- Une partie collectée chaque année jusqu'en 1453 : environ 3 Go.
- Machine sans GPU, 15 Go de RAM, 8 cœurs : l'extraction ne lit que les sections utiles pour rester rapide et sobre en mémoire.
