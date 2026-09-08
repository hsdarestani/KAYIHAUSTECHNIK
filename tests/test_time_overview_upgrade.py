from pathlib import Path
from django.test import SimpleTestCase
R=Path(__file__).resolve().parents[1]
class T(SimpleTestCase):
 def test_contract(self):
  t=(R/'templates/rebuild/time_overview.html').read_text();v=(R/'erp/rebuild_views.py').read_text();u=(R/'erp/rebuild_urls.py').read_text();self.assertIn('Diese Woche',t);self.assertIn('Korrigieren',t);self.assertIn('ui_duration',t);self.assertIn('def time_entry_edit',v);self.assertIn('next-time-entry-edit',u)
