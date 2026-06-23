# Pubblicare PureNote (Release AAB firmato)

Il workflow `.github/workflows/build-release.yml` produce l'**Android App Bundle
(.aab)** firmato da caricare sul Play Store. Si avvia manualmente
(*Actions → Build PureNote Release AAB → Run workflow*) o pushando un tag
versione (`git tag v2.1 && git push origin v2.1`).

## 1. Genera il keystore (una sola volta)

Crea la chiave di firma in locale e **conservala al sicuro** (se la perdi non
puoi più aggiornare l'app sul Play Store):

```
keytool -genkey -v \
  -keystore purenote-release.keystore \
  -alias purenote \
  -keyalg RSA -keysize 2048 -validity 10000
```

Ti chiederà una password (store) e i tuoi dati. Annota:
- password del keystore
- alias (`purenote`)
- password dell'alias (può coincidere con quella del keystore)

## 2. Imposta i secret su GitHub

Converti il keystore in base64:

```
base64 -i purenote-release.keystore | pbcopy   # macOS, copia negli appunti
```

Poi su GitHub: *Settings → Secrets and variables → Actions → New repository
secret* e crea:

| Secret | Valore |
|---|---|
| `ANDROID_KEYSTORE_B64` | il base64 del keystore (passo sopra) |
| `ANDROID_KEYSTORE_PASSWORD` | password del keystore |
| `ANDROID_KEY_ALIAS` | `purenote` |
| `ANDROID_KEY_PASSWORD` | password dell'alias |

> Senza questi secret il workflow gira lo stesso ma produce un AAB **non
> firmato**, utile solo a validare la build (non caricabile sul Play Store).

## 3. Avvia la build e scarica l'AAB

Lancia il workflow; al termine scarica l'artifact `purenote-release-aab`
(contiene `bin/*.aab`) e caricalo nella Play Console.

## Note
- Il release builda **entrambe le architetture** (`arm64-v8a` + `armeabi-v7a`);
  il Play Store serve poi la ABI giusta a ciascun dispositivo. La build di
  debug resta solo `arm64-v8a` per velocità.
- Incrementa `version` in `buildozer.spec` ad ogni release (la Play Console
  rifiuta due upload con lo stesso version code).
