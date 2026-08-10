from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI_VERSION = "20260810-6"
CACHE_NAME = "kayi-shell-v18-20260810-de"


def _read(path: str) -> tuple[Path, str]:
    target = ROOT / path
    if not target.exists():
        raise RuntimeError(f"Missing German UI target: {path}")
    return target, target.read_text(encoding="utf-8")


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def patch_photo_picker() -> None:
    path, text = _read("templates/rebuild/room_planner.html")
    old = '''      <label class="rp-photo-drop" data-rp-photo-drop>
        <input type="file" accept="image/jpeg,image/png,image/webp" capture="environment" multiple data-rp-vision-files>
        <span class="rp-photo-orb">📷</span><b>Raumfotos aufnehmen oder auswählen</b><small>4–8 Fotos empfohlen · maximal 12</small>
      </label>
      <div class="rp-photo-previews" data-rp-photo-previews></div>'''
    new = '''      <div class="rp-photo-picker" data-rp-photo-drop>
        <div class="rp-photo-picker-head"><span class="rp-photo-orb">📷</span><div><b>Raumfotos hinzufügen</b><small>4–8 Fotos empfohlen · maximal 12</small></div></div>
        <div class="rp-photo-actions">
          <label class="rp-photo-action rp-photo-action-primary">📷 Foto aufnehmen<input type="file" accept="image/jpeg,image/png,image/webp" capture="environment" data-rp-camera-files></label>
          <label class="rp-photo-action">▧ Aus Galerie auswählen<input type="file" accept="image/jpeg,image/png,image/webp" multiple data-rp-gallery-files></label>
        </div>
        <div class="rp-photo-selection"><span data-rp-photo-count>0 / 12 Fotos ausgewählt</span><button type="button" data-rp-clear-files disabled>Auswahl löschen</button></div>
      </div>
      <div class="rp-photo-previews" data-rp-photo-previews aria-live="polite"></div>'''
    if new not in text:
        if old not in text:
            raise RuntimeError("Room photo picker source contract changed")
        text = text.replace(old, new, 1)
    text = text.replace("KAYI VISION", "KAYI RAUMERKENNUNG").replace("AI-", "KI-")
    text = re.sub(r"\bAI\b", "KI", text)
    text = re.sub(r"(room-planner\.(?:css|js)' %\}\?v=)[^\"']+", r"\g<1>20260810-3", text)
    _write(path, text)


