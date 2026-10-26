# AAB di PureNote

Il workflow **Build PureNote Release AAB** prepara il bundle per il Play Store.
Esegue gli stessi controlli dell’APK e compila per `arm64-v8a` e `armeabi-v7a`.
Non pubblica automaticamente il bundle.

## Firma

Per aggiornare l’app già pubblicata, usa il keystore di upload esistente e mantieni
l’application ID `bbnss.test.purenote`. Non sostituire la chiave con una nuova
senza aver completato l’eventuale procedura di cambio chiave nella Play Console.

Configura questi repository secret in **Settings → Secrets and variables → Actions**:

| Secret | Contenuto |
| --- | --- |
| `ANDROID_KEYSTORE_B64` | File keystore codificato in base64 |
| `ANDROID_KEYSTORE_PASSWORD` | Password del keystore |
| `ANDROID_KEY_ALIAS` | Alias della chiave |
| `ANDROID_KEY_PASSWORD` | Password della chiave |

Su Linux puoi produrre la codifica con `base64 -w 0 percorso/chiave.keystore`.
Conserva il file originale e le credenziali fuori dal repository.
Il workflow decodifica la chiave in una cartella temporanea del runner e la rimuove
anche quando la build fallisce.

## Compilazione

Dopo il push autorizzato, apri **Actions → Build PureNote Release AAB → Run workflow**.
In alternativa, il workflow parte con un tag `v*`. L’artifact si chiama
`purenote-release-aab-signed` se il keystore è configurato; senza chiave viene
prodotto `purenote-release-aab-unsigned`, utile per verificare la compilazione
ma non caricabile sul Play Store.

La prima build della toolchain aggiornata va ancora convalidata su GitHub.
Prima di pubblicare, prova l’APK su Android: tastiera e barre di sistema,
background/riapertura, aggiornamento con dati esistenti, selettore file,
condivisione, backup e ripristino. Verifica poi i controlli della Play Console.

Ogni nuovo upload richiede un `android.numeric_version` strettamente maggiore
in `buildozer.spec`. Questa revisione usa `version = 3.0` e
`android.numeric_version = 10216`, successivo al precedente 10215.

## Compilazione locale facoltativa

Con le dipendenze di sistema elencate nell’action Android condivisa:

```bash
python3.11 -m venv .build-venv
.build-venv/bin/python -m pip install -r requirements-build.txt
.build-venv/bin/buildozer -v android debug
.build-venv/bin/buildozer -v android release
```

Il release locale richiede le variabili `P4A_RELEASE_KEYSTORE`,
`P4A_RELEASE_KEYSTORE_PASSWD`, `P4A_RELEASE_KEYALIAS` e `P4A_RELEASE_KEYALIAS_PASSWD`
per firmare il bundle. Le architetture locali sono quelle di `buildozer.spec`;
il workflow GitHub seleziona entrambe le ABI per il release.
