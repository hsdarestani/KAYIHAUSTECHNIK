// A+BAU V3 CATALOGUE + TEXT LAYOUT PARITY 2026-09-08
(() => {
  const num=value=>{const n=Number(String(value??"").trim().replace(/\s/g,"").replace(",","."));return Number.isFinite(n)?n:0};
  const money=new Intl.NumberFormat("de-DE",{style:"currency",currency:"EUR"});

  const article=document.querySelector("[data-ab-v3-article-form]");
  if(article){
    const quantity=article.querySelector("[data-ab-quantity]"),purchase=article.querySelector("[data-ab-purchase]"),markup=article.querySelector("[data-ab-markup]"),sales=article.querySelector("[data-ab-sales]"),markupValue=article.querySelector("[data-ab-markup-value]"),total=article.querySelector("[data-ab-total]");
    let syncing=false;
    const render=()=>{const q=Math.max(0,num(quantity?.value)),p=Math.max(0,num(purchase?.value)),s=Math.max(0,num(sales?.value));if(markupValue)markupValue.textContent=money.format(s-p);if(total)total.textContent=money.format(q*s)};
    const salesFromMarkup=()=>{if(syncing)return;syncing=true;const p=Math.max(0,num(purchase?.value)),m=num(markup?.value);if(sales)sales.value=(p*(1+m/100)).toFixed(2);syncing=false;render()};
    const markupFromSales=()=>{if(syncing)return;syncing=true;const p=Math.max(0,num(purchase?.value)),s=Math.max(0,num(sales?.value));if(markup)markup.value=p>0?(((s-p)/p)*100).toFixed(2):"0";syncing=false;render()};
    const initialPurchase=Math.max(0,num(purchase?.value)),initialSales=Math.max(0,num(sales?.value));
    if(initialSales>0)markupFromSales();else if(initialPurchase>0)salesFromMarkup();else render();
    quantity?.addEventListener("input",render);purchase?.addEventListener("input",salesFromMarkup);markup?.addEventListener("input",salesFromMarkup);sales?.addEventListener("input",markupFromSales);
  }

  const layout=document.querySelector("[data-ab-v3-layout-form]");
  if(layout){
    const preview=layout.querySelector("[data-ab-v3-layout-preview]"),logoShow=layout.querySelector('[name="logo_show"]'),logoPosition=layout.querySelector('[name="logo_position"]'),logoSize=layout.querySelector('[name="logo_size"]'),senderShow=layout.querySelector('[name="sender_line_show"]'),footerShow=layout.querySelector('[name="footer_show"]');
    const logoWrap=preview?.querySelector("[data-ab-preview-logo-wrap]"),logoNode=preview?.querySelector("[data-ab-preview-logo]"),senderNode=preview?.querySelector("[data-ab-preview-sender]"),footerNode=preview?.querySelector("[data-ab-preview-footer]");
    const logoOwner=logoShow?.closest(".tt-three")||logoShow?.closest("label");
    if(preview&&logoOwner&&!layout.querySelector(".abtt-layout-stage")){const stage=document.createElement("div"),controls=document.createElement("div");stage.className="abtt-layout-stage";controls.className="abtt-layout-controls";logoOwner.before(stage);controls.appendChild(logoOwner);stage.appendChild(controls);stage.appendChild(preview)}
    const applyPreview=()=>{if(logoWrap){logoWrap.style.display=logoShow&&!logoShow.checked?"none":"flex";const p=logoPosition?.value||"right";logoWrap.style.justifyContent=p==="left"?"flex-start":p==="center"?"center":"flex-end"}if(logoNode){const s=logoSize?.value||"large";logoNode.style.maxWidth=s==="small"?"84px":s==="medium"?"122px":"160px"}if(senderNode)senderNode.style.display=senderShow&&!senderShow.checked?"none":"block";if(footerNode)footerNode.style.display=footerShow&&!footerShow.checked?"none":"grid"};
    [logoShow,logoPosition,logoSize,senderShow,footerShow].forEach(el=>{el?.addEventListener("input",applyPreview);el?.addEventListener("change",applyPreview)});applyPreview();
    const logoUpload=layout.querySelector('input[type="file"][name*="logo" i]');
    logoUpload?.addEventListener("change",()=>{const file=logoUpload.files?.[0];if(!file||!file.type.startsWith("image/")||!(logoNode instanceof HTMLImageElement))return;logoNode.src=URL.createObjectURL(file)});
  }
})();
