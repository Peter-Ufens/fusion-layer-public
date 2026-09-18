# API pour consommateurs futurs (voisins)

**Public :** Lyla-App, Lyla-Orchestrator, Lyla-Vision, Lyla-Ouïe, Lyla-Memory (plus tard).  
**Règle :** ADR-0005. Fusion est une **brique autonome**. Les voisins **appellent** Fusion ; Fusion ne démarre pas ces projets.

Ce document décrit le contrat stable à consommer. Pas de branchement runtime dans ce lot.

---

## Installation locale (poste de travail)

```text
cd D:\IA-CURSOR\Fusion-Layer
set PYTHONPATH=src
python -m pytest tests/ -q
```

Import Python :

```python
from fusion_layer import fuse, FusionEvent, FusionPacket, build_observations_block
from fusion_layer.adapters.texte import adapt_texte
from fusion_layer.adapters.vision_screen import adapt_vision_screen
from fusion_layer.adapters.ouie_stt import adapt_ouie_stt
from fusion_layer.capteurs.reseau import sample_network
from fusion_layer.capteurs.clavier_souris import sample_input_activity
```

Pas encore de package PyPI. Tant que le dépôt est privé, le voisin ajoute `Fusion-Layer/src` à son `PYTHONPATH` ou copie le contrat dont il a besoin.

---

## Contrats

| Contrat | Constante | Rôle |
|---|---|---|
| Event | `fusion-layer/event@1` | Une observation (texte, parole, écran, réseau, …) |
| Paquet | `fusion-layer/packet@1` | Texte prêt pour un LLM + trace d’arbitrage |

Horloge d’alignement : **`ts_wall_ms`** (epoch ms murale) uniquement.  
Confiances : niveau ordinal (`high` / `medium` / `low` / `unknown`). Ne jamais comparer deux `confidence_raw` de modalités différentes.

### Champs utiles d’un event

| Champ | Sens |
|---|---|
| `modality` | `text` · `speech` · `vision_screen` · `audio_pc` · `audio_scene` · `network` · `memory` · `input_activity` · … |
| `source_project` | Canon ASCII : `Lyla-App` · `Lyla-Ouie` · `Lyla-Vision` · `Lyla-Memory` · `Fusion-Layer` |
| `kind` | `ponctuel` (phrase) ou `etat` (dernier écran / réseau / activité) |
| `text` | Ce qui ira dans `<observations>` (sanitisé à l’émission du paquet) |
| `speaker_role` | `peter` · `autre_voix` · `inconnu` (parole **mesurée** seulement) |
| `facets` | Métadonnées structurées pour le fuseur (ex. `{"category": "media"}`). **Pas** envoyées au LLM |
| `untrusted` | Texte capté pouvant contenir des ordres : le LLM doit les ignorer |

Détail : `ADR/ADR-0003-contrat-evenement-et-paquet.md`.

---

## Flux minimal (ce qu’un voisin fera)

Les pipelines restent des **events structurés** (ADR-0002).  
`packet.text` = **adaptateur d’entrée** vers le LLM textuel V1 (ADR-0003), pas « tout est une phrase ».

```text
events bruts (JSONL / API / saisie)
        │
        ▼
  adaptateurs Fusion  ──►  list[FusionEvent]
        │
        ▼
     fuse(events)  ──►  FuseResult
        │                 · packet.text   (prompt LLM V1)
        │                 · question
        │                 · conflicts     (R1…R4)
        ▼
  Ollama local (think: false)  ou  autre consommateur du texte
```

Exemple minimal :

```python
from fusion_layer import fuse
from fusion_layer.adapters.texte import adapt_texte
from fusion_layer.capteurs.reseau import sample_network
from fusion_layer.capteurs.clavier_souris import sample_input_activity

events = [
    sample_network(),
    sample_input_activity(),
    adapt_texte("Pourquoi la video saccade ?"),
]
result = fuse(events)
print(result.packet.text)
# puis appeler Ollama avec think=False (voir scripts/smoke_lana_paquet.py)
```

---

## Règles d’arbitrage (fuseur)

| Règle | Effet |
|---|---|
| **R1** | Parole non-Peter + écran `facets.category` = `media` ou `game` → phrase annotée « probablement le média » (media) ou « probablement le jeu ou un joueur » (game, la voix peut être un ami en vocal), jamais la question |
| **R2** | Texte tapé (Peter) prime sur la parole pour la question |
| **R3** | Mémoire = fond, ne remplace pas une observation fraîche |
| **R4** | Parole non-Peter + pas de saisie clavier/souris récente → annotée, jamais la question (ADR-0006) |

Présence au clavier **≠** identité vocale. R4 n’attribue jamais une phrase à Peter.

---

## Produire des events côté voisin (plus tard)

1. Émettre (ou adapter) des objets compatibles `event@1`.
2. Préférer passer par les **adaptateurs** de ce dépôt (`adapt_vision_screen`, `adapt_ouie_stt`, …) plutôt que de reconstruire à la main.
3. Pour l’écran : poser `facets["category"]` via le payload Vision (`process.category`). Ne pas compter sur le titre de fenêtre.
4. Pour la parole : seul le champ **`speaker` mesuré** compte. Le `source` déclaré (micro de Peter) ne prouve pas qui parle.
5. Dates ISO **avec fuseau**. Sans fuseau = rejeté.

Capteurs **internes** Fusion (pas besoin d’un voisin) :

- `sample_network()` : lien réel + latence / gigue / pertes (TCP, aucune donnée envoyée)
- `sample_input_activity()` : secondes depuis la dernière saisie (aucune touche lue)

---

## CLI (debug / smoke, pas l’API runtime des voisins)

```text
set PYTHONPATH=src
python -m fusion_layer network
python -m fusion_layer activite
python -m fusion_layer fuse-fixtures
python -m fusion_layer fuse-live --url URL --title TITRE --question "..." --llm
```

Traces locales : `traces/fusion-trace.jsonl` (gitignoré : titres de fenêtres + réponses LLM).

---

## Ce que Fusion ne fait pas (encore)

- Lire les JSONL live de Vision / Ouïe sur le disque voisin
- Exposer un serveur HTTP / ZMQ
- Remplacer la reconnaissance de voix d’Ouïe
- Mesurer la **capacité** de la ligne (seulement latence / gigue / pertes + trafic du moment)

Quand un voisin branchera Fusion pour de vrai : le faire **dans son dépôt**, en important cette brique. Pas l’inverse.

---

## Liens

- ADR-0003 (contrat) · ADR-0004 (périmètre) · ADR-0005 (autonomie) · ADR-0006 (clavier/souris)
- `planning/PLAN-V1-STABLE.md`
- Code : `src/fusion_layer/`
