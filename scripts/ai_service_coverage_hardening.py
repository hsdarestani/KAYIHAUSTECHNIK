from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "erp/services/ai.py"
text = path.read_text(encoding="utf-8")
old = '''            "die exakt im Kontext vorkommen. Keine Preise oder Leistungen erfinden. Priorisiere die "\n            "kleinste sinnvolle Auswahl und nenne kurz den Grund.\\n\\nAnfrage:\\n" + request_text\n'''
new = '''            "die exakt im Kontext vorkommen. Keine Preise oder Leistungen erfinden. Decke alle ausdrücklich "\n            "verlangten Gewerke ab. Wenn die Anfrage Fliesen, verfliesen, Wandfliesen, Bodenfliesen oder "\n            "gefliest ausdrücklich nennt, muss mindestens eine passende Fliesen-, Platten- oder Belagsposition "\n            "gewählt werden, sofern ein exakt passender Code im bereitgestellten Kontext vorhanden ist. Dasselbe "\n            "Coverage-Prinzip gilt für Sanitär, Maler/Spachtel, Türen und andere ausdrücklich verlangte Gewerke. "\n            "Erst danach begrenze auf die kleinste sinnvolle Auswahl und nenne kurz den Grund.\\n\\nAnfrage:\\n" + request_text\n'''
if new not in text:
    if old not in text:
        raise RuntimeError("AI catalog-service suggestion prompt changed unexpectedly")
    text = text.replace(old, new, 1)
path.write_text(text, encoding="utf-8")

test_path = ROOT / "tests" / "test_ai_service_coverage_contract.py"
test_path.write_text('''from pathlib import Path\nfrom django.test import SimpleTestCase\n\n\nclass AiServiceCoverageContractTests(SimpleTestCase):\n    SAMPLE = """wir möchten im bad die alten beläge an wand und boden entfernen und alles neu verfliesen die wandfliesen sollen im nassbereich 2,00 meter betragen und die restlichen wände sollen bis zu einer höhe von 1,40 meter gefliest werden der boden soll hell grau sein in 60x60 cm und die wände in weiß größe 30x60 cm die restlichen wände und decken sollen in q3 gespachtelt werden und gestrichen die tür soll geschliffen und lackiert werden. alle sanitär objekte sollen ausgetauscht werden neue badewanne neue toilette und neues waschbecken"""\n\n    def test_explicit_tile_work_cannot_be_deprioritized_by_prompt(self):\n        source = Path("erp/services/ai.py").read_text(encoding="utf-8")\n        self.assertIn("Decke alle ausdrücklich", source)\n        self.assertIn("Fliesen-, Platten- oder Belagsposition", source)\n        self.assertIn("Coverage-Prinzip", source)\n        self.assertIn("verfliesen", self.SAMPLE)\n        self.assertIn("wandfliesen", self.SAMPLE)\n        self.assertIn("sanitär", self.SAMPLE)\n''', encoding="utf-8")
print("KAYI AI service suggestions now prioritize explicit trade coverage before minimizing the list.")
