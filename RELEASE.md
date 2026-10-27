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

Configura anche la variabile del repository `ANDROID_UPLOAD_CERT_SHA256` con
l'impronta SHA-256 del certificato della **chiave di caricamento** già associata
a questa app in Play Console → Integrità dell'app. Non ricavarla soltanto dalla
chiave locale: deve essere confrontata con il dato indipendente della Console.
Il workflow confronta il certificato prima della build e sul bundle finale;
se manca la chiave, manca l'impronta o il confronto fallisce, interrompe il rilascio.

Le APK di prova 3.0.2 hanno una firma debug, che non va riutilizzata per il rilascio.
Per l'APK ufficiale su GitHub occorre verificare il certificato di **firma dell'app**
già distribuita. Con Play App Signing questo può differire dalla chiave di upload:
un APK firmato soltanto con la chiave di upload non aggiorna un'installazione
firmata da Google. In tal caso si usa un APK firmato fornito da Play, oppure la
chiave originale di firma dell'app se ancora disponibile. Non generare nuove chiavi.

Verifica l'APK destinato a GitHub prima di pubblicarlo, usando l'impronta
del certificato di **firma dell'app** confermata su Play:

```sh
python tests/verify_apk.py --release --expected-sha256 "$PLAY_APP_CERT_SHA256" --sdk "$ANDROID_HOME" percorso/PureNote.apk
```

Il controllo rifiuta firme diverse, APK debuggable e permessi Android.
Keystore, credenziali, database e file di release restano ignorati da Git;
l'APK ufficiale va allegato alla release GitHub, non aggiunto al codice.
L'AAB rimane un artifact della build, da scaricare per il caricamento successivo.

## Compilazione

Dopo il push autorizzato, apri **Actions → Build PureNote Release AAB → Run workflow**.
In alternativa, il workflow parte con un tag `v*`. L’artifact si chiama
`purenote-release-aab-signed` solo dopo la verifica della firma. Non viene prodotto
un bundle unsigned in sostituzione di quello ufficiale.

La prima build della toolchain aggiornata va ancora convalidata su GitHub.
Prima di pubblicare, prova l’APK su Android: tastiera e barre di sistema,
background/riapertura, aggiornamento con dati esistenti, selettore file,
condivisione, backup e ripristino. Verifica poi i controlli della Play Console.

Ogni nuovo upload richiede un `android.numeric_version` strettamente maggiore
in `buildozer.spec`. Questa revisione usa `version = 3.0.2` e
`android.numeric_version = 10219`, successivo alla 3.0.2 provata (10218).
Questa revisione mantiene il comportamento della 3.0.2 e aggiorna l'icona;
il sorgente vettoriale e i livelli adattivi sono documentati in
[artwork/README.md](artwork/README.md).

## Compilazione locale facoltativa

Con le dipendenze di sistema elencate nell’action Android condivisa:

```bash
python3.11 -m venv .build-venv
.build-venv/bin/python -m pip install -r requirements-build.txt
export PIP_CONSTRAINT="$PWD/constraints-android.txt"
.build-venv/bin/buildozer -v android debug
.build-venv/bin/buildozer -v android release
```

Il release locale richiede le variabili `P4A_RELEASE_KEYSTORE`,
`P4A_RELEASE_KEYSTORE_PASSWD`, `P4A_RELEASE_KEYALIAS` e `P4A_RELEASE_KEYALIAS_PASSWD`
per firmare il bundle. Le architetture locali sono quelle di `buildozer.spec`;
il workflow GitHub seleziona entrambe le ABI per il release.
