from __future__ import annotations

import json

from rag import RagService
from sample_documents import SAMPLE_DOCUMENTS


EVALUATION_CASES = [
    ("How do I reset my company password and access my account?", "en", "kb-en-password-reset.md"),
    ("Come posso segnalare un'email di phishing?", "it", "kb-it-phishing-report.md"),
    ("VPN error code and MFA troubleshooting", "en", "kb-en-vpn-access.md"),
    ("What should a manager request for a new employee?", "en", "kb-en-employee-onboarding.md"),
    ("Come richiedo l'installazione di un software aziendale?", "it", "kb-it-software-request.md"),
    ("My old phone is gone and I cannot complete MFA", "en", "kb-en-multi-factor-authentication.md"),
    ("Restore an older version of a deleted file", "en", "kb-en-file-backup.md"),
    ("Priority when an essential service is down for several users", "en", "kb-en-ticket-priority.md"),
    ("La coda della stampante mostra un errore", "it", "kb-it-printer-support.md"),
    ("What should I do after losing my company laptop?", "en", "kb-en-remote-work.md"),
    ("The browser cannot keep my company identity provider session alive", "en", "kb-en-single-sign-on.md"),
    ("What information does a manager need to request access for a new starter?", "en", "kb-en-employee-onboarding.md"),
    ("How do I check disk encryption status on a company computer?", "en", "kb-en-device-encryption.md"),
    ("Forward a suspicious message to security without opening its links", "en", "kb-en-phishing-report.md"),
    ("Add an update to my existing issue so the assigned agent sees it", "en", "kb-en-ticket-updates.md"),
    ("Il client VPN non si connette: cosa controllo e quale codice comunico?", "it", "kb-it-vpn-access.md"),
    ("Ho cancellato un file: quali informazioni servono per ripristinarlo?", "it", "kb-it-file-backup.md"),
    ("La sincronizzazione della posta aziendale si è fermata sul dispositivo", "it", "kb-it-email-setup.md"),
    ("Chi deve richiedere la disattivazione degli accessi quando un collega lascia l'azienda?", "it", "kb-it-employee-offboarding.md"),
    ("Un servizio essenziale è fermo per molti utenti senza soluzione temporanea: quale priorità?", "it", "kb-it-ticket-priority.md"),
]


def evaluate(service: RagService) -> dict[str, object]:
    reciprocal_ranks: list[float] = []
    details: list[dict[str, object]] = []
    for query, language, expected_source in EVALUATION_CASES:
        hits = service.search(query, limit=5, language=language)
        rank = next(
            (index for index, hit in enumerate(hits, start=1) if hit.source == expected_source),
            None,
        )
        reciprocal_ranks.append(1 / rank if rank else 0.0)
        details.append(
            {
                "query": query,
                "expected_source": expected_source,
                "rank": rank,
                "returned_sources": [hit.source for hit in hits],
            }
        )
    return {
        "queries": len(EVALUATION_CASES),
        "recall_at_5": sum(1 for rank in reciprocal_ranks if rank > 0) / len(reciprocal_ranks),
        "mrr_at_5": sum(reciprocal_ranks) / len(reciprocal_ranks),
        "details": details,
    }


def main() -> None:
    service = RagService()
    service.initialize()
    service.seed_if_empty(SAMPLE_DOCUMENTS)
    print(json.dumps(evaluate(service), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
