from pathlib import Path
from django.test import SimpleTestCase
R=Path(__file__).resolve().parents[1]
class T(SimpleTestCase):
 def test_contract(self):
  t=(R/'templates/rebuild/room_planner.html').read_text();j=(R/'static/js/room-planner.js').read_text();v=(R/'erp/room_planner_views.py').read_text();self.assertIn('sichtbaren Referenzobjekt',t);self.assertIn('Länge / Tiefe',t);self.assertIn('data-rp-known-length',t);self.assertIn('known_room_dimensions',j);self.assertIn('known_room_dimensions',v)
