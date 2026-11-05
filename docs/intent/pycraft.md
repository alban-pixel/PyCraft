# Intention — PyCraft

> Confirmée le 21 octobre 2026. Contrat de départ du projet ; toute décision
> ultérieure doit pouvoir s'y rattacher.

> **Suite (4 novembre 2026) :** l'objectif et le public restent valables, mais
> la contrainte « rendu avec les primitives 2D de Pyxel » a été levée — le jeu
> est rendu par le GPU (`moderngl`) dans `pycraft-gpu/` (branches `SWE-2`,
> `m1-pro`). Voir [`pycraft-gpu/README.md`](../../pycraft-gpu/README.md) et
> [`docs/technique.md`](../technique.md).

## Énoncé

- **Livrable** : un monde de blocs en vraie perspective 3D, vue première personne,
  où l'on se déplace, tourne la tête, casse et pose des blocs — rendu avec les
  primitives 2D de Pyxel.
- **Pour qui** : Alban, projet NSI ; le professeur / jury regarde une démo de
  quelques minutes.
- **Pourquoi maintenant** : échéance dans 2 à 4 semaines, aucune grille imposée —
  c'est le rendu qui doit marquer.
- **Succès** : fluide (20–30 fps visés), l'effet 3D saute aux yeux, casser/poser
  fonctionne, et le code est explicable à l'oral.
- **Contrainte** : Pyxel ne dessine qu'en 2D (pas de moteur 3D) et Python pur est
  lent → la 3D doit être construite à la main.
- **Hors périmètre** : survie (vie, faim), mobs, craft, inventaire complet, monde
  infini en streaming, multijoueur, sauvegarde serveur, packs de textures.

## Dépôt

- GitHub : https://github.com/alban-pixel/PyCraft (vide au 21/10/2026)
- Local : `/Users/Apple/Documents/NSI/NSI-Game`

## Ce que cette intention exclut volontairement

Tout ce qui ajoute de la profondeur de jeu sans améliorer la démo visuelle est
repoussé. Si un arbitrage est nécessaire, **le rendu gagne**.
