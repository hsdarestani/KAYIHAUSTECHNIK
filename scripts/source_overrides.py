from pathlib import Path


def replace_exact(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise RuntimeError(f"Expected source fragment not found in {path}")
    target.write_text(text.replace(old, new), encoding="utf-8")


replace_exact(
    "erp/models.py",
    '    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="objects")\n'
    '    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="objects")',
    '    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="object_locations")\n'
    '    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="object_locations")',
)

replace_exact(
    "Dockerfile",
    "COPY . .\nRUN useradd --create-home --uid 10001 appuser",
    "COPY . .\nRUN python manage.py makemigrations erp --noinput\nRUN useradd --create-home --uid 10001 appuser",
)
