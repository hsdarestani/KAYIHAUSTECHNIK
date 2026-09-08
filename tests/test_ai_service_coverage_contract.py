from pathlib import Path
from django.test import SimpleTestCase


class AiServiceCoverageContractTests(SimpleTestCase):
    SAMPLE = """wir möchten im bad die alten beläge an wand und boden entfernen und alles neu verfliesen die wandfliesen sollen im nassbereich 2,00 meter betragen und die restlichen wände sollen bis zu einer höhe von 1,40 meter gefliest werden der boden soll hell grau sein in 60x60 cm und die wände in weiß größe 30x60 cm die restlichen wände und decken sollen in q3 gespachtelt werden und gestrichen die tür soll geschliffen und lackiert werden. alle sanitär objekte sollen ausgetauscht werden neue badewanne neue toilette und neues waschbecken"""

    def test_explicit_tile_work_cannot_be_deprioritized_by_prompt(self):
        source = Path("erp/services/ai.py").read_text(encoding="utf-8")
        self.assertIn("Decke alle ausdrücklich", source)
        self.assertIn("Fliesen-, Platten- oder Belagsposition", source)
        self.assertIn("Coverage-Prinzip", source)
        self.assertIn("verfliesen", self.SAMPLE)
        self.assertIn("wandfliesen", self.SAMPLE)
        self.assertIn("sanitär", self.SAMPLE)
