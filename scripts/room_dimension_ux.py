from pathlib import Path
import re
R=Path(__file__).resolve().parents[1];V='20260811-7';M='KAYI ROOM DIMENSION UX 2026-08-11'
def r(p):return (R/p).read_text(encoding='utf-8')
def w(p,s):q=R/p;q.parent.mkdir(parents=True,exist_ok=True);q.write_text(s,encoding='utf-8')

p='templates/rebuild/room_planner.html';s=r(p)
s=s.replace('<label><span>Länge</span><div><input type="number" min="0.1" max="50" step="0.01" data-rp-room-field="length_m"><em>m</em></div></label>','<label><span>Länge / Tiefe</span><div><input type="number" min="0.1" max="50" step="0.01" data-rp-room-field="length_m"><em>m</em></div></label>',1)
old='''      <div class="rp-calibration">\n        <div><b>Optional: Maßstab absichern</b><small>Ohne Referenz platziert KI Objekte relativ korrekt, metrische Maße bleiben aber prüfpflichtig.</small></div>\n        <label>Referenz<select class="nx-control" data-rp-reference-type><option value="">Keine</option><option value="a4">A4-Blatt (21 × 29,7 cm)</option><option value="custom">Eigenes Referenzobjekt</option></select></label>\n        <label>Breite cm<input class="nx-control" type="number" min="1" max="500" step="0.1" data-rp-reference-width></label>\n        <label>Höhe cm<input class="nx-control" type="number" min="1" max="500" step="0.1" data-rp-reference-height></label>\n      </div>\n'''
old_ai=old.replace('KI Objekte','AI Objekte')
new='''      <div class="rp-calibration">\n        <div class="rp-calibration-intro"><b>Optional: Foto-Maßstab absichern</b><small>Diese zwei Werte gehören nur zum sichtbaren Referenzobjekt im Foto – nicht zu den Raummaßen. Für ein A4-Blatt reichen Breite × Höhe; eine Referenz-Tiefe wird nicht benötigt.</small></div>\n        <label>Referenz im Foto<select class="nx-control" data-rp-reference-type><option value="">Keine</option><option value="a4">A4-Blatt (21 × 29,7 cm)</option><option value="custom">Eigenes Referenzobjekt</option></select></label>\n        <label>Sichtbare Breite cm<input class="nx-control" type="number" min="1" max="500" step="0.1" data-rp-reference-width></label>\n        <label>Sichtbare Höhe cm<input class="nx-control" type="number" min="1" max="500" step="0.1" data-rp-reference-height></label>\n        <div class="rp-known-room"><div><b>Raummaße bekannt?</b><small>Wenn du echte Maße hast, alle drei eintragen. KAYI nutzt Länge/Tiefe × Breite × Höhe als verbindliche Geometrie und erkennt aus den Fotos vor allem Positionen und Objekte.</small></div><label>Länge / Tiefe m<input class="nx-control" type="number" min="0.5" max="50" step="0.01" data-rp-known-length placeholder="z. B. 4,20"></label><label>Breite m<input class="nx-control" type="number" min="0.5" max="50" step="0.01" data-rp-known-width placeholder="z. B. 3,10"></label><label>Höhe m<input class="nx-control" type="number" min="1.5" max="12" step="0.01" data-rp-known-height placeholder="z. B. 2,55"></label></div>\n      </div>\n'''
if new not in s:
    target=old if old in s else old_ai
    if target not in s:raise RuntimeError('room calibration anchor changed')
    s=s.replace(target,new,1)
s=re.sub(r"(room-planner\.(?:css|js)' %\}\?v=)[^\"']+",rf"\g<1>{V}",s);w(p,s)

p='erp/room_planner_views.py';s=r(p);a='        "existing_dimensions_confirmed": bool(measurement and measurement.status == m.RoomMeasurement.Status.CONFIRMED),\n';b='        "existing_dimensions_confirmed": bool(request.POST.get("known_room_dimensions") == "1" or (measurement and measurement.status == m.RoomMeasurement.Status.CONFIRMED)),\n'
if b not in s:
    if a not in s:raise RuntimeError('room backend anchor changed')
    s=s.replace(a,b,1)
w(p,s)

p='static/js/room-planner.js';s=r(p);a="fd.append('measurement_id',root.dataset.measurementId||'');fd.append('state',JSON.stringify(state));const refType=$('[data-rp-reference-type]',visionForm)?.value||'';";b="fd.append('measurement_id',root.dataset.measurementId||'');const kl=Number($('[data-rp-known-length]',visionForm)?.value||0),kw=Number($('[data-rp-known-width]',visionForm)?.value||0),kh=Number($('[data-rp-known-height]',visionForm)?.value||0),known=[kl,kw,kh],anyKnown=known.some(v=>v>0),allKnown=known.every(v=>Number.isFinite(v)&&v>0);if(anyKnown&&!allKnown){visionStatus.textContent='Wenn Raummaße bekannt sind, bitte Länge/Tiefe, Breite und Höhe vollständig eintragen.';submit.disabled=false;return;}const visionState=deepClone(state);if(allKnown){visionState.room.length_m=clamp(kl,1,30);visionState.room.width_m=clamp(kw,1,30);visionState.room.height_m=clamp(kh,1.8,8);fd.append('known_room_dimensions','1');}fd.append('state',JSON.stringify(visionState));const refType=$('[data-rp-reference-type]',visionForm)?.value||'';"
if b not in s:
    if a not in s:raise RuntimeError('room JS anchor changed')
    s=s.replace(a,b,1)
w(p,s)

p='static/css/room-planner.css';s=r(p)
if M not in s:s+='''\n/* KAYI ROOM DIMENSION UX 2026-08-11 */\n.rp-calibration-intro{grid-column:1/-1}.rp-known-room{grid-column:1/-1;display:grid;grid-template-columns:1.35fr repeat(3,minmax(0,1fr));gap:10px;padding-top:12px;margin-top:4px;border-top:1px solid rgba(17,24,39,.09)}.rp-known-room>div{display:grid;align-content:center;gap:3px}.rp-known-room label{min-width:0}@media(max-width:760px){.rp-known-room{grid-template-columns:1fr 1fr}.rp-known-room>div{grid-column:1/-1}.rp-known-room label:last-child{grid-column:1/-1}}\n''';w(p,s)
w('tests/test_room_dimension_ux.py','''from pathlib import Path\nfrom django.test import SimpleTestCase\nR=Path(__file__).resolve().parents[1]\nclass T(SimpleTestCase):\n def test_contract(self):\n  t=(R/'templates/rebuild/room_planner.html').read_text();j=(R/'static/js/room-planner.js').read_text();v=(R/'erp/room_planner_views.py').read_text();self.assertIn('sichtbaren Referenzobjekt',t);self.assertIn('Länge / Tiefe',t);self.assertIn('data-rp-known-length',t);self.assertIn('known_room_dimensions',j);self.assertIn('known_room_dimensions',v)\n''')
print('KAYI room dimension UX installed')
