from pathlib import Path

from django.test import SimpleTestCase

from erp.rebuild_views import AppointmentForm, QuoteForm


class KayiUiRegressionTests(SimpleTestCase):
    def test_checkboxes_are_compact_and_german(self):
        field = AppointmentForm().fields["all_day"]
        self.assertEqual(field.label, "Ganztägig")
        classes = field.widget.attrs.get("class", "").split()
        self.assertIn("nx-checkbox-input", classes)
        self.assertNotIn("next-control", classes)

    def test_quote_labels_are_german(self):
        form = QuoteForm()
        self.assertEqual(form.fields["valid_until"].label, "Gültig bis")
        self.assertEqual(form.fields["intro_text"].label, "Einleitungstext")
        self.assertEqual(form.fields["discount_percent"].label, "Rabatt (%)")

    def test_project_customer_search_is_rendered(self):
        text = Path("templates/rebuild/project_form.html").read_text(encoding="utf-8")
        self.assertIn("data-select-search", text)
        self.assertIn("Kunde suchen", text)

    def test_document_editor_and_project_download_contract(self):
        editor = Path("templates/rebuild/document_editor.html").read_text(encoding="utf-8")
        detail = Path("templates/rebuild/project_detail.html").read_text(encoding="utf-8")
        self.assertIn("data-add-item", editor)
        self.assertIn("data-row-href", detail)
        self.assertIn("Herunterladen", detail)