def patch_room_js() -> None:
    path, text = _read("static/js/room-planner.js")
    old = '''const fileInput = $('[data-rp-vision-files]', root);
const filePreview = $('[data-rp-photo-previews]', root);
const readonly = root.dataset.readonly === '1';'''
    new = '''const cameraInput = $('[data-rp-camera-files]', root);
const galleryInput = $('[data-rp-gallery-files]', root);
const filePreview = $('[data-rp-photo-previews]', root);
const photoCount = $('[data-rp-photo-count]', root);
const clearPhotosButton = $('[data-rp-clear-files]', root);
const readonly = root.dataset.readonly === '1';
let selectedVisionFiles = [];
let previewObjectUrls = [];'''
    if new not in text:
        if old not in text:
            raise RuntimeError("Room photo input JS contract changed")
        text = text.replace(old, new, 1)

    old = "  fileInput?.addEventListener('change',renderFilePreviews); $('[data-rp-run-vision]',root)?.addEventListener('click',runVision);"
    new = "  cameraInput?.addEventListener('change',()=>{addVisionFiles(cameraInput.files);cameraInput.value='';}); galleryInput?.addEventListener('change',()=>{addVisionFiles(galleryInput.files);galleryInput.value='';}); clearPhotosButton?.addEventListener('click',clearVisionFiles); $('[data-rp-run-vision]',root)?.addEventListener('click',runVision);"
    if new not in text:
        if old not in text:
            raise RuntimeError("Room photo event binding contract changed")
        text = text.replace(old, new, 1)

    old = "function renderFilePreviews(){if(!filePreview)return;filePreview.innerHTML='';[...(fileInput?.files||[])].slice(0,12).forEach((f)=>{const item=document.createElement('div');item.className='rp-file-chip';item.textContent=f.name;filePreview.appendChild(item);});}\nasync function runVision(ev){ev.preventDefault();if(visionStatus)visionStatus.hidden=false;const files=[...(fileInput?.files||[])];if(!files.length){visionStatus.textContent='Bitte mindestens ein Foto auswählen.';return;}const submit=$('[data-rp-run-vision]',visionForm);"
    new = r'''function fileKey(f){return `${f.name}:${f.size}:${f.lastModified}`;}
function addVisionFiles(list){const ok=new Set(['image/jpeg','image/png','image/webp']);let rejected=false;[...(list||[])].forEach(f=>{if(!ok.has(f.type)){rejected=true;return;}if(f.size>12*1024*1024){toast(`${f.name}: Das Foto ist größer als 12 MB.`,'error');return;}if(selectedVisionFiles.some(x=>fileKey(x)===fileKey(f)))return;if(selectedVisionFiles.length>=12){rejected=true;return;}selectedVisionFiles.push(f);});if(rejected)toast(selectedVisionFiles.length>=12?'Es können maximal 12 Fotos ausgewählt werden.':'Ein Dateiformat wird nicht unterstützt.','error');renderFilePreviews();}
function clearVisionFiles(){selectedVisionFiles=[];previewObjectUrls.forEach(URL.revokeObjectURL);previewObjectUrls=[];if(filePreview)filePreview.innerHTML='';if(photoCount)photoCount.textContent='0 / 12 Fotos ausgewählt';if(clearPhotosButton)clearPhotosButton.disabled=true;}
function renderFilePreviews(){if(!filePreview)return;previewObjectUrls.forEach(URL.revokeObjectURL);previewObjectUrls=[];filePreview.innerHTML='';selectedVisionFiles.forEach((f,i)=>{const card=document.createElement('div');card.className='rp-photo-preview';const img=document.createElement('img');const url=URL.createObjectURL(f);previewObjectUrls.push(url);img.src=url;img.alt=`Vorschau Foto ${i+1}`;const meta=document.createElement('span');meta.textContent=`Foto ${i+1}`;const remove=document.createElement('button');remove.type='button';remove.textContent='×';remove.setAttribute('aria-label',`Foto ${i+1} entfernen`);remove.onclick=()=>{selectedVisionFiles.splice(i,1);renderFilePreviews();};card.append(img,meta,remove);filePreview.appendChild(card);});if(photoCount)photoCount.textContent=`${selectedVisionFiles.length} / 12 Fotos ausgewählt`;if(clearPhotosButton)clearPhotosButton.disabled=!selectedVisionFiles.length;}
function germanRequestError(err,fallback){const raw=String(err?.message||'');if(/Failed to fetch|NetworkError|Load failed|fetch failed/i.test(raw))return 'Netzwerkfehler. Bitte Internetverbindung prüfen und erneut versuchen.';if(/Unexpected token|not valid JSON|JSON/i.test(raw))return fallback;return raw||fallback;}
async function readJson(res,fallback){if(res.redirected&&new URL(res.url,location.href).pathname.includes('/login'))throw new Error('Deine Sitzung ist abgelaufen. Bitte neu anmelden.');const type=(res.headers.get('content-type')||'').toLowerCase();const raw=await res.text();if(!type.includes('application/json')){if(res.status===413)throw new Error('Die ausgewählten Fotos sind zusammen zu groß. Bitte weniger oder kleinere Fotos verwenden.');if(res.status===403)throw new Error('Die Anfrage wurde aus Sicherheitsgründen abgelehnt. Bitte Seite neu laden.');if(res.status>=500)throw new Error('Die Raumerkennung ist momentan nicht erreichbar. Bitte später erneut versuchen.');throw new Error(fallback);}let data;try{data=raw?JSON.parse(raw):{};}catch(_){throw new Error(fallback);}if(!res.ok)throw new Error(data.error||fallback);return data;}
async function runVision(ev){ev.preventDefault();if(visionStatus)visionStatus.hidden=false;const files=selectedVisionFiles.slice(0,12);if(!files.length){visionStatus.textContent='Bitte mindestens ein Foto aufnehmen oder aus der Galerie auswählen.';return;}if(files.reduce((sum,f)=>sum+f.size,0)>50*1024*1024){visionStatus.textContent='Die ausgewählten Fotos sind zusammen größer als 50 MB.';return;}const submit=$('[data-rp-run-vision]',visionForm);'''
    if "function fileKey(f)" not in text:
        if old not in text:
            raise RuntimeError("Room photo preview JS contract changed")
        text = text.replace(old, new, 1)

    text = text.replace("const data=await res.json();if(!res.ok)throw new Error(data.error||'Speichern fehlgeschlagen');", "const data=await readJson(res,'Speichern fehlgeschlagen. Bitte Seite neu laden.');")
    text = text.replace("const data=await res.json();if(!res.ok)throw new Error(data.error||'AI-Analyse fehlgeschlagen');", "const data=await readJson(res,'Die Raumerkennung hat eine unerwartete Serverantwort erhalten. Bitte Seite neu laden und erneut versuchen.');")
    text = text.replace("toast(`${data.recognized_objects||0} Objekte und ${data.recognized_openings||0} Öffnungen erkannt.`,'success');setTimeout(()=>visionDialog?.close(),1600);", "toast(`${data.recognized_objects||0} Objekte und ${data.recognized_openings||0} Öffnungen erkannt.`,'success');clearVisionFiles();setTimeout(()=>visionDialog?.close(),1600);")
    text = text.replace("}catch(err){visionStatus.textContent=err.message;toast(err.message,'error');}finally{submit.disabled=false;}}", "}catch(err){const message=germanRequestError(err,'Die Raumerkennung konnte nicht abgeschlossen werden. Bitte Seite neu laden und erneut versuchen.');visionStatus.textContent=message;toast(message,'error');}finally{submit.disabled=false;}}")
    text = text.replace("AI analysiert Raum, Wände und Objekte…", "KI analysiert Raum, Wände und Objekte…").replace("AI-Entwurf gespeichert", "KI-Entwurf gespeichert").replace("AI-Erkennung", "KI-Erkennung")
    text = text.replace("throw new Error('Room planner root missing');", "throw new Error('Raumplaner konnte nicht gestartet werden.');")
    _write(path, text)


