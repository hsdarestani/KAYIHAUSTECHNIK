from django.test import SimpleTestCase
from erp.ai_scope_planner import catalog_semantic_match
class AuthoritativeCatalogSafetyContractTests(SimpleTestCase):
    def test_known_false_positive_descriptions_fail_semantic_gate(self):
        self.assertFalse(catalog_semantic_match({"key":"bath.floor.seal","unit":"m²"}, {"description":"Abbruch und Entsorgung vorhandene Parkettböden","unit":"m²"}))
        self.assertFalse(catalog_semantic_match({"key":"bath.walltile.install","unit":"m²"}, {"description":"Brandschutz Dämmwolle ums Fallrohr verlegen","unit":"m²"}))
