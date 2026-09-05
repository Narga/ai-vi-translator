async function mkProject(){const body={title:$('npTitle').value.trim(),author:$('npAuthor').value.trim(),description:$('npDesc').value.trim()};
if(!body.title){toast('Nhập tên sách.',true);return;}
try{const r=await fetch('/api/projects',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}).then(J);
toast('Đã tạo dự án: '+r.slug);}catch(e){toast(e.message,true);return;}
$('npTitle').value=$('npAuthor').value=$('npDesc').value='';projDlg.close();listProjects();}
let _infoSlug=null;
async function openInfo(eslug){const slug=decodeURIComponent(eslug);_infoSlug=slug;
try{const d=await fetch('/api/projects/'+encodeURIComponent(slug)+'/info').then(J);
$('ipTitle').value=d.title||'';$('ipAuthor').value=d.author||'';$('ipDesc').value=d.description||'';}
catch(e){toast(e.message,true);return;}
infoDlg.showModal();}
async function saveInfo(){if(!_infoSlug)return;
try{await fetch('/api/projects/'+encodeURIComponent(_infoSlug)+'/info',{method:'PUT',headers:{'Content-Type':'application/json'},
body:JSON.stringify({title:$('ipTitle').value,author:$('ipAuthor').value,description:$('ipDesc').value})}).then(J);
toast('Đã lưu thông tin.');}catch(e){toast(e.message,true);return;}
infoDlg.close();listProjects();}
async function listProjects(){const d=await fetch('/api/projects').then(J);
$('pCards').innerHTML=d.projects.map(p=>{const e=encodeURIComponent(p.slug);
const n=p.sources||0,m=p.results||0,dn=p.done||0;
const pct=n?Math.min(100,Math.round(dn/n*100)):0;
const title=esc(p.title||p.slug);
return `<div class="pcard"><h3 class="${pct>=100&&n>0?'done':''}">`
+`<svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M3 2h6l4 4v8H3z"/><path d="M9 2v4h4"/></svg> `
+`<span class="pname" onclick="goWS('${e}')" title="Mở workspace">${title}</span></h3>`
+(p.author?`<div class="pauthor">${esc(p.author)}</div>`:'')
+(p.description?`<div class="pdesc">${esc(p.description)}</div>`:'')
+`<div class="row spread"><span><svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M4 2h5l3 3v9H4z"/><path d="M9 2v3h3"/></svg> ${dn}/${n} tập tin</span>`
+`<span><button class="icon-btn" onclick="openInfo('${e}')" title="Sửa thông tin dự án"><svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="8" cy="8" r="6"/><path d="M8 7v4M8 5v.5"/></svg></button> `
+`<button class="icon-btn" onclick="archiveProject('${e}')" title="Nén + lưu trữ dự án vào archive/"><svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M2 5h12v8H2z"/><path d="M2 5l2-2h8l2 2M6 9h4"/></svg></button> `
+`<button class="icon-btn" onclick="delProject('${e}')" title="Xóa toàn bộ dự án"><svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M2 4h12M6 4V2h4v2M4 4l1 10h6l1-10"/></svg></button></span></div>`
+`<div class="row spread"><span>Tiến độ</span><span>${pct}%</span></div>`
+`<div class="pbar"><i style="width:${pct}%"></i></div></div>`;}).join('')
||'<p>Chưa có dự án — tạo ở trên.</p>';
$('wProj').innerHTML=d.projects.map(p=>`<option>${esc(p.slug)}</option>`).join('');
$('prProj').innerHTML=d.projects.map(p=>`<option>${esc(p.slug)}</option>`).join('');
try{const h=await fetch('/api/history?limit=20').then(J);
$('pHist').innerHTML=h.runs.map(r=>`<tr><td>${esc(r.project)}</td><td>${esc(r.file)}</td><td>${esc(r.provider)}/${esc(r.model)}</td><td>${esc(r.status)}${r.error?' — '+esc(r.error.slice(0,80)):''}</td><td>${esc(r.started_at||'')}</td></tr>`).join('')||'<tr><td colspan="5">Chưa có lượt chạy.</td></tr>';}catch(e){}}
function esc(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}
function goWS(eslug){const slug=decodeURIComponent(eslug);document.querySelector('[data-v=workspace]').click();$('wProj').value=slug;listFiles();}
async function delProject(eslug){const slug=decodeURIComponent(eslug);
if(!confirm('Xóa toàn bộ dự án '+slug+'?'))return;
try{await fetch('/api/projects/'+encodeURIComponent(slug),{method:'DELETE'}).then(J);}
catch(e){toast(e.message,true);return;}
listProjects();}
async function archiveProject(eslug){const slug=decodeURIComponent(eslug);
if(!confirm('Nén + lưu trữ toàn bộ dự án '+slug+' vào archive/?'))return;
try{const r=await fetch('/api/projects/'+encodeURIComponent(slug)+'/archive',{method:'POST'}).then(J);
toast('Đã lưu trữ: '+r.path);}catch(e){toast(e.message,true);return;}
listProjects();}
