# ADR-0004 · Périmètre V1 : 5 pipelines et LLM textuel

- **Statut :** Accepté (GO Peter 18/09)
- **Date :** 2026-09-18
- **Décideur :** Peter UFENS
- **Rédaction :** Bob (= Claude Code) · amendements Karen (think:false obligatoire)
- **Titre projet :** Fusion Layer
- **Dépendances :** ADR-0002 et ADR-0003 encore **proposées** (contrat déjà codé en avance)

## Contexte

Dictée Peter du 18/09 (2e demande de la session) :

- V1 avec **au moins 5 pipelines** : **texte**, **réseau**, **visuel**, **audio avec Lyla**.
- **Réutiliser** ce qui est déjà construit dans les autres projets, puis augmenter progressivement.
- Cobayes : **vidéos** et **jeux vidéo**. Comprendre le contenu diffusé à l'écran au fil de l'eau.
- Nommer le **LLM local** utilisé, pour pouvoir **démontrer** qu'on l'a utilisé.

`planning/PLAN-V1-STABLE.md` (Karen, draft) prévoyait : Texte, Ouïe, Vision (webcam et / ou écran), Mémoire. Pas de réseau, pas d'audio PC.

### Inventaire (observé sur disque le 18/09)

| # | Pipeline | Déjà construit ? | Où | Ce qu'on lit |
|---|---|---|---|---|
| 1 | **Texte** (P01) | oui | Lyla-App (Electron vers Ollama) | V1 : saisie directe dans l'outil Fusion (passe-plat) |
| 2 | **Réseau** (P22, nouveau) | **non** | rien de tel : scripts de lien LAN (Parc-Maison), notes panne fibre (Suivi-Pro) | à construire (`psutil` 7.1.0 déjà installé) |
| 3 | **Visuel écran + vidéo** (P09 · P13) | oui | Lyla-Vision : `screen.context`, `scripts/session_screen.py` (profil `film` = 1 observation / 5 s), `src/session_contenu.py` (capture déclenchée + OCR) | events JSONL + trace de session |
| 4 | **Audio micro** (P02 · P03) | oui | Lyla-Ouïe Phase A (STT Whisper) + Phase C (qui parle) | `events/stt-test.jsonl` |
| 5 | **Audio PC** (P05) | oui (B2, code mergé 28/08 · **test film 10 min à faire par Peter**) | Lyla-Ouïe `system_listen` | `events/system.jsonl` (`media.playback`) |
| 6 | Mémoire (P20), bonus | oui | Lyla-Memory `GET /prompt-block` | API (fixture si arrêtée) |

**4 pipelines sur 5 existent déjà.** Seul le réseau est à construire.

### LLM installés (`ollama list`, 18/09)

| Famille | Tags | Utilisable pour le paquet Fusion ? |
|---|---|---|
| Généralistes officiels | `qwen3.5:9b-gpu` · `qwen3.5:9b` · `gemma3:27b` | **oui** |
| Persona Lana | `Lana/qwen3.6-27b-*` · `Lana/gemma4-12b-heretic` · `lana-coder` | non : persona qui déborde (mesuré, voir plus bas) · Zone A-1 / A-2 |
| Garde-fous retirés | `*abliterated*` · `*heretic*` | non : pas pour une démo publique |
| Code | `qwen2.5-coder:32b` · `qwen25-coder-32b` · `qwen3-coder` | non : spécialisés code |
| Vision | `llava:7b` · `moondream` | non : outils de la brique Vision |
| Embeddings | `nomic-embed-text` | non |

