# FlyffAssist

Assistant de soutien pour **Flyff Universe**, à utiliser **pendant que tu joues** : ton second perso (le prêtre) suit ton perso principal, le soigne quand ses PV passent sous un seuil et relance ses buffs tout seul.

## Comment ça marche

- **Lecture des PV** : l'appli lit à l'écran la barre de PV de ton perso principal dans la fenêtre de groupe du prêtre, et en déduit un pourcentage.
- **Envoi de touches** : les touches sont envoyées directement à la fenêtre du prêtre (`PostMessage`). Tu n'as pas besoin de cliquer dessus : tu gardes la main sur ton perso principal.
- **Priorités** : soin d'abord, puis buffs arrivés à échéance (un par un, en laissant le temps d'incanter), puis la touche « suivre » quand rien n'est en cours.

## Installation (Windows)

1. Installe Python 3.11 ou plus récent depuis python.org (coche « Add to PATH »).
2. Double-clique sur `lancer.bat`. La première fois, il crée un environnement virtuel et installe les dépendances (`pywin32`, `mss`).

**Le plus simple** : télécharge `FlyffAssist.exe` dans la release « latest » du repo et lance-le. La config est enregistrée dans `config.json` à côté de l'exe.

Ou à partir des sources : `pip install -r requirements.txt` puis `python -m flyffassist`.

## Mise en place dans le jeu

- Ouvre chaque perso dans **sa propre fenêtre** Opera ou Chrome (pas deux onglets) et mets-les **côte à côte** : la fenêtre du prêtre doit rester visible, pas réduite.
- Mets le soin et les buffs du prêtre dans la barre **1 à 0**. `alt+1` est accepté mais moins fiable en arrière-plan.
- Le prêtre doit avoir ton perso principal **en cible** pour que soins et buffs partent sur lui.

## Réglages dans l'appli

1. **Fenêtre du prêtre** : clique sur « Choisir », puis survole la fenêtre du prêtre pendant 3 secondes. Utilise « Tester cette touche » pour vérifier que la touche part bien. Si rien ne se passe, passe le mode d'envoi de `top` à `render` et réessaie.
2. **Barre de PV** : ton perso principal doit être à 100 % PV. Clique sur « Bord gauche » et pointe le début de sa barre de PV dans la fenêtre de groupe du prêtre. Fais pareil avec « Bord droit ». Le champ « PV lus » doit afficher environ 100 %. Si la valeur est fausse, ajuste la tolérance.
3. **Soin** : touche, seuil en %, délai minimum entre deux soins.
4. **Buffs** : jusqu'à 8 buffs, chacun avec sa touche et son intervalle de relance en secondes. Tous partent au démarrage.
5. **Suivi** : par défaut `Z`, la touche « suivre » de Flyff Universe. Le prêtre suit sa cible actuelle, donc cible ton perso principal une fois au début (clic sur lui ou dans la fenêtre de groupe). L'appli renvoie `Z` toutes les 5 secondes, car le suivi du jeu décroche parfois (téléportation, combat, obstacle).

Option **« Re-cibler automatiquement »** : l'appli clique elle-même (sans bouger ta souris) au milieu de la barre de PV de ton perso principal dans la fenêtre de groupe du prêtre, à la même fréquence que le suivi. Plus besoin de cibler à la main, et si le prêtre perd sa cible, il la retrouve. Utilise « Tester le ciblage » pour vérifier.

Chaque section (soin, chaque buff, suivi) a sa case « Activé » pour l'allumer ou l'éteindre.

`F8` (réglable) met l'assistant en pause ou le relance, depuis n'importe quelle fenêtre.

## Tests

```
pip install pytest
python -m pytest tests
```

La logique (`engine.py`, `hp.py`, `keys.py`) est indépendante de Windows et testée. `winapi.py` et `app.py` ne tournent que sous Windows.
