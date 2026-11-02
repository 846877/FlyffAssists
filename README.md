# FlyffAssist

Extension Chrome pour **Flyff Universe**, à utiliser **pendant que tu joues** : ton perso soutien suit ton perso principal, le soigne quand ses PV passent sous un seuil et relance ses buffs tout seul.

## Pourquoi une extension

L'extension tourne dans la page du jeu et envoie les touches directement au jeu, comme les autres extensions Flyff. Ça marche même quand la fenêtre du soutien n'est pas au premier plan, alors qu'un programme Windows externe voit ses touches ignorées par Chrome dans ce cas.

## Installation

1. Télécharge `FlyffAssist-extension.zip` dans la [release « latest »](../../releases/tag/latest) et dézippe-le dans un dossier que tu gardes.
2. Dans Chrome, ouvre `chrome://extensions` et active le **Mode développeur** (en haut à droite).
3. Clique sur **Charger l'extension non empaquetée** et choisis le dossier dézippé.
4. Recharge les pages du jeu (F5).

Pour une mise à jour : remplace le contenu du dossier, clique sur ↻ sur la carte de l'extension, puis recharge le jeu.

## Utilisation

Un panneau FlyffAssist apparaît dans chaque fenêtre du jeu. Tu peux le déplacer en le tirant par son titre, et le réduire avec ▾.

1. **Dans la fenêtre du soutien**, cible ton perso principal (clic sur lui). La barre de PV de la cible s'affiche en haut de l'écran.
2. **PV de la cible** : ton perso principal doit être à 100 % PV. Clique sur « Calibrer la barre », puis sur le début (gauche) et la fin (droite) de la barre rouge en haut de l'écran. Le panneau doit afficher environ 100 %.
3. **Soin** : la touche de ton soin et le seuil de PV.
4. **Buffs** : jusqu'à 8 buffs, chacun avec sa touche et son temps de relance en secondes. Tous partent à l'activation.
5. **Suivi** : `Z` par défaut (touche « suivre la cible » du jeu), renvoyée régulièrement.
6. Clique sur **▶ Activer sur ce perso**. Ne l'active que dans la fenêtre du soutien.

`F8` met en pause ou relance, **y compris depuis la fenêtre de ton perso principal**.

Touches acceptées : `1` à `0`, `alt+1` à `alt+0`, une lettre (`z`), `F1` à `F12`.

Les réglages sont communs aux deux fenêtres. L'état « activé » est propre à chaque fenêtre.

## Limites

- Si tu redimensionnes la fenêtre du soutien, recalibre la barre de PV.
- Le soin et les buffs partent sur la cible actuelle du soutien : garde ton perso principal en cible.
