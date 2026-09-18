# ADR-0006 · Capteur clavier / souris (présence au PC)

- **Statut :** **Accepté** (GO Peter 18/09)
- **Date :** 2026-09-18
- **Décideur :** Peter UFENS
- **Rédaction :** Bob (= Claude Code) · acceptation tracée par Karen (= Cursor)
- **Titre projet :** Fusion Layer
- **Complète :** ADR-0004 (acceptée : « au moins 5 pipelines ») · s'appuie sur ADR-0003 et ADR-0005

## Contexte

Dictée Peter du 18/09 (après la review Bob) : tout ce que le micro entendait était attribué à sa voix (faille F1, corrigée : sans voix mesurée, `inconnu`). Le projet Ouïe n'a pas encore une banque de voix propre. Peter propose donc un **capteur clavier / souris** comme **signe d'activité** : s'il tape ou bouge la souris, il est là.

Vérifié sur disque le 18/09 : **rien ne mesure l'activité clavier / souris** dans l'écosystème. Lyla-Vision lit la position du curseur à la demande (`src/screen_cursor.py`), sans notion d'inactivité. Lyla-Ouïe utilise une touche pour « pousser pour parler » (`--ptt`), mais **n'écrit pas ce mode dans ses events** (`meta.phase` vaut toujours `"A"`). Cette idée n'était donc prise en compte nulle part, ni dans la cartographie (P01 à P21) ni dans ADR-0004.

## Options considérées

### Option A : durée d'inactivité Windows `GetLastInputInfo` (retenue)

| Dimension | Évaluation |
|---|---|
| Ce qu'on obtient | Secondes depuis la dernière saisie, clavier et souris **confondus** |
| Vie privée | Aucune touche, aucun texte, aucune position. C'est l'API de l'écran de veille |
| Droits | Aucun (ni admin, ni crochet clavier) |
| Coût | Un appel système, instantané, rien en arrière-plan |

### Option B : crochets clavier / souris (`SetWindowsHookEx`, `pynput` en écoute globale)

**Rejetée.** Séparerait clavier et souris, mais c'est la technique d'un **enregistreur de frappe** : lecture de chaque touche, alertes antivirus, risque vie privée maximal. Hors de question pour une vitrine publique.

### Option C : « pousser pour parler » d'Ouïe comme preuve de voix

C'est la seule façon pour le clavier de prouver **qui parle** : Peter maintient une touche pendant qu'il parle. Ouïe sait déjà le faire, mais ne l'écrit pas dans ses events. **Hors de ce lot** (territoire Ouïe, ADR-0005). Piste : redirection vers Ouïe pour ajouter `meta.mode = "ptt"`, puis un adaptateur Fusion qui fait confiance à ce mode.

## Décision

1. **Nouveau capteur interne** `src/fusion_layer/capteurs/clavier_souris.py`, modalité **`input_activity`**, event de type `etat`, source `Fusion-Layer` / `fusion/input-activity@1`.
2. **Ce qu'il mesure** : secondes depuis la dernière saisie et un état décrit comme un **fait** : `actif` (≤ 60 s), `sans_saisie_recente` (≤ 10 min), `sans_saisie_longue`. Seuils en config, à calibrer.
3. **Ce qu'il ne fera jamais** : lire une touche, un texte ou une position, poser un crochet, tourner en arrière-plan. Un test garde-fou échoue si le code du capteur référence une API de lecture de touches.
4. **Présence ≠ voix.** Le capteur ne dit pas qui parle. Il ne sert **jamais** à faire d'une phrase « la question de Peter ».
5. **Règle R4** (fuseur) : parole non-Peter (`inconnu` / `autre_voix`) alors que personne n'a tapé ni bougé la souris récemment : la phrase est annotée `[sans_saisie_clavier_souris R4]`, gardée comme observation et tracée. R4 se cumule avec R1.
6. **Commande** `python -m fusion_layer activite` ; le capteur est inclus dans `fuse-live`.

## Conséquences

- (+) Un 6e sens utile tout de suite, sans dépendre d'Ouïe (ADR-0005).
- (+) Aide à distinguer « Peter regarde » (média, pas de saisie) et « Peter joue ou travaille » (saisie active).
- (+) Vie privée tenue par construction et par un test.
- (-) Clavier et souris confondus.
- (-) **Une manette de jeu ne compte pas** comme saisie pour Windows : pendant une partie à la manette, le capteur voit « pas de saisie ».
- (-) Il ne résout pas « qui parle » : pour ça, il faut l'option C (Ouïe) ou une banque de voix propre.

## Actions

1. [x] GO Peter (18/09).
2. [ ] Option C : redirection vers Ouïe (`meta.mode = "ptt"`) si Peter le souhaite.
3. [ ] V1.1 possible : activité manette (XInput), sans lire les boutons, seulement « la manette a bougé ».

## Liens

- ADR-0003 · ADR-0004 · ADR-0005
- Retour : `planning/briefs-claude-code/retours/RETOUR-CLAUDE-CODE-CAPTEUR-CLAVIER-SOURIS-2026-09-18.md`