def patch_room_css() -> None:
    path, text = _read("static/css/room-planner.css")
    if "KAYI multi-photo picker" in text:
        return
    text += "\n/* KAYI multi-photo picker */\n.rp-photo-picker{border:1.5px dashed #c9ced6;border-radius:20px;padding:16px;background:#fafbfc}.rp-photo-picker-head{display:flex;gap:12px;align-items:center;margin-bottom:12px}.rp-photo-picker-head>div{display:flex;flex-direction:column}.rp-photo-actions{display:grid;grid-template-columns:1fr 1fr;gap:10px}.rp-photo-action{min-height:48px;border:1px solid #d8dce2;border-radius:14px;background:#fff;display:flex;align-items:center;justify-content:center;font-weight:800;cursor:pointer;padding:10px}.rp-photo-action-primary{background:#17191d;color:#fff}.rp-photo-action input{position:absolute;width:1px;height:1px;opacity:0}.rp-photo-selection{display:flex;justify-content:space-between;gap:8px;margin-top:10px;font-size:12px;color:#69717b}.rp-photo-selection button{border:0;background:transparent;font-weight:800}.rp-photo-previews{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-top:12px}.rp-photo-preview{position:relative;overflow:hidden;border:1px solid #e0e3e8;border-radius:14px;background:#fff}.rp-photo-preview img{display:block;width:100%;aspect-ratio:4/3;object-fit:cover}.rp-photo-preview span{display:block;padding:7px 9px;font-size:12px;font-weight:800}.rp-photo-preview button{position:absolute;right:6px;top:6px;width:28px;height:28px;border:0;border-radius:50%;background:#111c;color:#fff;font-size:18px}@media(max-width:700px){.rp-photo-actions{grid-template-columns:1fr}.rp-photo-previews{grid-template-columns:repeat(2,1fr)}}\n"
    _write(path, text)


