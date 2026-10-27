# Release PureNote

Il workflow **Build PureNote Release AAB** compila APK e AAB release per
`arm64-v8a` e `armeabi-v7a`, dopo test, lint e verifiche dell'interfaccia.
I pacchetti sono preparati per la firma locale: il runner non riceve keystore o
password di produzione. Nessuna pubblicazione su GitHub Releases o Play è automatica.

La versione resta **3.0.2**, con `android.numeric_version = 10219`, successivo
alla build 10218 provata su dispositivo. Questa revisione aggiorna l'icona;
il vettoriale e i livelli adattivi sono descritti in [artwork/README.md](artwork/README.md).
L'application ID rimane `bbnss.test.purenote` per preservare aggiornamenti e note.

## Compilazione

Avvia **Actions → Build PureNote Release AAB → Run workflow** dal ramo desiderato.
Il workflow parte anche sui tag `v*`. Scarica entrambi gli artifact:

- `purenote-release-apk-for-local-signing`
- `purenote-release-aab-for-local-signing`

Questi file non sono ancora ufficiali: vanno firmati e verificati prima di distribuirli.
I log diagnostici grezzi non vengono caricati come artifact.

La toolchain usa il commit p4a fissato in `buildozer.spec`. L'action condivisa
applica soltanto `venv --clear` all'ambiente pip temporaneo di ciascuna ABI:
senza pulizia, la ricreazione dello stesso venv per la seconda ABI può mescolare
file di versioni pip diverse e interrompere la compilazione. Le ricette native
compilate restano riutilizzabili dalla cache.

## Firma locale e certificati

Usa esclusivamente le chiavi esistenti e inserisci la password nel terminale.
Non inviare chiavi o password a GitHub e non generare una chiave sostitutiva.
Le APK debug di prova non costituiscono il rilascio ufficiale.

L'APK per GitHub deve avere lo stesso certificato di firma dell'app distribuita
da Play. La firma è stata confermata sia tramite le API Play sia sull'APK storico
`PureNote_F.apk`; l'impronta SHA-256 pubblica è:

```text
9D:61:85:C8:C5:CA:F9:B9:3A:1A:D1:5F:E2:52:E6:7A:08:DD:D7:D1:2B:DF:C0:CB:AD:66:80:BC:31:81:5A:D0
```

Confrontala con il certificato del keystore locale prima di firmare. Con
Play App Signing la chiave di upload può essere diversa: per l'AAB occorre
la chiave già accettata da Google Play. Se manca la chiave privata corrispondente
alla firma dell'app, un APK firmato con la sola chiave di upload non può sostituire
l'APK dello Store: bisogna usare un APK firmato fornito da Play.

Dopo zipalign e firma con gli strumenti Android, verifica l'APK:

```sh
python tests/verify_apk.py --release --expected-sha256 "$PLAY_APP_CERT_SHA256" --sdk "$ANDROID_HOME" percorso/PureNote.apk
```

Il controllo rifiuta firme diverse, APK debuggable e permessi Android; distingue
il certificato dell'app dall'eventuale source stamp di Google.

Verifica anche firma e integrità del bundle:

```sh
python tests/verify_signing.py --expected-sha256 "$PLAY_UPLOAD_CERT_SHA256" percorso/PureNote.aab
java -jar bundletool.jar validate --bundle=percorso/PureNote.aab
```

Keystore, credenziali, database e pacchetti compilati sono ignorati da Git e
esclusi dai sorgenti confezionati da Buildozer. Allega solo l'APK ufficiale alla
release GitHub; conserva l'AAB firmato per il successivo caricamento su Play.
Prima della produzione completa la prova dell'APK su dispositivo e i controlli
richiesti dalla Play Console.
