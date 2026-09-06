async function loadMeta(){const s=await fetch('/api/settings').then(J);
try{const h=await fetch('/api/health').then(J);
$('srvInfo').textContent=h.version+' · từ '+(h.started_at||'').slice(11);}
catch(e){$('srvInfo').textContent='mất kết nối?';}
$('sMax').value=s.max_chunk_chars;$('sDelay').value=s.api_delay_seconds;$('sTimeout').value=s.timeout_seconds;
$('sThink').innerHTML=s.thinking_levels.map(l=>`<option>${l}</option>`).join('');
const pv=await fetch('/api/settings/providers').then(J);
function safeHref(u){
  if(typeof u!=="string")return "#";
  const t=u.trim();
  return /^https?:\/\//i.test(t)?t:"#";
}
$('wProv').innerHTML=pv.providers.map(p=>`<option value="${esc(p.id)}" ${p.id===pv.active_id?'selected':''}>${esc(p.name)}</option>`).join('');
$('sProvSel').innerHTML=pv.providers.map(p=>`<option value="${esc(p.id)}" ${p.id===pv.active_id?'selected':''}>${esc(p.name)}${p.id===pv.active_id?' ★':''}</option>`).join('');
$('sActive').textContent='active: '+pv.active_id;window._PV=pv;
await fillModels();
const pr=await fetch('/api/prompts').then(J);
const dp=s.default_prompt||'default_translation.txt';
const prSorted=pr.prompts.slice().sort((a,b)=>(a===dp?-1:0)-(b===dp?-1:0)||a.localeCompare(b,'vi'));
const prOpt=prSorted.map(p=>`<option value="${esc(p)}">${p===dp?'✓ ':''}${esc(p)}</option>`).join('');
$('wPrompt').innerHTML=prOpt;
if(s.default_prompt_missing)toast('Prompt mặc định '+dp+' không còn file!',true);
$('wExtra').innerHTML=pr.prompts.map(p=>`<label><input type="checkbox" value="${esc(p)}"> ${esc(p)}</label>`).join('');
$('prList').innerHTML=prOpt;updExtraEst();}
const _plenCache={};
async function plen(name){if(_plenCache[name]==null){
try{const d=await fetch('/api/prompts/'+encodeURIComponent(name)).then(J);_plenCache[name]=d.content.length;}
catch(e){_plenCache[name]=0;}}return _plenCache[name];}
async function updExtraEst(){const base=await plen($('wPrompt').value);let ex=0,n=0;
for(const x of document.querySelectorAll('#wExtra input:checked')){ex+=await plen(x.value);n++;}
$('wExtraEst').textContent=`Prompt chính ${base} + bổ sung ${ex} ≈ ${base+ex} ký tự/chunk.`;
const b=$('wExtraBtn');if(b)b.textContent=n?`+prompts (${n})`:'+prompts';}
// --- Model list dùng chung: lọc client-side, badge free, giữ selection ---
window._Models={};
function filterList(list,kw,mode){kw=(kw||'').toLowerCase().trim();if(!kw)return list;
return list.filter(m=>{const t=((m.id||'')+' '+(m.name||'')).toLowerCase();const hit=t.includes(kw);
return mode==='exclude'?!hit:hit;});}
function optHtml(list,selected){return list.map(m=>{const id=m.id||m;
const free=(m.is_free||/free/i.test(id))?' 🆓':'';
return `<option value="${id}" ${id===selected?'selected':''}>${m.name||id}${free}</option>`;}).join('')
+`<option value="__custom__">…tự nhập…</option>`;}
async function fetchModels(pid){const m=await fetch('/api/settings/models?provider_id='+encodeURIComponent(pid)).then(J);
window._Models[pid]=m;return m;}
async function fillModels(){const pid=$('wProv').value;if(!pid)return;
const m=window._Models[pid]||await fetchModels(pid);
renderWorkspaceModels();}
function renderWorkspaceModels(){const pid=$('wProv').value;const m=window._Models[pid];if(!m)return;
const list=filterList(m.models,$('wFilter').value,$('wFilterMode').value);
let cur=$('wModel').value;if(cur==='__custom__')cur=$('wCustom').value;
if(!list.some(x=>(x.id||x)===cur))cur=m.selected_model;
$('wModel').innerHTML=optHtml(list,cur);
if(cur&&!list.some(x=>(x.id||x)===cur)&&cur!==m.selected_model){$('wModel').value='__custom__';$('wCustom').value=cur;}
$('wModel').onchange=()=>{$('wCustom').style.display=$('wModel').value==='__custom__'?'':'none'};}
$('wProv').onchange=fillModels;
function curModel(){return $('wModel').value==='__custom__'?$('wCustom').value.trim():$('wModel').value;}
// --- Trang cấu hình mới (providers.json SSOT, model live) ---
function curProv(){return (window._PV.providers||[]).find(p=>p.id===$('sProvSel').value);}
function selOrCustom(){return $('sModelSel').value==='__custom__'?$('sModel').value.trim():$('sModelSel').value;}
async function loadProvDetail(){const p=curProv();if(!p)return;
$('sPName').textContent=p.name+' ('+p.type+')';
const keys=p.api_keys||(p.api_key?[p.api_key]:[]);
$('sKeys').value=keys.join('\n');
$('sBaseRow').style.display=p.type==='openai'?'':'none';
$('sBase').value=p.base_url||'';$('sDocs').value=p.docs_url||'';
$('sThink').value=p.thinking||'OFF';
await refreshModels();}
async function refreshModels(){const pid=$('sProvSel').value;
const m=await fetch('/api/settings/models?provider_id='+encodeURIComponent(pid)).then(J);
window._Models[pid]=m;renderSettingsModels();}
function renderSettingsModels(){const pid=$('sProvSel').value;const m=window._Models[pid];if(!m)return;
const p=curProv();
const list=filterList(m.models,$('sFilter').value,$('sFilterMode').value);
const isCustom=p.default_model&&!m.models.some(x=>(x.id||x)===p.default_model);
const sel=isCustom?'__custom__':(m.selected_model||p.default_model);
$('sModelSel').innerHTML=optHtml(list,sel);
if(isCustom)$('sModel').value=p.default_model;else $('sModel').value='';
$('sModel').style.display=$('sModelSel').value==='__custom__'?'':'none';
$('sModelSel').onchange=()=>{const c=$('sModelSel').value==='__custom__';
$('sModel').style.display=c?'':'none';if(!c)loadModelInfo();};
$('sSrc').textContent='nguồn: '+m.source;
$('sWarn').textContent=m.error?('⚠️ '+m.error):'';
loadModelInfo();}
async function loadModelInfo(){const pid=$('sProvSel').value;const model=selOrCustom();if(!model)return;
const d=await fetch(`/api/settings/model-info?provider_id=${encodeURIComponent(pid)}&model=${encodeURIComponent(model)}`).then(J);
const f=n=>n==null?'—':(+n).toLocaleString();
$('mIn').textContent=f(d.input_limit);$('mOut').textContent=f(d.output_limit);
$('mCtx').textContent=f(d.context_length);
const r=d.rate_limits||{};const parts=[];
if(r.usage!=null||r.limit!=null)parts.push(`usage ${r.usage??'—'}/${r.limit??'—'}`);
if(d.quota_url){const h=safeHref(d.quota_url);
parts.push(h==="#"?`quota (link bị chặn)`:`<a href="${esc(h)}" target="_blank" rel="noopener">quota↗</a>`);}
$('mRate').innerHTML=parts.join(' · ')||'—';
if(d.docs_url){const h=safeHref(d.docs_url);
if(h==="#"){$('mDocs').style.display='none';}
else{$('mDocs').style.display='';$('mDocs').href=h;}}else $('mDocs').style.display='none';}
async function saveProvider(){const p=curProv();const isG=p.type==='gemini';
const lines=$('sKeys').value.split('\n').map(s=>s.trim()).filter(Boolean);
const body={provider_id:p.id,selected_model:selOrCustom()||undefined,thinking:$('sThink').value,docs_url:$('sDocs').value.trim()};
if(isG){body.api_keys=lines;}else{body.api_key=lines[0]||'';body.base_url=$('sBase').value.trim();}
try{await fetch('/api/settings/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}).then(J);
$('sMsg').textContent='✅ Đã lưu.';delete window._Models[p.id];loadMeta().then(loadProvDetail);}catch(e){$('sMsg').innerHTML='<span class=err>'+e.message+'</span>';}}
async function setActive(){await fetch('/api/settings/save',{method:'POST',headers:{'Content-Type':'application/json'},
body:JSON.stringify({provider_id:$('sProvSel').value,set_active:true})}).then(J);loadMeta();}
async function addProvider(){const body={name:$('nName').value.trim(),type:$('nType').value,
base_url:$('nBase').value.trim(),api_key:$('nKey').value.trim()};
if(!body.name){$('sMsg').innerHTML='<span class=err>Nhập tên provider.</span>';return;}
const r=await fetch('/api/settings/providers',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}).then(J);
$('sMsg').textContent='✅ Đã thêm '+r.id;loadMeta().then(()=>{$('sProvSel').value=r.id;loadProvDetail();});}
async function delProvider(){const pid=$('sProvSel').value;
if(!confirm('Xóa provider '+pid+'?'))return;
try{await fetch('/api/settings/providers/'+encodeURIComponent(pid),{method:'DELETE'}).then(J);loadMeta().then(loadProvDetail);}
catch(e){$('sMsg').innerHTML='<span class=err>'+e.message+'</span>';}}
async function savePrefs(){await fetch('/api/settings',{method:'PUT',headers:{'Content-Type':'application/json'},
body:JSON.stringify({max_chunk_chars:+$('sMax').value||16000,api_delay_seconds:+$('sDelay').value||0,timeout_seconds:+$('sTimeout').value||90})}).then(J);$('sMsg').textContent='✅ Đã lưu prefs.';}
