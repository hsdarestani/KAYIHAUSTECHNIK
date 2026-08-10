# KAYI Haustechnik — Store Privacy Declarations

Stand: 10.08.2026. Diese Datei ist die Ausfüllvorlage für App Store Connect und Google Play Console. Sie muss bei jeder neuen SDK-/Funktionsintegration erneut geprüft werden.

## Grundsätze
- Werbung: **Nein**
- Werbe-Tracking / Cross-App-Tracking: **Nein**
- Verkauf personenbezogener Daten: **Nein**
- In-App-Käufe: **Nein**
- Datenübertragung: HTTPS; Android-Cleartext ist deaktiviert.
- Kontolöschung: in KAYI sowie öffentlich unter `https://kayi.smarbiz.sbs/konto-loeschen/`.
- KI: nutzerbezogene Texte oder ausdrücklich ausgewählte Raumfotos werden erst nach gesonderter, widerrufbarer Einwilligung an OpenAI übertragen.
- Gerätefotos: kein pauschaler Zugriff auf die komplette Medienbibliothek; Auswahl erfolgt nutzerinitiiert über Kamera/Dateiauswahl.

## Apple App Privacy
### Data Used to Track You
**None / Nein**

### Data Linked to You — Purpose: App Functionality
Konservativ angeben, wenn die entsprechende Betriebsfunktion genutzt wird:
- Contact Info → Name
- Contact Info → Email Address
- Contact Info → Phone Number
- Contact Info → Physical Address
- Financial Info → Payment Info
- Financial Info → Other Financial Info
- User Content → Emails or Text Messages
- User Content → Photos or Videos
- User Content → Audio Data
- User Content → Other User Content
- Identifiers → User ID
- Usage Data → Product Interaction
- Other Data → Environment Scanning

Für diese Kategorien:
- Linked to the User: **Yes**
- Used for Tracking: **No**
- Purpose: **App Functionality**

### Location
Aktuell **nicht deklarieren**, solange die native Store-Build-Konfiguration keine Standortberechtigung anfordert und kein verifizierter nativer Standortfluss aktiv ist. Falls später mobile Standorterfassung aktiviert wird, Privacy Manifest, App Privacy und beide Plattform-Permissions gemeinsam aktualisieren.

### Third-party AI
Bei Apple im Review-Hinweis und in der Datenschutzerklärung offenlegen: Nur Inhalte, die der Nutzer aktiv an eine KI-Funktion übergibt, können an OpenAI übertragen werden; vorher wird eine ausdrückliche Einwilligung verlangt und diese kann widerrufen werden.

## Google Play Data Safety
### Does your app collect or share any of the required user data types?
**Yes**

### Is all of the user data collected by your app encrypted in transit?
**Yes**

### Do you provide a way for users to request that their data is deleted?
**Yes**
- In-app: Einstellungen → Datenschutz & Konto → Konto und Daten löschen
- Web: `https://kayi.smarbiz.sbs/konto-loeschen/`

### Account creation
KAYI benötigt einen betrieblichen Zugang. Wenn Play Console fragt, ob Nutzer ein Konto innerhalb der App erstellen können: **No**, sofern die Release-Version keine Self-Service-Registrierung anbietet. Bestehende Nutzer melden sich mit einem vom Betrieb bereitgestellten Zugang an.

### Data types — Collected for App Functionality
Konservativ markieren, soweit die jeweilige Funktion vom Betrieb genutzt wird:
- Personal info: Name, Email address, User IDs, Address, Phone number, Other info
- Financial info: User payment info, Purchase history / financial business records where applicable, Other financial info
- Messages: Emails, Other in-app messages where applicable
- Photos and videos: Photos, Videos
- Audio: Voice or sound recordings
- Files and docs: Files and docs
- App activity: App interactions
- Other: Environment/room scan data and business/project content where the form permits an "Other" category

### Shared data
Für ausdrücklich KI-verarbeitete Nutzerdaten konservativ als **shared** angeben, falls Play Console die OpenAI-Verarbeitung nicht unter eine anwendbare Service-Provider-Ausnahme einordnen lässt:
- Text / Other user content
- Photos selected for room analysis
Purpose: App functionality. Transfer occurs only after explicit user consent.

### Data not used for advertising
Für alle oben genannten Kategorien:
- Advertising or marketing: **No**
- Fraud prevention/security may apply only to technical security metadata where actually collected.

## Permissions / sensitive access
### Android
- INTERNET — erforderlich für KAYI-Serverzugriff.
- RECORD_AUDIO — nur für aktiv gestartete Sprachaufnahme; Mikrofon ist als nicht zwingend erforderliches Hardware-Feature deklariert.
- Keine READ_MEDIA_IMAGES, READ_EXTERNAL_STORAGE oder MANAGE_EXTERNAL_STORAGE Berechtigung.
- Kamera kann durch die native ARCore-Komponente als Library-Berechtigung in das finale Manifest eingebracht werden; Store-Release-CI prüft das zusammengeführte Manifest.

### iOS
- NSCameraUsageDescription — Kamera nur bei aktiv gestarteter Foto-/Raumscan-Funktion.
- NSMicrophoneUsageDescription — Mikrofon nur bei aktiv gestarteter Sprachaufnahme.
- ITSAppUsesNonExemptEncryption = false.
- App-level PrivacyInfo.xcprivacy ist Bestandteil des Release-Archivs.
