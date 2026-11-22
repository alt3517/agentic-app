from __future__ import annotations

_articles = [
    (
        "password-reset",
        "Account",
        "Reimpostare la password",
        "Resetting a password",
        "Per reimpostare la password aziendale, apri il portale account e seleziona «Password dimenticata». Verifica l'identità con il secondo fattore e scegli una password nuova che non sia stata usata in precedenza. Se il secondo fattore non è disponibile o l'account risulta bloccato, apri un ticket Account e indica il tuo nome utente; non inviare la password o i codici di verifica nel ticket.",
        "To reset your company password, open the account portal and select “Forgot password”. Verify your identity with the second factor and choose a new password that has not been used before. If the second factor is unavailable or the account is locked, open an Account ticket and include your username; never include a password or verification code in a ticket.",
    ),
    (
        "multi-factor-authentication",
        "Account",
        "Configurare l'autenticazione a più fattori",
        "Setting up multi-factor authentication",
        "Registra almeno un metodo MFA approvato nel portale account, preferibilmente l'app di autenticazione gestita dall'azienda. Conserva i codici di recupero in un luogo sicuro e non condividerli con il supporto. In caso di sostituzione del telefono, registra prima il nuovo dispositivo; se non puoi accedere al vecchio metodo, richiedi una verifica d'identità al service desk.",
        "Register at least one approved MFA method in the account portal, preferably the company-managed authenticator app. Store recovery codes securely and never share them with support. When replacing a phone, register the new device first; if the old method is unavailable, request an identity check from the service desk.",
    ),
    (
        "vpn-access",
        "Network",
        "Risoluzione dei problemi VPN",
        "Troubleshooting VPN access",
        "Prima di aprire la VPN, verifica che il dispositivo sia connesso a Internet e che data e ora siano corrette. Accedi con il tuo account aziendale e completa la richiesta MFA. Se la connessione fallisce, riavvia il client una sola volta e annota il codice d'errore. Apri un ticket Network con il codice, il sistema operativo e l'orario del tentativo; non allegare credenziali.",
        "Before connecting to the VPN, confirm that the device has Internet access and the correct date and time. Sign in with your company account and complete MFA. If the connection fails, restart the client once and record the error code. Open a Network ticket with the code, operating system, and attempt time; do not attach credentials.",
    ),
    (
        "phishing-report",
        "Security",
        "Segnalare un'email sospetta",
        "Reporting a suspicious email",
        "Non aprire link o allegati di un messaggio sospetto e non rispondere al mittente. Usa il pulsante aziendale «Segnala phishing» per inoltrare il messaggio completo al team di sicurezza, quindi elimina il messaggio se richiesto. Se hai già inserito la password, cambiala dal portale ufficiale e contatta immediatamente il service desk indicando l'ora e il dispositivo coinvolto.",
        "Do not open links or attachments in a suspicious message and do not reply to the sender. Use the company “Report phishing” button to forward the complete message to Security, then delete it if prompted. If you already entered your password, change it through the official portal and contact the service desk immediately with the time and device involved.",
    ),
    (
        "ticket-priority",
        "Service Desk",
        "Scegliere la priorità di un ticket",
        "Choosing a ticket priority",
        "La priorità riflette impatto e urgenza, non il ruolo della persona che apre il ticket. Usa Alta quando un servizio essenziale è indisponibile per più utenti e non esiste una soluzione temporanea; usa Media per un problema circoscritto con una soluzione temporanea; usa Bassa per richieste standard o informazioni. Descrivi utenti coinvolti, servizio, orario d'inizio e impatto operativo.",
        "Priority reflects impact and urgency, not the seniority of the person opening the ticket. Use High when an essential service is unavailable to multiple users with no workaround; use Medium for a limited issue with a workaround; use Low for standard requests or information. Describe affected users, service, start time, and business impact.",
    ),
    (
        "ticket-updates",
        "Service Desk",
        "Aggiornare un ticket esistente",
        "Updating an existing ticket",
        "Apri «I miei ticket», seleziona il ticket interessato e aggiungi un commento con i nuovi dettagli. Mantieni la conversazione nello stesso ticket per conservare la cronologia e avvisare l'assegnatario. Non inserire password, token o dati di pagamento. Se il ticket è chiuso e il problema si è ripresentato, crea un nuovo ticket e cita il numero precedente.",
        "Open “My tickets”, select the relevant ticket, and add a comment with the new details. Keep updates in the same ticket so the history and assigned agent remain together. Do not include passwords, tokens, or payment data. If a closed issue has returned, create a new ticket and reference the earlier ticket number.",
    ),
    (
        "single-sign-on",
        "Account",
        "Problemi di accesso SSO",
        "Troubleshooting single sign-on",
        "Verifica di usare il nome utente aziendale completo e che il browser supporti i cookie necessari al provider di identità. Chiudi le sessioni aziendali precedenti e riprova dal collegamento ufficiale dell'applicazione. Se il problema persiste, invia al service desk il nome dell'applicazione, il messaggio d'errore e l'orario; non condividere schermate che mostrano codici o dati personali non necessari.",
        "Confirm that you are using your full company username and that the browser allows the identity provider's required cookies. Close previous company sessions and retry from the application's official link. If the issue continues, send the application name, error message, and time to the service desk; do not share screenshots containing codes or unnecessary personal data.",
    ),
    (
        "email-setup",
        "Workplace",
        "Configurare la posta aziendale",
        "Setting up company email",
        "Configura la posta usando l'applicazione approvata dall'azienda e completa l'accesso tramite SSO e MFA. Non inserire la password aziendale in app di terze parti o in configurazioni manuali non approvate. Se la sincronizzazione si interrompe, controlla prima lo stato del servizio e la connessione di rete; poi apri un ticket Workplace indicando dispositivo, versione dell'app e ora dell'ultimo aggiornamento riuscito.",
        "Set up email with the company-approved application and complete sign-in through SSO and MFA. Do not enter your company password into third-party apps or unapproved manual configurations. If synchronization stops, first check service status and network connectivity; then open a Workplace ticket with the device, app version, and time of the last successful sync.",
    ),
    (
        "device-encryption",
        "Security",
        "Verificare la cifratura del dispositivo",
        "Checking device encryption",
        "I computer aziendali devono avere attiva la cifratura del disco e la gestione endpoint approvata. Verifica lo stato nell'applicazione di sicurezza aziendale; non disattivare la cifratura per risolvere un problema di prestazioni. Se il dispositivo risulta non conforme, collegalo alla rete aziendale e apri un ticket Security con il nome del dispositivo e lo stato mostrato, senza inviare chiavi di ripristino.",
        "Company computers must have disk encryption and approved endpoint management enabled. Check status in the company security application; do not disable encryption to address performance issues. If the device is non-compliant, connect it to the company network and open a Security ticket with the device name and displayed status; never send recovery keys.",
    ),
    (
        "file-backup",
        "Workplace",
        "Ripristinare un file da backup",
        "Restoring a file from backup",
        "Per ripristinare un file, individua il percorso originale, il nome del file e la data in cui era disponibile. Usa prima la funzione di version history dello spazio aziendale, se prevista. Se serve l'intervento del supporto, apri un ticket Workplace con percorso e data approssimativa; evita di allegare copie di dati riservati. Il ripristino è soggetto alle regole di conservazione aziendali.",
        "To restore a file, identify its original path, file name, and the date it was last available. First use the version history in the company storage service, if available. If support is needed, open a Workplace ticket with the path and approximate date; avoid attaching confidential copies. Restores follow company retention rules.",
    ),
    (
        "software-request",
        "Requests",
        "Richiedere un software",
        "Requesting software",
        "Invia una richiesta Software indicando il nome e la versione del prodotto, il motivo aziendale e il dispositivo interessato. Il team verifica licenza, compatibilità e requisiti di sicurezza prima dell'installazione. Non scaricare software da siti non ufficiali e non usare account personali per aggirare i controlli aziendali. Le richieste urgenti devono includere la scadenza e l'impatto operativo.",
        "Submit a Software request with the product name and version, business reason, and target device. The team checks licensing, compatibility, and security requirements before installation. Do not download software from unofficial sites or use personal accounts to bypass company controls. Urgent requests should include the deadline and business impact.",
    ),
    (
        "employee-onboarding",
        "People Operations",
        "Preparare l'accesso di un nuovo collega",
        "Preparing access for a new employee",
        "Il responsabile avvia la richiesta di onboarding attraverso il flusso approvato, indicando data d'inizio, ruolo, sede e applicazioni necessarie. Gli accessi seguono il principio del privilegio minimo e richiedono l'approvazione dei responsabili dei sistemi. Non inviare password temporanee via email; il nuovo collega deve completare la procedura di attivazione e MFA personalmente.",
        "The manager starts onboarding through the approved workflow and provides the start date, role, location, and required applications. Access follows least privilege and requires approval from the relevant system owners. Do not email temporary passwords; the new employee must complete activation and MFA personally.",
    ),
    (
        "employee-offboarding",
        "People Operations",
        "Segnalare la cessazione di un account",
        "Reporting an employee offboarding",
        "Il responsabile o People Operations invia la richiesta di offboarding con la data effettiva e l'elenco delle risorse da trasferire. Il team disabilita gli accessi secondo il processo aziendale e preserva i dati soggetti a obblighi di conservazione. Non chiedere di condividere credenziali o di accedere all'account di un'altra persona; le eccezioni richiedono autorizzazione formale.",
        "The manager or People Operations submits an offboarding request with the effective date and resources to transfer. The team disables access under the company process and retains data subject to retention requirements. Do not ask for another person's credentials or access their account; exceptions require formal authorization.",
    ),
    (
        "remote-work",
        "Network",
        "Lavorare in sicurezza da remoto",
        "Working securely from home",
        "Quando lavori da remoto, usa il dispositivo gestito dall'azienda, una rete protetta da password e la VPN per i servizi che la richiedono. Evita reti Wi-Fi pubbliche per trattare informazioni riservate e blocca lo schermo quando ti allontani. Segnala subito lo smarrimento del dispositivo al service desk e al team Security, specificando quando e dove è stato visto l'ultima volta.",
        "When working remotely, use a company-managed device, a password-protected network, and the VPN for services that require it. Avoid public Wi-Fi for confidential work and lock your screen when away. Report a lost device immediately to the service desk and Security, including when and where it was last seen.",
    ),
    (
        "printer-support",
        "Workplace",
        "Risoluzione dei problemi della stampante",
        "Troubleshooting a printer",
        "Controlla che la stampante sia accesa, collegata alla rete aziendale e che la coda non contenga un errore evidente. Verifica di aver selezionato la stampante corretta e che il documento non contenga pagine riservate destinate ad altri utenti. Se il problema persiste, apri un ticket Workplace indicando sede, nome della stampante, messaggio d'errore e ora del tentativo.",
        "Check that the printer is powered on, connected to the company network, and that its queue has no obvious error. Confirm that you selected the correct printer and that the document does not contain confidential pages intended for someone else. If the issue continues, open a Workplace ticket with the location, printer name, error message, and attempt time.",
    ),
]

SAMPLE_DOCUMENTS = [
    {
        "source": f"kb-{language}-{slug}.md",
        "title": title,
        "category": category,
        "language": language,
        "content": content,
    }
    for slug, category, italian_title, english_title, italian_content, english_content in _articles
    for language, title, content in (
        ("it", italian_title, italian_content),
        ("en", english_title, english_content),
    )
]
