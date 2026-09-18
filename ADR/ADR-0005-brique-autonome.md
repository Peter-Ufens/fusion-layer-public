# ADR-0005 — Brique autonome (pas de branchement runtime)

- **Statut :** Accepté (dictée Peter 18/09)
- **Date :** 2026-09-18
- **Décideur :** Peter UFENS
- **Rédaction :** Karen (= Cursor)
- **Titre projet :** Fusion Layer

## Contexte

Peter précise (dictée) : **Fusion Layer doit rester une brique unique, seule.**  
On n’enchaîne pas un « branchement » runtime vers Lyla-Vision, Lyla-Ouïe, Lyla-Memory, Lyla-App, Lana-Ollama (projets Cursor).  
On peut **regarder** et **réutiliser du code** déjà bâti ailleurs (copie / adaptation **dans ce dépôt**).  
Ce que Fusion produit doit pouvoir être **réutilisé plus tard par les autres projets**, sans que Fusion dépende d’eux pour avancer.

La formulation « brancher Lana » / « smoke live contre les JSONL Vision / Ouïe » orientait à tort vers une intégration croisée immédiate.

## Décision

1. **Autonomie runtime V1 :** ce projet avance et se teste **tout seul** (fixtures, smokes, capteurs internes). Aucun autre projet Cursor n’a à être lancé pour valider Fusion.
2. **Réemploi de savoir-faire :** lecture des voisins **autorisée** pour s’inspirer ; si un morceau de code est utile, il est **repris ou adapté ici** (ou un contrat JSON compatible est documenté ici). Pas d’import vivant depuis `D:\IA-CURSOR\Lyla-*` comme dépendance de build.
3. **Sens de réutilisation :** Fusion = **bibliothèque / brique** que Vision, Ouïe, App, Orchestrator pourront appeler **plus tard**. Ce lot ne câble pas ces appels.
4. **LLM :** appel **Ollama local** (`127.0.0.1:11434`, modèle déclaré en config). C’est de l’infra machine, pas un branchement au projet `Lana-Ollama`. Ne pas écrire « brancher Lana » pour ce lot.
5. **Adaptateurs :** ils connaissent des **formes d’événements compatibles** (alignées sur les contrats déjà vus chez les voisins) et se prouvent sur **fixtures appartenant à Fusion**. Brancher des chemins live vers les JSONL des voisins = **hors ce lot** (éventuel cran ultérieur + GO explicite).
6. **Amendement de lecture d’ADR-0004 :** la phrase « réutiliser en lecture seule les sorties des briques » s’entend comme **compatibilité de format / copie de patterns**, pas comme dépendance runtime à ces dépôts pour la V1.

## Conséquences

- (+) On avance sans attendre qu’Ouïe / Vision / Memory tournent.
- (+) Livrable clair pour les voisins plus tard (contrat event + paquet + fuseur).
- (+) Territoires respectés : pas d’écriture chez un voisin, pas de couplage de démarrage.
- (−) Les smokes « monde réel » (vrais JSONL d’une session Vision) sont reportés, avec GO dédié.
- (−) Risque de dérive de format si un voisin change son contrat : à gérer par version de schéma Fusion (`event@1`).

## Actions

1. [x] Mettre à jour `PLAN-V1-STABLE.md`, `prochaines-etapes.md`, `REGLES.md`, `CLAUDE.md`.
2. [x] Corriger les formulations « brancher Lana » / « smoke live voisins » dans le plan.
3. [ ] Suite de lot : enrichir **dans ce repo** (fixtures, fuseur, smoke Ollama, docs d’API pour consommateurs futurs).

## Liens

- ADR-0001 · ADR-0002 · ADR-0003 · ADR-0004  
- `planning/PLAN-V1-STABLE.md`