def germanize_all_templates() -> None:
    replacements = {
        "Work OS":"Handwerkssoftware", "ToolTime Import":"ToolTime-Datenimport", "Projekt ohne Wizard":"Projekt ohne Assistenten", "AI + 3D":"KI + 3D", "Details können gleich per Voice erfasst werden.":"Details können gleich per Spracheingabe erfasst werden.", "per Voice":"per Spracheingabe", "Voice":"Spracheingabe", "Provider":"Anbieter", "Workflows":"Arbeitsabläufe", "Fallback":"Rückfalllösung", "ToolTime-parity Flow":"an ToolTime orientierten Arbeitsablauf",
        "Create a room from photos":"Raum aus Fotos aufbauen", "Multiple viewpoints provide significantly better positions and fewer duplicate objects.":"Mehrere Blickwinkel liefern deutlich bessere Positionen und weniger doppelte Objekte.", "Entrance":"Eingang", "room completely":"Raum vollständig", "Opposite":"Gegenüber", "entire wall":"gesamte Wand", "Left":"Links", "Right":"Rechts", "including connections":"inkl. Anschlüsse", "Take or select room photos":"Raumfotos aufnehmen oder auswählen", "4–8 photos recommended · maximum 12":"4–8 Fotos empfohlen · maximal 12", "Optional: Secure the scale":"Optional: Maßstab absichern", "Without a reference, AI places objects relatively correctly, but metric measurements still require verification.":"Ohne Referenz platziert die KI Objekte relativ korrekt; metrische Maße müssen weiterhin geprüft werden.", "Width cm":"Breite cm", "Height cm":"Höhe cm", ">Cancel<":">Abbrechen<", "Detect and place space":"Raum erkennen und platzieren"
    }
    for path in (ROOT / "templates").rglob("*.html"):
        text = path.read_text(encoding="utf-8")
        original = text
        for old, new in replacements.items():
            text = text.replace(old, new)
        text = text.replace("AI-", "KI-")
        text = re.sub(r"(?<![-\w])AI(?=[\s+:.&<])", "KI", text)
        if text != original:
            path.write_text(text, encoding="utf-8")


