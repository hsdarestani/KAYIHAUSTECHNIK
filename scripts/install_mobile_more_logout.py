from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "templates/erp/base.html"
text = path.read_text(encoding="utf-8")

if 'data-mobile-more-sheet' not in text:
    old = '''<nav class="mobile-nav">
  <a href="{% url 'dashboard' %}"><span>⌂</span>Start</a>
  <a href="{% url 'resource-list' 'projects' %}"><span>▦</span>Projekte</a>
  {% if is_technician %}<a href="{% url 'mobile-app' %}" class="mobile-primary"><span>▶</span>Arbeit</a>{% else %}<a href="{% url 'project-create' %}" class="mobile-primary"><span>＋</span>Neu</a>{% endif %}
  <a href="{% url 'calendar' %}"><span>□</span>Termine</a>
  <a href="{% url 'mobile-app' %}"><span>▯</span>App</a>
</nav>'''
    new = '''<nav class="mobile-nav">
  <a href="{% url 'dashboard' %}"><span>⌂</span>Start</a>
  <a href="{% url 'calendar' %}"><span>□</span>Termine</a>
  <a href="{% url 'resource-list' 'projects' %}"><span>▦</span>Projekte</a>
  {% if not is_technician %}<a href="{% url 'resource-list' 'customers' %}"><span>◎</span>Kunden</a>{% else %}<a href="{% url 'mobile-app' %}"><span>▶</span>Arbeit</a>{% endif %}
  <button type="button" data-mobile-more><span>•••</span>Mehr</button>
</nav>
<div class="mobile-more-sheet" data-mobile-more-sheet hidden>
  <a href="{% url 'settings' %}">⚙ Einstellungen</a>
  <form action="{% url 'logout' %}" method="post">{% csrf_token %}<button type="submit">↪ Abmelden</button></form>
</div>
<style>.mobile-nav button{border:0;background:transparent;color:inherit;font:inherit}.mobile-more-sheet{position:fixed;z-index:120;right:12px;bottom:calc(76px + env(safe-area-inset-bottom));left:12px;padding:10px;border:1px solid #ded8cc;border-radius:16px;background:#fff;box-shadow:0 18px 55px rgba(0,0,0,.22)}.mobile-more-sheet a,.mobile-more-sheet button{display:block;width:100%;padding:14px;border:0;border-radius:10px;background:transparent;color:#17191c;text-align:left;text-decoration:none;font:inherit;font-weight:750}.mobile-more-sheet button{color:#a43732}@media(min-width:901px){.mobile-more-sheet{display:none!important}}</style>
<script>document.addEventListener('DOMContentLoaded',()=>{const trigger=document.querySelector('[data-mobile-more]');const sheet=document.querySelector('[data-mobile-more-sheet]');trigger?.addEventListener('click',()=>{sheet.hidden=!sheet.hidden;trigger.setAttribute('aria-expanded',String(!sheet.hidden));});document.addEventListener('click',event=>{if(sheet&&!sheet.hidden&&!sheet.contains(event.target)&&!trigger?.contains(event.target))sheet.hidden=true;});});</script>'''
    if old not in text:
        raise RuntimeError("Canonical mobile navigation anchor missing")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")

print("A+Bau mobile web Mehr menu and logout installed.")
