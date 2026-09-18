# Fusion Layer

**Titre exact :** Fusion Layer  
**Dépôt de travail :** `D:\IA-CURSOR\Fusion-Layer`  
**Dernière mise à jour :** 2026-09-18  
**Agente Cursor :** Karen  
**Statut INDEX :** `cloture` (V1 preuve labo · 18/09)  
Voir [`CLOTURE.md`](CLOTURE.md) · remotes [`REPOS.md`](REPOS.md).

> **Session Cursor :** ouvrir d’abord [`LIRE-EN-PREMIER.md`](LIRE-EN-PREMIER.md)

## Rôle de ce dossier

Brique **autonome** de **fusion multimodale** (ADR-0005) : contrat d’events, fuseur, probes PC, smokes Ollama.  
Périmètre tech **Windows** et **mobile**. Les voisins réutiliseront Fusion plus tard ; ce lot ne les branche pas.

## CLI (probes)

```text
set PYTHONPATH=src
python -m fusion_layer network
python -m fusion_layer fuse-fixtures
python -m fusion_layer fuse-live --url URL --title TITRE --question "..." --llm
```

Tests : `python -m pytest tests/ -q` (depuis la racine, avec `PYTHONPATH=src` ou install editable).

## Structure

| Dossier / fichier | Contenu |
|---|---|
| **`LIRE-EN-PREMIER.md`** | Accueil auto (1er message) |
| **`LIEN-VAULT.md`** | Carte vault + chemins disque |
| `context/PERSONNES-SUIVI.md` | Sync ↔ `personnes.md` |
| **`docs/LIMITES-CONTEXTE-LLM.md`** | Budgets fuseur / LLM · navigateur interne vs externe |
| **`docs/API-CONSOMMATEURS.md`** | Comment un voisin consommera Fusion plus tard |
| `ADR/` | Décisions structurantes |
| `context/` | Contexte humain / technique local |
| `planning/` | Prochaines étapes |
| `planning/briefs-claude-code/` | Briefs Claude Code + `retours/` |
| `pieces/` | Pièces jointes brutes |
| `journal/` | Journal sessions |
| `REGLES.md` | Règles de ce projet |
| `CONSIGNES-GRAPHIFY.md` | Graphify au GO |
| `.graphifyignore` | Excludes Graphify |
| GitHub | **privé (ops)** · https://github.com/Peter-Ufens/fusion-layer-public · **public (vitrine)** · https://github.com/Peter-Ufens/fusion-layer-public |
| `presentations-gamma/` | Gamma (deck burger **05k** déjà existant côté hub) |
| `README.md` | Point d’entrée |

## Index ADR

| ADR | Titre | Statut |
|---|---|---|
| [ADR-0001](ADR/ADR-0001-contexte.md) | Contexte et objectifs | Accepté |
| [ADR-0002](ADR/ADR-0002-fusion-vers-llm-textuel.md) | Pipelines multimodaux autour d’un LLM textuel | **Accepté** (GO 18/09 soir) |
| [ADR-0003](ADR/ADR-0003-contrat-evenement-et-paquet.md) | Contrat d'événement Fusion v1 et paquet texte | **Accepté** (GO 18/09 · nuance paquet) |
| [ADR-0004](ADR/ADR-0004-perimetre-v1-5-pipelines-et-llm.md) | Périmètre V1 : 5 pipelines et LLM textuel | **Accepté** (GO 18/09) · amend. ADR-0005 |
| [ADR-0005](ADR/ADR-0005-brique-autonome.md) | Brique autonome (pas de branchement runtime) | **Accepté** (dictée 18/09) |
| [ADR-0006](ADR/ADR-0006-capteur-clavier-souris.md) | Capteur clavier / souris (présence au PC) | **Accepté** (GO 18/09) |

## Ce que ce projet n’est pas

| Autre | Rôle |
|---|---|
| Lyla-Vision / Ouïe / Memory / App / Avatar | Briques sensorielles ou UI |
| Lyla-Orchestrator | Orchestration workflows (gel) |
| A-traiter | Inbox · deck burger **05k** hébergé côté hub |

## Liens

- Profil : `D:\Obsidian\Obsidian\Peter-Vault-Local\00-Meta\profil-peter\Profil-Peter-Canonique.md`
- INDEX : `D:\IA-CURSOR\INDEX.md`
- Vault : [[02-Projets/Fusion-Layer]] (note Obsidian)
- Gamma burger (05k) : https://gamma.app/docs/Le-burger-comment-on-empile-les-sens-dune-IA-50tvqbr74jqyq84