def install_runtime_guard() -> None:
    js = r'''(()=>{'use strict';const m={'Cancel':'Abbrechen','Save':'Speichern','Close':'Schließen','Search':'Suchen','Create':'Erstellen','New':'Neu','Edit':'Bearbeiten','Delete':'Löschen','Upload':'Hochladen','Select':'Auswählen','Choose':'Auswählen','Company':'Firma','Salutation':'Anrede','First name':'Vorname','Last name':'Nachname','Email':'E-Mail','Phone':'Telefon','Mobile':'Mobil','Street':'Straße','Postal code':'PLZ','City':'Ort','Country':'Land','Notes':'Notizen','Description':'Beschreibung','Customer':'Kunde','Project':'Projekt','Task':'Aufgabe','Quote':'Angebot','Invoice':'Rechnung','Calendar':'Kalender','Settings':'Einstellungen','Work OS':'Handwerkssoftware','Provider':'Anbieter','Wizard':'Assistent','Voice':'Spracheingabe','Create a room from photos':'Raum aus Fotos aufbauen','Entrance':'Eingang','Opposite':'Gegenüber','Left':'Links','Right':'Rechts','Take or select room photos':'Raumfotos aufnehmen oder auswählen','Cancel':'Abbrechen','Detect and place space':'Raum erkennen und platzieren'};const p=[['Multiple viewpoints provide significantly better positions and fewer duplicate objects.','Mehrere Blickwinkel liefern deutlich bessere Positionen und weniger doppelte Objekte.'],['Without a reference, AI places objects relatively correctly, but metric measurements still require verification.','Ohne Referenz platziert die KI Objekte relativ korrekt; metrische Maße müssen weiterhin geprüft werden.'],['AI + 3D','KI + 3D']];function t(v){let s=String(v||''),q=s.trim();if(m[q])s=s.replace(q,m[q]);for(const x of p)s=s.split(x[0]).join(x[1]);return s}function e(n){if(n.nodeType===3){if(n.parentElement&&!['SCRIPT','STYLE','TEXTAREA'].includes(n.parentElement.tagName)){const a=n.nodeValue,b=t(a);if(a!==b)n.nodeValue=b}return}if(!(n instanceof Element))return;for(const a of ['placeholder','title','aria-label'])if(n.hasAttribute(a)){const v=n.getAttribute(a),w=t(v);if(v!==w)n.setAttribute(a,w)}n.childNodes.forEach(e)}function run(){e(document.body)}document.readyState==='loading'?document.addEventListener('DOMContentLoaded',run):run();new MutationObserver(r=>r.forEach(x=>x.addedNodes.forEach(e))).observe(document.documentElement,{subtree:true,childList:true});navigator.serviceWorker?.getRegistration('/')?.then?.(r=>r?.update()).catch(()=>{});caches?.keys?.().then(k=>Promise.all(k.filter(x=>x.startsWith('kayi-shell-')&&x!=='kayi-shell-v18-20260810-de').map(x=>caches.delete(x)))).catch(()=>{});})();'''
    target = ROOT / "static/js/kayi-de-ui.js"
    target.write_text(js, encoding="utf-8")
    for relative in ("templates/rebuild/base.html", "templates/erp/base.html", "templates/registration/login.html"):
        path = ROOT / relative
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        if "kayi-de-ui.js" not in text:
            if "{% load static %}" not in text:
                text = "{% load static %}\n" + text
            tag = f'''<script src="{{% static 'js/kayi-de-ui.js' %}}?v={UI_VERSION}" defer></script>'''
            text = text.replace("</body>", tag + "\n</body>", 1)
        text = re.sub(r"(\.(?:css|js)' %\}\?v=)[^\"']+", rf"\g<1>{UI_VERSION}", text)
        path.write_text(text, encoding="utf-8")
    sw = ROOT / "static/js/sw.js"
    if sw.exists():
        text = sw.read_text(encoding="utf-8")
        sw.write_text(re.sub(r'const CACHE = "[^"]+";', f'const CACHE = "{CACHE_NAME}";', text, count=1), encoding="utf-8")
    app = ROOT / "static/js/app.js"
    if app.exists():
        text = app.read_text(encoding="utf-8")
        app.write_text(re.sub(r'/sw\.js\?v=[^\"]+', f'/sw.js?v={UI_VERSION}', text), encoding="utf-8")


def add_regression_test() -> None:
    test = '''from pathlib import Path\nfrom django.test import SimpleTestCase\nROOT=Path(__file__).resolve().parents[1]\nclass GermanUiQualityTests(SimpleTestCase):\n def test_room_photo_ui_is_german_and_camera_gallery_are_separate(self):\n  h=(ROOT/"templates/rebuild/room_planner.html").read_text(encoding="utf-8");j=(ROOT/"static/js/room-planner.js").read_text(encoding="utf-8")\n  for x in ("Foto aufnehmen","Aus Galerie auswählen","data-rp-camera-files","data-rp-gallery-files"):self.assertIn(x,h)\n  self.assertIn("selectedVisionFiles",j);self.assertIn("readJson(res,fallback)",j)\n  for x in ("Create a room from photos","Take or select room photos","Detect and place space",">Cancel<"):self.assertNotIn(x,h)\n def test_german_runtime_guard_is_installed(self):\n  h=(ROOT/"templates/rebuild/base.html").read_text(encoding="utf-8");self.assertIn("kayi-de-ui.js",h);self.assertNotIn("Work OS",h)\n'''
    (ROOT / "tests/test_german_ui_quality.py").write_text(test, encoding="utf-8")


patch_photo_picker()
patch_room_js()
patch_room_css()
germanize_all_templates()
install_runtime_guard()
add_regression_test()
print("KAYI German-only UI, camera/gallery multi-photo picker and robust JSON handling installed.")
