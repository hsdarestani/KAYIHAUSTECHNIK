from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
app = (ROOT / "native/www/app.js").read_text(encoding="utf-8")
for marker in (
    "cachedOperationalData", "navigator.onLine", "Offline-Modus",
    "notifyUpcomingAppointments", "connectionLabel", "sync-chip",
    "Offline: Änderungen sind erst nach Wiederherstellung der Verbindung möglich.",
):
    if marker not in app:
        raise RuntimeError(f"Native Full App phase 5 marker missing: {marker}")

compliance_path = ROOT / "docs/store-compliance.md"
compliance = compliance_path.read_text(encoding="utf-8")
compliance = compliance.replace(
    "- Bundle identifier: `sbs.smarbiz.kayi`",
    "- Bundle identifier (iOS and Android): `de.kayihaustechnik.app`",
)
compliance = compliance.replace(
    "- WebView is supplemented by camera, files, geolocation, offline queue and push integration to avoid a thin-wrapper product.",
    "- The native shell includes RoomPlan/ARCore scanning, camera/files, connectivity-aware cached read access, scan upload queue, role-aware operational workflows and in-app appointment reminders. Financial writes are deliberately blocked offline to prevent duplicate documents.",
)
compliance_path.write_text(compliance, encoding="utf-8")

(ROOT / "tests/test_native_full_app_phase5.py").write_text('''from pathlib import Path
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class NativeFullAppPhase5Tests(SimpleTestCase):
    def test_offline_cache_is_per_user_and_excludes_finance(self):
        app = (ROOT / "native/www/app.js").read_text(encoding="utf-8")
        self.assertIn("ab.cachedData.${state.user?.id", app)
        self.assertIn("customers:[],quotes:[],invoices:[],employees:[],expenses:[]", app)
        self.assertIn("localStorage.removeItem(oldCache)", app)

    def test_offline_writes_are_blocked_and_reconnect_syncs(self):
        app = (ROOT / "native/www/app.js").read_text(encoding="utf-8")
        self.assertIn("if (!navigator.onLine && !['GET','HEAD'].includes", app)
        self.assertIn("window.addEventListener('online'", app)
        self.assertIn("if(state.user)bootstrap()", app)

    def test_appointment_reminders_are_deduplicated(self):
        app = (ROOT / "native/www/app.js").read_text(encoding="utf-8")
        self.assertIn("notifyUpcomingAppointments", app)
        self.assertIn("ab.reminded.${event.id}", app)
        self.assertIn("delta<=2*60*60*1000", app)

    def test_store_identifiers_are_consistent(self):
        compliance = (ROOT / "docs/store-compliance.md").read_text(encoding="utf-8")
        config = (ROOT / "native/capacitor.config.ts").read_text(encoding="utf-8")
        self.assertIn("de.kayihaustechnik.app", compliance)
        self.assertIn("de.kayihaustechnik.app", config)
''', encoding="utf-8")

print("Installed Native Full App phase 5: safe offline read cache, reconnect sync and reminders.")
