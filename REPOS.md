# Remotes Git — Fusion Layer

| Remote | Repo | Visibilité | Usage |
|---|---|---|---|
| `origin` | https://github.com/Peter-Ufens/Fusion-Layer | **privé** | Ops : briefs, traces locales gitignorées, vault links |
| `public` | https://github.com/Peter-Ufens/fusion-layer-public | **public** | Vitrine : code + ADR + docs sans chemins perso |

## Sync vitrine (manuel / GO)

Depuis la racine privée, pousser un sous-ensemble vers `public` (pas de `planning/briefs`, pas de `context/PERSONNES`, pas de chemins vault).  
Script d’export (ops **privé seulement**) : `scripts/export_vitrine_publique.py` · **scanne le contenu** après copie et **refuse** l’export si motif de zone / chemin perso / forme de secret.

## Règle

Le dépôt **privé** reste la source de vérité ops.  
Le dépôt **public** ne doit contenir ni PII, ni titres de fenêtres live, ni secrets.
