from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
api_path = ROOT / "erp/api.py"
urls_path = ROOT / "config/urls.py"
app_path = ROOT / "native/www/app.js"

app = app_path.read_text(encoding="utf-8")
for marker in (
    "renderDocuments", "renderDocumentDetail", "renderDocumentForm", "saveDocument",
    "renderExpenses", "renderExpenseForm", "saveExpense", "/api/mobile/commercial/",
    "Angebot wurde gespeichert.", "Rechnung wurde gespeichert.", "Ausgabe wurde gespeichert.",
):
    if marker not in app:
        raise RuntimeError(f"Native Full App phase 4 marker missing: {marker}")

api = api_path.read_text(encoding="utf-8")
if "class MobileCommercialDocumentAPIView" not in api:
    anchor = "\n\nclass MobileAppointmentWorkReportAPIView(APIView):"
    endpoint = '''

class MobileCommercialDocumentAPIView(APIView):
    """Create or replace a quote/invoice and its line items atomically."""
    permission_classes = [IsAuthenticated]

    def post(self, request, kind, pk=None):
        return self._save(request, kind, pk)

    def patch(self, request, kind, pk=None):
        return self._save(request, kind, pk)

    def _save(self, request, kind, pk):
        from decimal import Decimal, InvalidOperation
        from django.db import transaction
        from erp.models import QuoteItem, InvoiceItem

        if not can_write(request.user) or not can_view_prices(request.user):
            return Response({"detail": "Keine Berechtigung für kaufmännische Dokumente."}, status=403)
        definitions = {
            "quote": (Quote, QuoteItem, QuoteSerializer, "quote"),
            "invoice": (Invoice, InvoiceItem, InvoiceSerializer, "invoice"),
        }
        if kind not in definitions:
            return Response({"detail": "Unbekannter Dokumenttyp."}, status=404)
        model, item_model, serializer_class, parent_field = definitions[kind]
        org = organization_for(request.user)
        instance = model.objects.filter(organization=org, pk=pk).first() if pk else None
        if pk and not instance:
            return Response({"detail": "Dokument nicht gefunden."}, status=404)
        project = Project.objects.filter(organization=org, pk=request.data.get("project")).first()
        if not project:
            return Response({"detail": "Bitte ein gültiges Projekt auswählen."}, status=400)
        items = request.data.get("items")
        if not isinstance(items, list) or not items:
            return Response({"detail": "Mindestens eine Position ist erforderlich."}, status=400)
        normalized = []
        try:
            for position, item in enumerate(items, 1):
                description = str(item.get("description", "")).strip()
                quantity = Decimal(str(item.get("quantity", "")))
                unit_price = Decimal(str(item.get("unit_price", "")))
                tax_rate = Decimal(str(item.get("tax_rate", "19")))
                if not description or quantity <= 0 or unit_price < 0 or tax_rate < 0:
                    raise ValueError
                normalized.append({
                    "position": position, "description": description[:10000],
                    "quantity": quantity, "unit": str(item.get("unit", "Stk."))[:30],
                    "unit_price": unit_price, "tax_rate": tax_rate,
                })
        except (InvalidOperation, TypeError, ValueError):
            return Response({"detail": "Positionen enthalten ungültige Mengen oder Preise."}, status=400)
        header = {key: value for key, value in request.data.items() if key != "items"}
        header["project"] = project.pk
        serializer = serializer_class(instance, data=header, partial=bool(instance), context={"request": request})
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            if instance:
                document = serializer.save()
                document.items.all().delete()
            else:
                document = serializer.save(
                    organization=org, number=next_number(org, kind), created_by=request.user,
                )
            item_model.objects.bulk_create([
                item_model(**{parent_field: document}, **item) for item in normalized
            ])
        document = model.objects.prefetch_related("items").get(pk=document.pk)
        return Response(serializer_class(document, context={"request": request}).data, status=200 if instance else 201)
'''
    if anchor not in api:
        raise RuntimeError("Phase 4 API insertion anchor missing")
    api = api.replace(anchor, endpoint + anchor, 1)
    api_path.write_text(api, encoding="utf-8")

urls = urls_path.read_text(encoding="utf-8")
routes = (
    '    path("api/mobile/commercial/<str:kind>/", api.MobileCommercialDocumentAPIView.as_view(), name="api-mobile-commercial-create"),\n',
    '    path("api/mobile/commercial/<str:kind>/<int:pk>/", api.MobileCommercialDocumentAPIView.as_view(), name="api-mobile-commercial-update"),\n',
)
anchor = '    path("api/mobile/appointments/<int:pk>/work-report/", api.MobileAppointmentWorkReportAPIView.as_view(), name="api-mobile-appointment-work-report"),\n'
if routes[0] not in urls:
    if anchor not in urls:
        raise RuntimeError("Phase 4 URL insertion anchor missing")
    urls = urls.replace(anchor, anchor + "".join(routes), 1)
    urls_path.write_text(urls, encoding="utf-8")

(ROOT / "tests/test_native_full_app_phase4.py").write_text('''from pathlib import Path
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class NativeFullAppPhase4Tests(SimpleTestCase):
    def test_finance_is_role_gated_and_has_complete_flows(self):
        app = (ROOT / "native/www/app.js").read_text(encoding="utf-8")
        self.assertIn("function renderCommercial() { if(!isOffice()) return forbidden()", app)
        for marker in ("renderDocuments", "renderDocumentDetail", "renderDocumentForm", "saveDocument", "renderExpenses", "saveExpense"):
            self.assertIn(marker, app)

    def test_document_editor_sends_positions_to_atomic_endpoint(self):
        app = (ROOT / "native/www/app.js").read_text(encoding="utf-8")
        api = (ROOT / "erp/api.py").read_text(encoding="utf-8")
        self.assertIn("/api/mobile/commercial/", app)
        self.assertIn("data-add-position", app)
        self.assertIn("class MobileCommercialDocumentAPIView", api)
        self.assertIn("with transaction.atomic()", api)
        self.assertIn("Mindestens eine Position ist erforderlich.", api)

    def test_finance_actions_have_user_feedback(self):
        app = (ROOT / "native/www/app.js").read_text(encoding="utf-8")
        for marker in ("Angebot wurde gespeichert.", "Rechnung wurde gespeichert.", "Ausgabe wurde gespeichert."):
            self.assertIn(marker, app)
''', encoding="utf-8")

print("Installed Native Full App phase 4: quotes, invoices, line items and expenses.")
