from pathlib import Path

from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class ToolTimeProjectsExactParityContract(SimpleTestCase):
    def test_project_index_has_reference_structure(self):
        template = (ROOT / "templates/rebuild/projects.html").read_text(encoding="utf-8")
        for token in (
            "data-tooltime-projects-exact",
            "Alle Projekte",
            "Neues Projekt",
            "data-project-modal",
            "Projekttitel",
            "Eingangsdatum",
            "Projektbeschreibung",
            "Kunde auswählen",
            "data-col=\"title\"",
            "data-col=\"no\"",
            "data-col=\"status\"",
            "data-col=\"address\"",
            "data-col=\"customer\"",
            "data-col=\"changed\"",
            "Letzte Änderung",
            "data-column-toggle",
            "Projektaktionen",
            "data-page-size",
        ):
            self.assertIn(token, template)

    def test_project_view_uses_tooltime_query_contract_and_real_create(self):
        source = (ROOT / "erp/rebuild_projects.py").read_text(encoding="utf-8")
        for token in (
            "searchText",
            "sortType",
            "sortOrder",
            "LAST_CHANGED",
            "ASCENDING",
            "DESCENDING",
            "amount",
            "offset",
            "create_project",
            "_tt_project_next_number",
            'f"{timezone.localdate().year % 100:02d}-"',
            "m.Project.objects.create",
            "updated_at",
            "prefetch_related(\"quotes\")",
        ):
            self.assertIn(token, source)

    def test_project_assets_have_modal_row_and_column_behaviour(self):
        js = (ROOT / "static/js/tooltime-projects-exact.js").read_text(encoding="utf-8")
        css = (ROOT / "static/css/tooltime-projects-exact.css").read_text(encoding="utf-8")
        for token in ("data-project-modal-open", "data-project-row", "localStorage", "data-page-size"):
            self.assertIn(token, js)
        for token in (".ttp-modal", ".ttp-row-menu", ".ttp-status", ".ttp-pagination"):
            self.assertIn(token, css)
