from pathlib import Path
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class ToolTimeQuotesExactParityTests(SimpleTestCase):
    def test_backend_supports_tooltime_filters_sort_and_offset_paging(self):
        views = (ROOT / "erp/tooltime_parity_views.py").read_text(encoding="utf-8")
        for contract in (
            'status == "pending"',
            'period == "30d"',
            'last_change_desc',
            'request.GET.get("amount") or 20',
            'request.GET.get("offset") or 0',
            'rows[offset: offset + amount]',
            '_tt_quote_relative_change',
            '_tt_quote_title',
        ):
            self.assertIn(contract, views)

    def test_visible_columns_match_tooltime_quote_index(self):
        template = (ROOT / "templates/rebuild/quotes.html").read_text(encoding="utf-8")
        for column in ("Angebotsdatum", "Nr.", "Status", "Angebotstitel", "Kunde", "Betrag", "Letzte Änderung"):
            self.assertIn(column, template)
        self.assertNotIn("<th>Projekt</th>", template)
        self.assertIn("{% if row.quote.number %}{{ row.quote.number }}{% else %}–{% endif %}", template)

    def test_tooltime_controls_are_real_not_placeholder_buttons(self):
        template = (ROOT / "templates/rebuild/quotes.html").read_text(encoding="utf-8")
        for contract in (
            'name="period"',
            'name="status"',
            'name="q"',
            'data-last-change-sort',
            'class="ttq-new-menu"',
            'data-page-size',
            'class="ttq-row-menu"',
            "next-quote-create",
            "next-projects",
            "next-quote-edit",
            "next-quote-to-invoice",
        ):
            self.assertIn(contract, template)
        self.assertIn("In Rechnung", template)
        self.assertIn("Sortieren", template)

    def test_pending_semantics_map_sent_quotes_to_pending(self):
        views = (ROOT / "erp/tooltime_parity_views.py").read_text(encoding="utf-8")
        self.assertIn('raw in {"sent", "pending"}', views)
        self.assertIn('qs.filter(status__in=("sent", "pending"))', views)

    def test_standard_page_size_is_twenty(self):
        template = (ROOT / "templates/rebuild/quotes.html").read_text(encoding="utf-8")
        self.assertIn('<option value="20"', template)
        self.assertIn('href="?{{ query_tail }}&offset={{ next_offset }}"', template)
