from pathlib import Path
from django.test import SimpleTestCase
ROOT=Path(__file__).resolve().parents[1]
class GermanUiQualityTests(SimpleTestCase):
 def test_room_photo_ui_is_german_and_camera_gallery_are_separate(self):
  h=(ROOT/"templates/rebuild/room_planner.html").read_text(encoding="utf-8");j=(ROOT/"static/js/room-planner.js").read_text(encoding="utf-8")
  for x in ("Foto aufnehmen","Aus Galerie auswählen","data-rp-camera-files","data-rp-gallery-files"):self.assertIn(x,h)
  self.assertIn("selectedVisionFiles",j);self.assertIn("readJson(res,fallback)",j)
  for x in ("Create a room from photos","Take or select room photos","Detect and place space",">Cancel<"):self.assertNotIn(x,h)
 def test_german_runtime_guard_is_installed(self):
  h=(ROOT/"templates/rebuild/base.html").read_text(encoding="utf-8");self.assertIn("kayi-de-ui.js",h);self.assertNotIn("Work OS",h)
