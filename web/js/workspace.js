// --- File trong workspace: nạp vào editor, liên kết cùng tên (2.5b-sửa) ---
let _wsSrc=null,_wsRes=null;
function wsProj(){return $('wProj').value;}
let _wsTab='sources';
const _sel=new Set();  // selection theo tên file (sống qua filter, reset khi đổi tab/project)
const _flt={sortBy:'name',sortOrder:'asc',keyword:''};
let _lists={sources:[],results:[]};
function wsTab(t){_wsTab=t;_sel.clear();listFiles();}
function applyFlt(names){let r=names.slice();
const kw=_flt.keyword.toLowerCase().trim();
if(kw)r=r.filter(f=>f.toLowerCase().includes(kw));
r.sort((a,b)=>{let c=0;
if(_flt.sortBy==='ext'){const ea=(a.split('.').pop()||'').toLowerCase(),eb=(b.split('.').pop()||'').toLowerCase();
c=ea.localeCompare(eb,'vi');if(!c)c=a.localeCompare(b,'vi');}
else c=a.localeCompare(b,'vi');
return _flt.sortOrder==='desc'?-c:c;});
return r;}
async function listFiles(){const s=wsProj();if(!s)return;
const d=await fetch(`/api/projects/${encodeURIComponent(s)}/files`).then(J);
_lists={sources:d.sources||[],results:d.results||[]};
$('wTabSrc').className='btn'+(_wsTab==='sources'?' pri':'');
$('wTabRes').className='btn'+(_wsTab==='results'?' pri':'');
const names=applyFlt(_wsTab==='sources'?d.sources:d.results);
const other=new Set(_wsTab==='sources'?d.results:d.sources);
$('wFileList').innerHTML=names.map(f=>wsRow(f,other.has(f))).join('')
||(_flt.keyword?'<p>Không có file nào khớp lọc.</p>':'<p>Trống.</p>');
updSelUI();}
function wsRow(f,paired){const e=encodeURIComponent(f);
const on=f===_wsSrc||f===_wsRes?' on':'';
return `<div class="pfile${on}"><span class="dot${paired?'':' off'}" title="${paired?'Đã có cặp cùng tên':'Chưa có cặp'}"></span>`
+`<input type="checkbox" class="wSel" value="${e}"${_sel.has(f)?' checked':''} onchange="wsTog('${e}',this.checked)"> `
+`<span class="fname" title="${esc(f)}" onclick="wsOpen('${e}')">${esc(f)}</span></div>`;}
function updSelUI(){const boxes=[...document.querySelectorAll('#wFileList .wSel')];
const vis=boxes.filter(x=>_sel.has(decodeURIComponent(x.value)));
$('wSelAll').checked=boxes.length>0&&vis.length===boxes.length;
const all=_wsTab==='sources'?_lists.sources:_lists.results;
const shown=new Set(applyFlt(all));
const hid=[..._sel].filter(f=>!shown.has(f)).length;
$('wSelCount').textContent=_sel.size?`${_sel.size} đã chọn`+(hid?` (${hid} ẩn bởi filter)`:''):'';
updFileInfo();}
function wsTog(ef,on){const f=decodeURIComponent(ef);if(on)_sel.add(f);else _sel.delete(f);updSelUI();}
function wsSelAll(){const boxes=[...document.querySelectorAll('#wFileList .wSel')];
const allOn=boxes.length>0&&boxes.every(x=>x.checked);
boxes.forEach(x=>{const f=decodeURIComponent(x.value);if(allOn)_sel.delete(f);else _sel.add(f);x.checked=!allOn;});
updSelUI();}
function wsSel(){return [..._sel];}
function fStats(name,text){const c=text.length,w=text.split(/\s+/).filter(Boolean).length;
return `Tập tin: ${name} | gồm có: ${c.toLocaleString()} ký tự | ${w.toLocaleString()} từ | ước lượng ~${Math.round(c/4).toLocaleString()} tokens`;}
let _wsStats='';
function updFileInfo(){let t=_wsStats||'Chưa chọn tập tin.';
if(_sel.size>1)t+=` | đã chọn ${_sel.size} tập tin.`;
$('wFileInfo').textContent=t;}
function wrapTog(){const off=$('tSrc').classList.toggle('nowrap');$('tOut').classList.toggle('nowrap',off);
try{localStorage.setItem('ct_wrap',off?'0':'1');}catch(e){}}
$('tOut').addEventListener('paste',e=>{  // chỉ chèn plain-text, chặn rác rich-text
e.preventDefault();
const text=(e.clipboardData||window.clipboardData).getData('text/plain');
document.execCommand('insertText',false,text);});
async function wsOpen(ef){const f=decodeURIComponent(ef),p=wsProj();if(!p)return;
_wsStats='';
try{const s=await fetch(`/api/projects/${encodeURIComponent(p)}/file?filename=${encodeURIComponent(f)}&side=sources`).then(J);
_wsSrc=f;$('tSrc').textContent=s.content;
_wsStats=fStats(f,s.content);}catch(e){_wsSrc=null;}
try{const r=await fetch(`/api/projects/${encodeURIComponent(p)}/file?filename=${encodeURIComponent(f)}&side=results`).then(J);
_wsRes=f;$('tOut').textContent=r.content;
if(!_wsStats)_wsStats=fStats(f,r.content);}catch(e){_wsRes=null;$('tOut').textContent='';toast('Chưa có kết quả — bấm Gửi AI.');}
_fMatches=[];updFileInfo();listFiles();}
function wsPick(){$('wFileInput').click();}
async function loadProfiles(){
try{const d=await fetch('/api/profiles').then(J);
$('wProfile').innerHTML='<option value="">— Profile —</option>'+d.profiles.map(p=>
`<option value="${esc(p.file)}" title="${esc(p.description||'')}">${esc(p.name)}</option>`).join('');}catch(e){}}
async function applyProfile(){const f=$('wProfile').value;if(!f)return;
try{const d=await fetch('/api/profiles').then(J);
const p=d.profiles.find(x=>x.file===f);if(!p)return;
const opts=[...$('wPrompt').options].map(o=>o.value);
if(p.prompt&&opts.includes(p.prompt))$('wPrompt').value=p.prompt;
document.querySelectorAll('#wExtra input').forEach(x=>{x.checked=(p.extra_prompts||[]).includes(x.value);});
updExtraEst();toast('Đã nạp profile: '+p.name);}catch(e){toast(e.message,true);}}
async function wsUpload(files){const p=wsProj();if(!p||!files.length)return;let ok=0,fail=0;const saved=[];
for(const f of files){try{const r=await fetch(`/api/projects/${encodeURIComponent(p)}/upload?filename=${encodeURIComponent(f.name)}&side=${_wsTab}`,{method:'POST',body:f}).then(J);
saved.push(r.filename);ok++;}catch(e){fail++;}}
$('wUpMsg').textContent=`Đã tải ${ok} file${fail?`, lỗi ${fail}`:''}.`+(saved.length===1&&saved[0]!==files[0].name?` Lưu thành ${saved[0]} (trùng tên).`:'');
$('wFileInput').value='';
listFiles();listProjects();}
async function wsDelOne(f){const p=wsProj();
try{await fetch(`/api/projects/${encodeURIComponent(p)}/files?filename=${encodeURIComponent(f)}`,{method:'DELETE'}).then(J);}
catch(e){toast(e.message,true);return false;}
if(_wsSrc===f)_wsSrc=null;if(_wsRes===f)_wsRes=null;_sel.delete(f);return true;}
async function wsDelSel(){const fs=wsSel(),p=wsProj();if(!fs.length){toast('Chọn file trước.');return;}
if(!confirm(`Xóa ${fs.length} file (cả cặp cùng tên nếu có)?`))return;
for(const f of fs){await wsDelOne(f).catch(e=>toast(f+': '+e.message,true));}
listFiles();listProjects();}
async function wsRenameOne(f,newName){const p=wsProj();
const r=await fetch(`/api/projects/${encodeURIComponent(p)}/rename`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({old:f,new:newName})}).then(J);
const got=r.renames&&r.renames.length?r.renames[0].new:r.filename;
if(_wsSrc===f)_wsSrc=got;if(_wsRes===f)_wsRes=got;
return r;}
async function wsRenameSel(){const fs=wsSel();if(!fs.length){toast('Chọn file trước.');return;}
if(fs.length===1){const f=fs[0];
const n=prompt('Tên mới:',f);if(!n||n===f)return;
try{const r=await wsRenameOne(f,n);
const got=r.renames&&r.renames.length?r.renames[0].new:r.filename;
toast(got===n?'Đã đổi tên.':`Tên đã tồn tại, đã lưu thành ${got}.`);}catch(e){toast(e.message,true);return;}
listFiles();return;}
rnOpen(fs);}
// sync-scroll dual-pane
$('tSrc').onscroll=()=>{$('tOut').scrollTop=$('tSrc').scrollTop;};
$('tOut').onscroll=()=>{$('tSrc').scrollTop=$('tOut').scrollTop;};
let lastSSE=[];
async function startTl(){if(!_wsSrc){$('wMsg').innerHTML='<span class=err>Chọn file nguồn ở cột trái trước.</span>';return;}
const body={project:wsProj(),file:_wsSrc,provider_id:$('wProv').value,
model:curModel()||undefined,prompt:$('wPrompt').value,
extra_prompts:[...document.querySelectorAll('#wExtra input:checked')].map(x=>x.value)};
$('wMsg').textContent='⏳ Đang dịch…';$('tOut').textContent='';lastSSE=[];
setRunning(true);
tlog(`Gửi AI: ${_wsSrc} @ ${$('wProv').selectedOptions[0].textContent}/${curModel()} [${$('wPrompt').value}]`);
clearInterval(window._progT);window._progT0=Date.now();window._progLast=null;
window._progT=setInterval(()=>{if(window._progLast)progPaint();},1000);
const r=await fetch('/api/translate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
if(r.status===409){$('wMsg').innerHTML='<span class=err>Đang có 1 phiên chạy.</span>';setRunning(false);return}
if(!r.ok){const j=await r.json();$('wMsg').innerHTML='<span class=err>'+j.error+'</span>';setRunning(false);return}
function progPaint(){const j=window._progLast;if(!j)return;
const s=Math.round((Date.now()-window._progT0)/1000);
$('wProg').textContent=`chunk ${j.i}/${j.n} · attempt ${j.attempt} · key ${j.key}/${j.keys}`+(j.file?` · ${j.file}`:'')+` · đã chờ ${s}s`;}
const res0=await readSSE(r,{
onChunk:j=>{lastSSE[j.i-1]=j.text;$('tOut').textContent=lastSSE.filter(Boolean).join('\n\n');$('wMsg').textContent=`⏳ chunk ${j.i}/${j.n} xong`;},
onProgress:j=>{window._progLast=j;progPaint();},
onDone:d=>{clearInterval(window._progT);setRunning(false);$('wMsg').textContent='🎉 Xong! Bấm Lưu Vào File.';tlog(`Xong ${_wsSrc} — bấm Lưu để ghi results/.`,'ok');
const w=(d&&d.warnings||[]).filter(x=>x.warnings&&x.warnings.length);
if(w.length){const t=`⚠️ Cảnh báo output: ${w.map(x=>`chunk ${x.i} (${x.warnings.join(',')})`).join('; ')} — chỉ cảnh báo, không tự sửa.`;
$('wMsg').innerHTML+='<br><span class=err>'+esc(t)+'</span>';tlog(t,'err');}},
onError:j=>{clearInterval(window._progT);setRunning(false);
if(j.cancelled){$('wMsg').textContent='⏹ Đã hủy — không ghi output dở.';tlog('Đã hủy phiên (nháp giữ trên editor).');}
else {$('wMsg').innerHTML='<span class=err>'+esc(j.error)+'</span>';tlog(`LỖI: ${j.error}`,'err');}}});}
function copyTl(){navigator.clipboard.writeText($('tOut').textContent);$('wMsg').textContent='📋 Đã copy.'}
// terminal log hệ thống (ô đen dưới editor)
function tlog(msg,cls){const t=$('wTerm');if(!t)return;
const d=document.createElement('div');if(cls)d.className=cls;
d.textContent=`[${new Date().toLocaleTimeString('vi-VN')}] ${msg}`;
t.appendChild(d);while(t.children.length>200)t.removeChild(t.firstChild);
t.scrollTop=t.scrollHeight;}
// Gửi AI: 1 nút, 2 chế độ (gộp-chia-chunk / tuần tự) — tối ưu limit ngày/giờ
let _sendFiles=[];
async function sendOpen(){const fs=wsSel(),p=wsProj();if(!fs.length){toast('Chọn file ở cột Tập tin trước.');return;}
if(_wsTab!=='sources'){toast('Chuyển tab Nguồn để gửi AI.',true);return;}
_sendFiles=fs.slice();
let total=0;for(const f of fs){try{const d=await fetch(`/api/projects/${encodeURIComponent(p)}/file?filename=${encodeURIComponent(f)}&side=sources`).then(J);
total+=d.content.length;}catch(e){toast('Không đọc được '+f+': '+e.message,true);return;}}
const max=+$('sMax').value||16000,est=Math.max(1,Math.ceil(total/max));
window._sendTotal=total;window._sendMax=max;
$('sendCount').textContent=`${fs.length} file`;
$('sendInfo').textContent=`${fs.join(', ')} — ${total.toLocaleString()} ký tự, ~${est} chunk.`
+` Provider: ${$('wProv').selectedOptions[0].textContent}, model: ${curModel()||'(chưa chọn)'}, prompt: ${$('wPrompt').value}.`
+(est>2?' ⚠️ Quá 2 chunk dễ giảm chất lượng.':'');
const mMerge=document.querySelector('input[name=sendMode][value=merge]');
const mSeq=document.querySelector('input[name=sendMode][value=seq]');
if(fs.length<2){mMerge.disabled=true;mSeq.checked=true;
$('sendInfo').textContent+=` Chỉ 1 file${total<=max?' (dưới ngưỡng chia chunk)':''} → dịch trực tiếp, không gộp.`;}
else{mMerge.disabled=false;}
sendDlg.showModal();}
async function sendGo(){const mode=document.querySelector('input[name=sendMode]:checked').value;
sendDlg.close();const fs=_sendFiles.slice();
if(mode==='merge'&&fs.length<2){tlog(`1 file (${(window._sendTotal||0).toLocaleString()} ký tự) → bỏ qua gộp, dịch trực tiếp.`);wsBulkTranslate(fs,true);return;}
if(mode==='merge')wsMergeTranslate(fs,true);else wsBulkTranslate(fs,true);}
async function saveTl(){const f=_wsRes||_wsSrc;if(!f)return;
await fetch('/api/save',{method:'POST',headers:{'Content-Type':'application/json'},
body:JSON.stringify({project:wsProj(),file:f,content:$('tOut').textContent})}).then(J);
$('wMsg').textContent='💾 Đã lưu vào results/'+f+'.';tlog(`Đã lưu results/${f} (ghi đè chủ đích).`,'ok');listFiles();}
function retryTl(){startTl()}function clearTl(){$('tOut').textContent='';startTl()}
async function cancelTl(){if(!confirm('Hủy phiên dịch đang chạy? Output dở không được ghi.'))return;
try{await fetch('/api/translate/cancel',{method:'POST'}).then(J);
toast('Đã gửi lệnh hủy.');tlog('Đã gửi lệnh hủy (cắt cả request đang bay).');}
catch(e){toast(e.message,true);}}
function setRunning(b){document.querySelectorAll('[data-act]').forEach(x=>{x.disabled=!!b;});
const s=$('wSendBtn');if(s)s.disabled=!!b;}
// bulk dịch tuần tự (gọi từ dialog Gửi AI; confirmed=true bỏ confirm riêng)
async function wsBulkTranslate(fs,inConfirmed){const p=wsProj();
if(!fs||!fs.length){toast('Chọn file trước.');return;}
if(_wsTab!=='sources'){toast('Chuyển tab Nguồn để dịch.',true);return;}
if(!inConfirmed&&!confirm(`Dịch tuần tự ${fs.length} file? Lỗi thì dừng cả loạt.`))return;
setRunning(true);
const prov=$('wProv').value,model=curModel()||undefined,prompt=$('wPrompt').value;
const extra=[...document.querySelectorAll('#wExtra input:checked')].map(x=>x.value);
const skipErr=$('sendSkipErr')&&$('sendSkipErr').checked;
const failed=[];
try{const pv=await fetch('/api/settings/providers').then(J);
const pi=(pv.providers||[]).find(x=>x.id===prov);
const nk=pi?((pi.api_keys||[]).length||(pi.api_key?1:0)):0;
tlog(`🔑 ${nk} API key · ${prov}/${model||'(mặc định)'} · prompt ${prompt}`+(extra.length?` +${extra.length} bổ sung`:'')+`.`);
}catch(e){}
for(const f of fs){try{const c=await fetch(`/api/chunks?project=${encodeURIComponent(p)}&file=${encodeURIComponent(f)}`).then(J);
tlog(`📄 ${f}: ${(c.chunks.reduce((a,x)=>a+x.chars,0)).toLocaleString()} ký tự (~${c.chunks.length} chunk).`);}catch(e){}}
clearInterval(window._progT);window._progT0=Date.now();window._progLast=null;
window._progT=setInterval(()=>{if(window._progLast)progPaint();},1000);
const doneOk=[];
for(let k=0;k<fs.length;k++){const f=fs[k];
$('wBulkMsg').textContent=`⏳ file ${k+1}/${fs.length}: ${f}`;
tlog(`file ${k+1}/${fs.length}: ${f}…`);
const r=await fetch('/api/translate',{method:'POST',headers:{'Content-Type':'application/json'},
body:JSON.stringify({project:p,file:f,provider_id:prov,model,prompt,extra_prompts:extra})});
if(!r.ok){const j=await r.json();
if(skipErr){failed.push(f);tlog(`Bỏ qua ${f}: ${j.error}`,'err');continue;}
$('wBulkMsg').innerHTML='<span class=err>Dừng ở '+esc(f)+': '+esc(j.error)+'</span>';tlog(`LỖI ở ${f}: ${j.error}`,'err');clearInterval(window._progT);setRunning(false);return;}
const textsB=[];
const resB=await readSSE(r,{onChunk:j=>{textsB[j.i-1]=j.text;
tlog(`✅ chunk ${j.i}/${j.n} xong (${f}).`);},
onProgress:j=>{window._progLast=j;progPaint();}});
if(resB.error){const ce=resB.error.cancelled?'Đã hủy':resB.error.error||resB.error;
if(skipErr&&!resB.error.cancelled){failed.push(f);tlog(`Bỏ qua ${f}: ${ce}`,'err');continue;}
$('wBulkMsg').innerHTML='<span class=err>Dừng ở '+esc(f)+': '+esc(ce)+'</span>';tlog(`Dừng ở ${f}: ${ce}`,'err');clearInterval(window._progT);setRunning(false);return;}
await fetch('/api/save',{method:'POST',headers:{'Content-Type':'application/json'},
body:JSON.stringify({project:p,file:f,content:textsB.filter(Boolean).join('\n\n')})}).then(J);
doneOk.push(f);
tlog(`💾 ${f} → results/ (${textsB.filter(Boolean).length} chunk).`);}
clearInterval(window._progT);
$('wBulkMsg').textContent=`🎉 Xong ${fs.length-failed.length}/${fs.length} file.`+(failed.length?` Bỏ qua: ${failed.join(', ')}.`:'');
tlog(`Hoàn tất tuần tự (${failed.length?`bỏ qua ${failed.join(', ')}`:'đủ'}).`);
setRunning(false);listFiles();
if(doneOk.length){await wsOpen(encodeURIComponent(doneOk[doneOk.length-1]));
toast(`Đã nạp kết quả: ${doneOk[doneOk.length-1]}`);}}
// gộp nhiều file -> 1 phiên, server tách đúng về từng file (gọi từ dialog Gửi AI)
async function wsMergeTranslate(fs,inConfirmed){const p=wsProj();
if(!fs||!fs.length){toast('Chọn file trước.');return;}
if(_wsTab!=='sources'){toast('Chuyển tab Nguồn để gộp dịch.',true);return;}
const prov=$('wProv').value,model=curModel()||undefined,prompt=$('wPrompt').value;
const extra=[...document.querySelectorAll('#wExtra input:checked')].map(x=>x.value);
$('wBulkMsg').textContent=`⏳ Đang gộp dịch ${fs.length} file…`;$('tOut').textContent='';
setRunning(true);
try{const pv=await fetch('/api/settings/providers').then(J);
const pi=(pv.providers||[]).find(x=>x.id===prov);
const nk=pi?((pi.api_keys||[]).length||(pi.api_key?1:0)):0;
tlog(`🔑 ${nk} API key · ${prov}/${model||'(mặc định)'} · prompt ${prompt}`+(extra.length?` +${extra.length} bổ sung`:'')+`.`);
}catch(e){}
let mTotal=0;for(const f of fs){try{const d=await fetch(`/api/projects/${encodeURIComponent(p)}/file?filename=${encodeURIComponent(f)}&side=sources`).then(J);
mTotal+=d.content.length;tlog(`📄 ${f}: ${d.content.length.toLocaleString()} ký tự.`);}catch(e){}}
try{const c=await fetch('/api/settings').then(J);
const mx=+c.max_chunk_chars||window._sendMax||16000;
tlog(`🧩 Gộp ${fs.length} file, tổng ~${mTotal.toLocaleString()} ký tự (~${Math.max(1,Math.ceil(mTotal/mx))} chunk, ngưỡng ${mx.toLocaleString()}).`);}catch(e){
tlog(`Bắt đầu gộp ${fs.length} file: ${fs.join(', ')}`);}
clearInterval(window._progT);window._progT0=Date.now();window._progLast=null;
window._progT=setInterval(()=>{if(window._progLast)progPaint();},1000);
const r=await fetch('/api/translate/merge',{method:'POST',headers:{'Content-Type':'application/json'},
body:JSON.stringify({project:p,files:fs,provider_id:prov,model,prompt,extra_prompts:extra})});
if(!r.ok){const j=await r.json();$('wBulkMsg').innerHTML='<span class=err>'+esc(j.error)+'</span>';tlog(`LỖI gộp: ${j.error}`,'err');clearInterval(window._progT);setRunning(false);return;}
const texts=[];
const resM=await readSSE(r,{
onChunk:j=>{texts[j.i-1]=j.text;$('tOut').textContent=texts.filter(Boolean).join('\n\n');
const lbl=`⏳ chunk ${j.i}/${j.n}`+(j.files&&j.files.length>1?` · ${j.files.join('+')}`:(j.file?` · ${j.file}`:''));
$('wBulkMsg').textContent=lbl;tlog(lbl);},
onProgress:j=>{window._progLast=j;progPaint();}});
if(resM.error){const ce=resM.error.cancelled?'Đã hủy':(resM.error.error||resM.error);
$('wBulkMsg').innerHTML='<span class=err>'+esc(ce)+'</span>';tlog(`Dừng gộp: ${ce}`,'err');clearInterval(window._progT);setRunning(false);return;}
const saved=resM.done&&resM.done.files?resM.done.files:[];
$('wBulkMsg').textContent=`🎉 Gộp xong → results/: ${saved.map(x=>x.file).join(', ')||fs.join(', ')}.`;
tlog(`Hoàn tất gộp: ${saved.map(x=>`${x.file} (${x.chars} ký tự)`).join(', ')}.`);
const mw=saved.filter(x=>x.warnings&&x.warnings.length);
if(mw.length)tlog(`⚠️ Cảnh báo: ${mw.map(x=>`${x.file} (${x.warnings.join(',')})`).join('; ')}.`,'err');
if(saved.length){_wsSrc=null;_wsRes=saved[0].file;
try{const d=await fetch(`/api/projects/${encodeURIComponent(p)}/file?filename=${encodeURIComponent(saved[0].file)}&side=results`).then(J);
$('tOut').textContent=d.content;}catch(e){}}
clearInterval(window._progT);
setRunning(false);listFiles();listProjects();}
// --- Batch rename: preview + xác nhận (không auto-sync, không ghi đè) ---
let _rnFiles=[];
function rnOpen(fs){_rnFiles=fs.slice();
const m=fs[0].match(/^(.*?)(\d+)(.*)$/);
if(m){$('rnPat').value=m[1]+'{N}'+m[3];$('rnStart').value=parseInt(m[2],10);$('rnPad').value=m[2].length;}
else{$('rnPat').value='{N}';$('rnStart').value=1;$('rnPad').value=2;}
rnPreview();rnDlg.showModal();}
function rnPlan(){const pat=$('rnPat').value,start=+$('rnStart').value||0,pad=+$('rnPad').value||0;
return _rnFiles.map((old,idx)=>{
const num=String(start+idx).padStart(pad,'0');
let nw=pat.split('{N}').join(num);
if(!nw.includes('.')&&old.includes('.'))nw=nw+'.'+old.split('.').pop();
return {old,new:nw};});}
function rnPreview(){const pat=$('rnPat').value;
const side=_wsTab,cur=new Set(side==='sources'?_lists.sources:_lists.results);
const other=new Set(side==='sources'?_lists.results:_lists.sources);
const plan=rnPlan();
const counts={};plan.forEach(r=>{counts[r.new]=(counts[r.new]||0)+1;});
let shape=true;
if(pat.includes('{N}')){const t=pat.split('{N}').join('0');
if(!t.trim()||/[\\/]/.test(t)||t.includes('..'))shape=false;}
let html='';
plan.forEach(r=>{
const dupBatch=counts[r.new]>1,exists=cur.has(r.new),pair=other.has(r.old);
const st=!pat.includes('{N}')?'thiếu {N}':(dupBatch?'trùng trong batch':(exists?'đã tồn tại':(pair?'có cặp bên kia':'ok')));
html+=`<div class="${(!pat.includes('{N}')||dupBatch||exists)?'bad':'ok'}">${esc(r.old)} → ${esc(r.new)} <i>(${st})</i></div>`;});
$('rnPrev').innerHTML=html;
$('rnCount').textContent=`File đã chọn (${_rnFiles.length} file)`;
$('rnGo').disabled=!pat.includes('{N}')||!_rnFiles.length||!shape;}
async function rnExec(){const p=wsProj();
const r=await fetch(`/api/projects/${encodeURIComponent(p)}/rename-batch`,{method:'POST',
headers:{'Content-Type':'application/json'},body:JSON.stringify({side:_wsTab,
pattern:$('rnPat').value,start:+$('rnStart').value||0,zeropad:+$('rnPad').value||0,
old_names:_rnFiles})}).then(J).catch(e=>{toast(e.message,true);return null;});
if(!r)return;
const bad=r.results.filter(x=>!x.ok);
toast(`Đã đổi ${r.renamed}/${_rnFiles.length} file.`+(bad.length?` Lỗi: ${bad.map(x=>x.old).join(', ')}.`:''));
_sel.clear();rnDlg.close();listFiles();}
// --- Bộ lọc hiển thị (client-side, giữ khi đổi tab, reset khi đổi project) ---
function fltToggle(ev){ev.stopPropagation();const p=$('fltPanel');p.style.display=p.style.display==='none'?'block':'none';}
function fltSet(){const s=document.querySelector('input[name=fltSort]:checked'),o=document.querySelector('input[name=fltOrd]:checked');
if(s)_flt.sortBy=s.value;if(o)_flt.sortOrder=o.value;_flt.keyword=$('fltKw').value;listFiles();}
document.addEventListener('click',e=>{const p=$('fltPanel');if(!p||p.style.display==='none')return;
if(!e.target.closest('#fltPanel')&&!e.target.closest('#fltToolBtn'))p.style.display='none';});
document.addEventListener('keydown',e=>{if(e.key==='Escape'){const p=$('fltPanel');if(p)p.style.display='none';}});
