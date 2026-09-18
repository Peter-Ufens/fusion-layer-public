# Limites de contexte (LLM + fuseur) · V1

**Public :** Peter, Karen, Bob, consommateurs futurs.  
**Pourquoi :** le LLM textuel n’a qu’une fenêtre d’attention limitée. Fusion doit le dire clairement (ADR-0002 / 0003).

---

## Ce que le LLM reçoit

| Couche | Limite V1 | Effet |
|---|---|---|
| Fenêtre temporelle fuseur | `window_ms` = **30 s** (ponctuels) | Une phrase trop vieille sort du paquet |
| États écran | max **10 min** | Dernière fenêtre / jeu retenu, pas l’historique long |
| États réseau | max **60 s** | Mesure périmée écartée |
| Présence clavier/souris | max **60 s** | Idem |
| Budget texte écran | **600** caractères / event | Titre long tronqué (`…[tronque]`) |
| Budget parole | **400** caractères | Idem |
| Budget mémoire | **1 200** caractères | Idem |
| Réponse Ollama | `num_predict` = **256** jetons | Réponse courte volontairement |
| Température | **0** | Pas de « créativité » pour la démo |

Le paquet = **adaptateur d’entrée** vers le LLM (ADR-0003), pas un journal complet de la journée.

---

## Ce que le contexte ne contient pas

- Pas de pixels / OCR / capture d’écran (capteur fenêtre = titre + exe + moniteur).
- Pas d’identité vocale sûre sans mesure (F1).
- Pas de capacité réseau (seulement latence / gigue / pertes + trafic du moment).
- Pas le contenu privé mail/chat (catégories refusées).
- Pas l’historique multi-heures : seulement la fenêtre courante.

---

## Navigateur interne vs externe

| Environnement | Statut preuve |
|---|---|
| Navigateur **interne** Cursor | Labo OK, environnement plus contrôlé |
| Navigateur **externe** (Chrome/Brave/Edge, fenêtre OS) | Preuve « terrain » vision |
| Application desktop (ex. LinkedIn Store) | Ouverture applicative + contexte fenêtre |

**Protocole :** ouvrir → mesurer (`fenetre` / `fuse-live`) → **fermer** la fenêtre / le profil dédié pour ne pas laisser une vidéo tourner.  
Fermeture : **possible** en lançant un profil Chrome/Brave jetable (`--user-data-dir` temporaire) puis en tuant uniquement ce processus.

---

## Objectif « concentre-toi sur X » (V1)

Demander au LLM de se concentrer sur le navigateur, le jeu ou Cursor **ne débloque pas** plus de contenu.

| Sens | Ce que le LLM reçoit vraiment |
|---|---|
| Vision navigateur | Titre de fenêtre (ex. onglet wiki Fandom), **pas** le corps de page |
| Vision jeu | Titre + moniteur + `focus` oui/non |
| Vision Cursor | Titre Windows de l’IDE (projet/fichier seulement s’ils sont dans ce titre) |
| Audio PC | Réel seulement si Ouïe mesure ; sinon simulation marquée |
| Saisie | `actif` / `idle` global ; la consigne lie la saisie à `focus=oui` |
| Réseau | Latence / gigue / trafic du moment |

Script de preuve : `scripts/preuve_focus_objectif.py`.

---

## Ce que le code tranche à la place du LLM

Le modèle local (9B) peut se tromper quand le paquet contient plusieurs fenêtres (mesuré : 3/3 erreurs sur le premier plan avec 4 fenêtres). Les faits décisifs sont donc **calculés par le code** : ligne `<premier_plan>` (une seule fenêtre `focus=oui`), règles R1 à R4. Le LLM résume, il n’arbitre pas.

## Pas encore de plafond global

Nombre de fenêtres suivies hors focus illimité ; budget **par** observation seulement (pas de plafond jetons sur le paquet entier). Piste V1.1 : plafonner (ex. 4 fenêtres hors focus).

## Vie privée par programme, pas par site

Un webmail ou une messagerie **dans le navigateur** (Gmail, WhatsApp Web…) passe en catégorie `browser` : le titre d’onglet peut partir au LLM. En V1 on refuse surtout par **exécutable** (`chat` / `mail`). Exe WhatsApp Store observé : `WhatsApp.Root.exe` → catégorie `chat` (clé `whatsapp.root`).

---

## Liens

- `src/fusion_layer/config.py`  
- `docs/API-CONSOMMATEURS.md`  
- ADR-0002 · ADR-0003 · ADR-0005  
- Retour Bob limites : `planning/briefs-claude-code/retours/RETOUR-CLAUDE-CODE-LIMITES-V1-2026-09-18.md`
