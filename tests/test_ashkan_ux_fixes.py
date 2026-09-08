from pathlib import Path

from django.test import SimpleTestCase

from erp.forms import RoomMeasurementForm


class AshkanUxRegressionTests(SimpleTestCase):
    def test_room_measurement_labels_are_german(self):
        form = RoomMeasurementForm()
        self.assertEqual(form.fields["length_m"].label, "Länge (m)")
        self.assertEqual(form.fields["width_m"].label, "Breite (m)")
        self.assertEqual(form.fields["height_m"].label, "Höhe (m)")
        self.assertEqual(form.fields["deductions_area_m2"].label, "Abzugsfläche (m²)")
        self.assertEqual(form.fields["waste_percent"].label, "Verschnitt (%)")
        self.assertEqual(form.fields["reference_type"].label, "Referenzobjekt")

    def test_generic_cancel_uses_safe_back_navigation(self):
        template = Path("templates/erp/form.html").read_text(encoding="utf-8")
        self.assertIn("data-smart-back", template)
        self.assertNotIn("onclick=\"history.back()\"", template)

    def test_configurator_has_front_wall_and_drag_hint(self):
        template = Path("templates/erp/configurator.html").read_text(encoding="utf-8")
        self.assertIn('data-model-openings="front"', template)
        self.assertIn("Direkt im Modell ziehen", template)

    def test_room_openings_are_drag_enabled_and_german(self):
        javascript = Path("static/js/app.js").read_text(encoding="utf-8")
        self.assertIn("attachOpeningDrag", javascript)
        self.assertIn("verschieben", javascript)
        self.assertIn("setPointerCapture", javascript)
        self.assertNotIn("node.title = `${opening.kind", javascript)
