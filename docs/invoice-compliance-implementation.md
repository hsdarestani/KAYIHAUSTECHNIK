# German invoice compliance implementation

This implementation uses the provided technical specification as the engineering baseline for German invoices and E-Rechnungen. It does not replace external tax, privacy, GoBD or security acceptance before the product is marketed as legally compliant.

## Core controls

- structured invoice core and Decimal-based backend totals
- statutory invoice-data validation before finalization
- invoice number allocation only at finalization with tenant/year sequence locking
- immutable finalized snapshot with SHA-256 and retention metadata
- append-only invoice audit events
- cancellation/correction relationships instead of silent edits
- PDF archive artifact generated from the frozen snapshot
- structured XRechnung UBL output from the same snapshot
- explicit external-validator state: XML is never marked VALID merely because it can be serialized
- configurable validator/schema/generator version metadata
- customer invoice profile for B2B/B2G fields including invoice email, Leitweg-ID and business references
- original PDF/XML document preservation and retention metadata
- finalized invoice edit guard
- dedicated finalize action in the invoice UI

## XRechnung validation

A real KoSIT validator can be connected with `XRECHNUNG_VALIDATOR_CMD`. If no real validator is available, the result stays `NOT_VALIDATED`; the application must not claim a valid XRechnung merely because XML was produced.

## ZUGFeRD

ZUGFeRD requires a compliant PDF/A-3 hybrid renderer with embedded structured XML. Until `ZUGFERD_RENDERER_CMD` is configured and the resulting artifact is validated, the system must not label an ordinary PDF as ZUGFeRD.

## External acceptance

Before public claims such as “GoBD-konform”, “DSGVO-konform” or “E-Rechnung-konform”, obtain external acceptance covering tax/invoice logic, retention/correction procedures, privacy/TOMs/subprocessors/hosting, and IT security/backup/penetration testing.
