from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from erp.ai_scope_catalog import _best_bo_row, _candidate_score


class CatalogContextHardeningTests(SimpleTestCase):
    def row(self, description, unit="m²", code="X"):
        return SimpleNamespace(description=description, unit=unit, code=code, pk=code)

    def test_generic_wall_paint_is_not_matched_to_keller_only_position(self):
        scope = {
            "key": "paint.wall.coat",
            "label": "Dispersionsfarbanstrich Wände",
            "unit": "m²",
            "catalog_terms": ["Dispersionsfarbe Wände", "Wandanstrich Dispersionsfarbe", "Wände streichen"],
        }
        candidate = self.row(
            "Massivwände und Decken weiß streichen in Kellerräumen beschichten",
            code="KELLER-MAL-01",
        )
        self.assertLess(_candidate_score(candidate, scope), 0)

    def test_wrong_trade_position_is_rejected_even_when_generic_verb_matches(self):
        scope = {
            "key": "bath.walltile.install",
            "label": "Wandfliesen herstellen",
            "unit": "m²",
            "catalog_terms": ["Wandfliesen herstellen", "Wandfliesen verlegen"],
        }
        candidate = self.row("Brandschutz Dämmwolle ums Fallrohr verlegen", code="BRAND-ROHR-01")
        self.assertLess(_candidate_score(candidate, scope), 0)

    def test_floor_sealing_does_not_match_parkett_demolition(self):
        scope = {
            "key": "bath.floor.seal",
            "label": "Boden abdichten",
            "unit": "m²",
            "catalog_terms": ["Boden abdichten", "Abdichtung Boden", "Verbundabdichtung"],
        }
        candidate = self.row("Abbruch und Entsorgung vorhandene Parkettböden", code="PARKETT-ABBR-01")
        self.assertLess(_candidate_score(candidate, scope), 0)

    def test_generic_primer_can_match_wall_or_ceiling_primer(self):
        candidate = self.row("Grundierung Wand / Deckenflächen einmal lösemittelfrei grundieren", code="MAL-GR-01")
        wall_scope = {
            "key": "paint.wall.primer",
            "label": "Grundierung Wände",
            "unit": "m²",
            "catalog_terms": ["Grundierung Wand", "Wände grundieren"],
        }
        ceiling_scope = {
            "key": "paint.ceiling.primer",
            "label": "Grundierung Decke",
            "unit": "m²",
            "catalog_terms": ["Grundierung Decke", "Decke grundieren"],
        }
        self.assertGreater(_candidate_score(candidate, wall_scope), 0)
        self.assertGreater(_candidate_score(candidate, ceiling_scope), 0)

    def test_wrong_unit_is_always_rejected(self):
        scope = {
            "key": "bath.water.cold",
            "label": "Kaltwasserleitung neu herstellen",
            "unit": "m",
            "catalog_terms": ["Kaltwasserleitung neu", "Kaltwasserleitung herstellen"],
        }
        candidate = self.row("Kaltwasserleitung neu herstellen", unit="m²", code="WASSER-01")
        self.assertLess(_candidate_score(candidate, scope), 0)

    def test_best_row_returns_none_when_only_bad_context_candidate_exists(self):
        scope = {
            "key": "paint.wall.coat",
            "label": "Dispersionsfarbanstrich Wände",
            "unit": "m²",
            "catalog_terms": ["Dispersionsfarbe Wände", "Wandanstrich Dispersionsfarbe", "Wände streichen"],
        }
        candidate = self.row(
            "Massivwände und Decken weiß streichen in Kellerräumen beschichten",
            code="KELLER-MAL-01",
        )
        with patch("erp.ai_scope_catalog.search_bo_prices", return_value=[candidate]):
            self.assertIsNone(_best_bo_row(SimpleNamespace(), scope))

    def test_best_row_accepts_specific_wall_disperison_position(self):
        scope = {
            "key": "paint.wall.coat",
            "label": "Dispersionsfarbanstrich Wände",
            "unit": "m²",
            "catalog_terms": ["Dispersionsfarbe Wände", "Wandanstrich Dispersionsfarbe", "Wände streichen"],
        }
        candidate = self.row(
            "Wandfläche mit Dispersionsfarbe streichen, innen",
            code="MAL-DISP-01",
        )
        with patch("erp.ai_scope_catalog.search_bo_prices", return_value=[candidate]):
            self.assertIs(_best_bo_row(SimpleNamespace(), scope), candidate)

    def test_generic_wall_paint_rejects_mold_spore_remediation_position(self):
        scope = {
            "key": "paint.wall.coat",
            "label": "Dispersionsfarbanstrich Wände",
            "unit": "m²",
            "catalog_terms": ["Dispersionsfarbe Wände", "Wandanstrich Dispersionsfarbe", "Wände streichen"],
        }
        candidate = self.row(
            "Demobilisieren von Schimmelpilzsporen Abschotten des sichtbaren Befalls mit Folie oder Einstreichen mit Sporenbinder zur Verhinderung weiterer Verbreitung von Gefahrstoffen",
            code="SCHIMMEL-SPOR-01",
        )
        self.assertLess(_candidate_score(candidate, scope), 0)
        with patch("erp.ai_scope_catalog.search_bo_prices", return_value=[candidate]):
            self.assertIsNone(_best_bo_row(SimpleNamespace(), scope))

    def test_floor_cover_still_accepts_normal_baufolie_position(self):
        scope = {
            "key": "protect.floor",
            "label": "Boden / Untergrund abdecken",
            "unit": "m²",
            "catalog_terms": ["Boden abdecken", "Abdeckarbeiten Boden", "Untergrund abdecken"],
        }
        candidate = self.row(
            "Abdecken von Belägen (Fußboden) mit Baufolie abdecken und nach Abschluss der Arbeiten aufnehmen",
            code="ABDECK-BODEN-01",
        )
        self.assertGreater(_candidate_score(candidate, scope), 0)
