# FlyffAssist

Application Windows pour **Flyff Universe**, à utiliser **pendant que tu joues** : ton perso soutien suit ton perso principal, le soigne quand ses PV passent sous un seuil et relance ses buffs tout seul.

## Comment ça marche

`FlyffAssist.exe` ouvre **lui-même** la fenêtre de ton perso soutien, dans Chrome (ou Edge), avec un profil dédié. Il pilote cette fenêtre de l'intérieur grâce au protocole de débogage de Chrome. Les touches partent depuis la page du jeu, donc la fenêtre du soutien n'a pas besoin d'être au premier plan. Un programme externe classique ne peut pas faire ça : Chrome ignore les touches qu'il envoie à une fenêtre en arrière-plan.

Ton perso principal, lui, reste dans ton navigateur habituel, comme avant.

## Installation

1. Télécharge `FlyffAssist.exe` dans la [release « latest »](../../releases/tag/latest).
2. Lance-le. Windows SmartScreen peut afficher un avertissement, car l'exe n'est pas signé : clique sur « Informations complémentaires » puis « Exécuter quand même ».

Google Chrome ou Microsoft Edge doit être installé.

## Utilisation

1. Clique sur **Ouvrir la fenêtre du soutien**.
2. Connecte-toi avec ton soutien. La connexion est mémorisée pour les fois suivantes.
3. Un panneau FlyffAssist apparaît dans le jeu. Tu peux le déplacer par son titre et le réduire avec ▾.
4. **Cible ton perso principal** : la barre de PV de la cible s'affiche en haut de l'écran.
5. **PV de la cible** : ton perso principal doit être à 100 % PV. Clique sur « Calibrer la barre », puis sur le début (gauche) et la fin (droite) de la barre rouge en haut de l'écran. Le panneau doit afficher environ 100 %.
6. Règle **Soin** (touche, seuil), **Buffs** (jusqu'à 8, chacun avec son temps de relance en secondes) et **Suivi** (`Z` par défaut, la touche « suivre la cible » du jeu).
7. Clique sur **▶ Activer sur ce perso**.

`F8` met en pause ou relance **depuis n'importe quelle fenêtre de Windows**.

**Régler une touche** : clique dans le champ, puis appuie sur la touche (avec Alt si besoin). L'appli enregistre exactement ta frappe, ce qui compte en AZERTY : le jeu prend un « z » tapé pour la touche « avancer » (ZQSD). Pour le suivi, enregistre la touche indiquée pour « Suivre » dans les options de touches du jeu.

## Limites

- Si tu redimensionnes la fenêtre du soutien, recalibre la barre de PV.
- Le soin et les buffs partent sur la cible actuelle du soutien : garde ton perso principal en cible.

## Variante extension Chrome

Le même assistant existe en extension (`FlyffAssist-extension.zip` dans la release), à charger depuis `chrome://extensions` en mode développeur.

## Développement

```
pip install -r app/requirements.txt
python app/flyffassist_app.py
```

Le cœur de l'assistant est `extension/flyffassist.js` : panneau, lecture des PV, envoi des touches. Il est partagé entre l'exe et l'extension.