Mesures déjà faites dans l'écosystème (Lyla-Vision, `planning/PLAN-PONT-LLM-CONTROLE-VISION-2026-09-09.md`, review R-S16 GO) : avec `think: false` et une consigne système minimale, **`qwen3.5:9b-gpu` = 23/25, s'abstient 4 fois sur 5 face à une zone noire (n'invente pas), 728 ms** ; `gemma3:27b` = 22/25, 3/5, 1 956 ms. Le bake-off du 09/09 montre aussi les tags `Lana/*` répondre **en jeu de rôle persona** sur une tâche technique.

Smoke Bob du 18/09 (paquet **fictif** : réseau instable + YouTube plein écran + audio PC + phrase piégée d'une autre voix + question de Peter) sur `qwen3.5:9b-gpu` (digest `d6b09270c793`) : **n'obéit pas** à la phrase piégée, l'attribue au média, relie la saccade vidéo aux pertes réseau (2 modalités croisées). **34 s à froid, dont 14 s de chargement** : mesure à chaud à faire.

## Options considérées (LLM)

### Option A : `qwen3.5:9b-gpu` (retenue)

| Dimension | Évaluation |
|---|---|
| Qualité mesurée | 23/25 · abstention 4/5 (la meilleure) |
| Latence | 728 ms à chaud (mesure Vision) · 14 s de chargement à froid |
| Mémoire GPU | 6,6 Go : tient à côté d'un jeu, de Whisper et de Moondream sur la RTX 5090 (32 Go) |
| Déjà câblé ailleurs | oui : `Lyla-Vision/src/llm_stream/client.py` (`MODELE_DEFAUT`) |

### Option B : `gemma3:27b`

| Dimension | Évaluation |
|---|---|
| Qualité mesurée | 22/25 · abstention 3/5 |
| Latence | 1 956 ms à chaud |
| Mémoire GPU | 17 Go : risqué pendant une session de jeu |

**Rôle :** secours et comparaison, hors session de jeu.

### Option C : un tag `Lana/*` (persona)

**Rejetée :** persona mesurée qui déborde sur une tâche technique, tags classés Zone A.

## Analyse des compromis

A gagne sur les trois critères qui comptent pour la démo : **ne pas inventer** (abstention), **tenir à côté d'un jeu** (mémoire GPU), **répondre vite**. B garde de l'intérêt pour comparer la qualité des réponses quand le GPU est libre. Choisir le même modèle que Vision évite aussi d'avoir deux « cerveaux » différents dans l'écosystème pour une même tâche de synthèse.

## Décision

1. **V1 = 5 pipelines** : Texte · Réseau · Visuel écran / vidéo · Audio micro · Audio PC. Mémoire = 6e si l'énergie le permet (déjà prête). Webcam (P08) et émotion visage (P11) : V1.1.
2. **Réutiliser** : les 4 pipelines existants sont lus en **lecture seule** (ADR-0003, règle 8). Aucune modification des briques.
3. **Réseau = seul pipeline à construire.** Exception assumée à ADR-0002 § 3 (les briques gardent leur code) : **capteur interne** `src/fusion_layer/capteurs/reseau.py` tant qu'il reste petit. S'il grandit (historique, alertes, mobile), scission en brique dédiée via A-traiter et nouvelle ADR.
   - **Mesure :** type de lien actif (Ethernet, Wi-Fi, partage de connexion USB du téléphone) · débit descendant / montant (compteurs système) · latence, gigue et perte vers la passerelle et vers une cible Internet réglable.
   - **Ne mesure pas :** aucune capture de paquets · aucune liste de sites ou de connexions par application · aucune adresse IP dans le texte du paquet · aucun droit administrateur.
   - Event de type `etat`, cadence basse réglable.
4. **Vidéo « au fil de l'eau »**, avec honnêteté :
   - Compréhension par la session écran (quelle application, quelle fenêtre, quel site · 1 observation / 5 s en profil `film`) et par la lecture déclenchée (OCR, sous-titres affichés).
   - **Quelques secondes de retard**, pas une analyse vidéo image par image.
   - Flux protégés (Netflix, Prime Video) : **capture noire**, rapportée comme telle (règle Vision : on ne devine jamais une scène).
   - Audio PC = **contexte seulement** (« un média joue »). La règle Ouïe **« Jamais Whisper » sur la sortie PC est conservée**. La lever serait une décision séparée de Peter.
5. **LLM textuel V1 = `qwen3.5:9b-gpu`** (Ollama local, infra machine) · **`think: false` obligatoire** (sans lui, `/api/chat` peut renvoyer `content` vide tout en brûlant le budget `eval_count` ; constat Karen 18/09) · consigne système minimale · température 0 · `127.0.0.1:11434` · gardé chargé pendant une session (`keep_alive`) pour éviter les 14 s de chargement. Secours / comparaison : `gemma3:27b`. Le tag est déclaré en config, pas en dur. Smoke versionné : `scripts/smoke_lana_paquet.py` (nom historique ; ce n’est **pas** un branchement au projet `Lana-Ollama`).
6. **Preuve d'usage** : chaque paquet journalise ce que renvoie Ollama (`model`, `load_duration`, `total_duration`, `eval_count`) plus le `digest` du modèle (`/api/tags`). C'est cette trace qui **démontre** quel LLM a répondu.
7. **Cobayes V1** : (a) vidéo YouTube non protégée avec sous-titres · (b) session de jeu vidéo · (c) conflit voix / film (règle R1 proposée dans le retour Bob) · (d) réseau instable (partage de connexion tant que la fibre est coupée, ETA 23/09).

## Conséquences

- (+) 4 pipelines sur 5 déjà construits : V1 atteignable vite.
- (+) Le capteur réseau a une utilité immédiate (fibre coupée, connexion partagée).
- (+) Preuve LLM vérifiable (digest + durées dans chaque trace).
- (-) Partage du GPU avec le jeu : impact sur les images par seconde à mesurer.
- (-) Démarrage à froid de 14 s : garder le modèle chargé pendant une session.
- (-) Le dialogue d'une vidéo ou d'un jeu n'est compris que s'il est sous-titré à l'écran (règle Ouïe conservée).
- (-) Exception à ADR-0002 § 3 pour le capteur réseau.
- (-) Prérequis : Peter doit faire le test Ouïe B2 (film 10 min).

## Actions

1. [x] GO Peter (ADR-0004) · 18/09 · 0002/0003 restent proposées
2. [x] Karen : `PLAN-V1-STABLE.md` + `prochaines-etapes.md` alignés
3. [ ] Peter : test Ouïe B2 film 10 min (dans Lyla-Ouïe)
4. [ ] Capteur réseau + fixture + smoke hors ligne
5. [ ] Mesure à chaud `qwen3.5:9b-gpu` sur les fixtures, et impact sur un jeu (images par seconde avant / après)

## Amendement (ADR-0005 · 18/09)

« Réutiliser les pipelines existants » = **compatibilité de format** et éventuelle **copie de code dans ce dépôt**, pas un branchement runtime vers les projets Cursor voisins.  
Le LLM reste un appel **Ollama local**, pas une intégration au projet `Lana-Ollama`.

## Liens

- ADR-0002 · ADR-0003 · **ADR-0005**
- `Lyla-Vision/planning/PLAN-PONT-LLM-CONTROLE-VISION-2026-09-09.md` · `Lyla-Vision/docs/session-ecran-usage.md` (lecture d’inspiration)
- `Lyla-Ouïe/lyla_ouie/system_listen.py` (règle « Jamais Whisper », inspiration)
- Retour : `planning/briefs-claude-code/retours/RETOUR-CLAUDE-CODE-REVIEW-KICKOFF-V1-2026-09-18.md`
