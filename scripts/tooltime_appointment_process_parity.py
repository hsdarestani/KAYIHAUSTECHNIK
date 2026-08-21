from __future__ import annotations

import tooltime_appointment_process_models as appointment_models
import tooltime_appointment_process_views as appointment_views
import tooltime_appointment_process_preflight as appointment_preflight
import tooltime_appointment_process_ui as appointment_ui
import tooltime_appointment_process_finalize as appointment_finalize
import tooltime_appointment_process_tests as appointment_tests

MARKER = "A+BAU TOOLTIME APPOINTMENT PROCESS PARITY 2026-08-21"


def run(module) -> None:
    appointment_models.run(module)
    appointment_views.run(module)
    appointment_preflight.run(module)
    appointment_ui.run(module)
    appointment_finalize.run(module)
    appointment_tests.run(module)
    print(
        f"{MARKER}: Termin-Leistungsgruppen und Positionen sind persistent, Preise bleiben im Termin verborgen, "
        "angenommene Angebote können vollständig in Termine übernommen werden, Monteure können Leistungen vor Ort "
        "ergänzen und dokumentierte Termine können ihre Leistungen in Angebot oder Rechnung übertragen."
    )
