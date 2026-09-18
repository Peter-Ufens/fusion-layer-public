# ADR-0002 — Pipelines multimodaux autour d’un LLM textuel

- **Statut :** **Accepté** (GO Peter 18/09 · dictée + validation)
- **Date :** 2026-09-18
- **Décideur :** Peter UFENS
- **Rédaction :** Karen (= Cursor) · vision Peter (dictée 18/09)
- **Titre projet :** Fusion Layer
- **Remplace la lecture :** l’ancienne formulation « late fusion = tout convertir en phrases » (proposée le matin du 18/09)

## Contexte

Le vault et le plan Lyla-OS V2 mentionnent un Fusion Layer. On a parfois envisagé des LLM « omni » (image + son en entrée native).

Dictée Peter (18/09, précisée le soir) : la stratégie n’est **pas** « tout traduire en texte pour le LLM ». C’est une **vision produit** :

1. On s’appuie d’abord sur **ce qu’on a en vision** (sens / brique déjà là).
2. On précise qu’on travaille avec un **LLM textuel** (pas un omni qui remplace les capteurs).
3. On **ajoute des couches** : voix, clavier/souris, réseau, etc. = des **pipelines / capteurs**.
4. On **crée ces pipelines**. On ne définit pas Fusion comme un convertisseur de phrases.

## Décision

1. **Cible V1 = LLM textuel** (Ollama local, infra machine ; voir ADR-0005). Ce n’est pas un branchement au projet `Lana-Ollama`. Ce n’est pas un LLM multimédia natif en entrée.
2. **Fusion = couches de pipelines** autour de cette cible : vision (forme compatible), parole, audio PC, réseau, présence clavier/souris (ADR-0006), texte saisi, etc. Chaque pipeline produit des **events structurés** (contrat ADR-0003).
3. **La vision produit n’est pas « tout devient une phrase ».** Les capteurs restent des observations typées (modalité, horloge, confiance, facettes). Le fait de présenter un **paquet texte** au LLM est un **adaptateur d’entrée** vers le modèle textuel (détail ADR-0003), pas la définition du projet.
4. **Brique autonome** (ADR-0005) : on avance dans ce dépôt ; les voisins réutiliseront Fusion plus tard.
5. **Hors V1 :** LLM omni natifs, early fusion par embeddings, remplacer les pipelines par un seul modèle multimodal.

## Conséquences

- (+) Aligné deck burger : on prouve l’**arbitrage entre sens**, pas l’empilement de projets.
- (+) On peut ajouter un pipeline (ex. clavier/souris) sans changer la nature du LLM.
- (+) Moins de VRAM / complexité qu’un omni 14B.
- (−) Le LLM textuel ne « voit » pas les pixels ni le timbre : il reçoit ce que le fuseur lui présente (souvent via le paquet texte V1).
- (−) Qualité « monde réel » dépendra plus tard des producteurs voisins.

## Liens

- `planning/CARTOGRAPHIE-PIPELINES-MULTIMODAUX.md`
- `planning/PLAN-V1-STABLE.md`
- ADR-0001 · ADR-0003 · ADR-0004 · ADR-0005 · ADR-0006
- `docs/API-CONSOMMATEURS.md`
