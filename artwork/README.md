# Icona PureNote

`icon.svg` è il disegno vettoriale approvato: foglio e cursore verde salvia
(`#A3DCB0`) su fondo scuro (`#0C120F`), senza font, immagini incorporate o
risorse esterne.

`../logo.png` è la versione 1024 × 1024 per Kivy, icona Android tradizionale
e schermata iniziale. Buildozer richiede PNG per questi ingressi.

L'icona adattiva Android usa `icon-foreground.png` e `icon-background.png`.
Il primo livello ha sfondo trasparente e simbolo ridotto al 90% per rispettare
l'area sicura delle maschere del launcher; il secondo è interamente opaco.
I due SVG corrispondenti conservano anche questi livelli in forma vettoriale.

Per rigenerare i PNG con ImageMagick 7 e librsvg:

```sh
magick -background none artwork/icon.svg -resize 1024x1024 -strip PNG32:logo.png
magick -background none artwork/icon-foreground.svg -resize 512x512 -strip PNG32:artwork/icon-foreground.png
magick -background none artwork/icon-background.svg -resize 512x512 -strip PNG32:artwork/icon-background.png
```

Eseguire dalla radice del repository. `artwork/` è esclusa dai file Python
confezionati nell'app; Buildozer legge i livelli direttamente durante la build.
