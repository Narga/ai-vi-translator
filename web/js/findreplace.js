// --- Tìm/thay thế kiểu Sigil: regex, hoa/thường, cả từ, $1 backref ---
let _fMatches=[],_fIdx=-1;
function fPane(){return $($('fTarget').value==='tSrc'?'tSrc':'tOut');}
function fMsg(t){$('fMsg').textContent=t;}
function fBuild(){const pat=$('fFind').value;
if(!pat){fMsg('Nhập mẫu tìm.');return null;}
let src=$('fRegex').checked?pat:pat.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
if($('fWord').checked)src='\\b(?:'+src+')\\b';
try{return new RegExp(src,'g'+($('fCase').checked?'':'i')+'u');}
catch(e){fMsg('Regex lỗi: '+e.message);return null;}}
function fPaint(cur){const pane=fPane(),text=pane.textContent,re=fBuild();if(!re)return false;
_fMatches=[...text.matchAll(re)].filter(m=>m[0].length>0);
if(_fIdx>=_fMatches.length)_fIdx=_fMatches.length-1;
let html='',last=0;
_fMatches.forEach((m,i)=>{html+=esc(text.slice(last,m.index))
+`<mark data-i="${i}"${i===cur?' class="cur"':''}>${esc(m[0])}</mark>`;last=m.index+m[0].length;});
html+=esc(text.slice(last));
pane.innerHTML=html;
const marks=pane.querySelectorAll('mark');
if(cur>=0&&marks[cur])marks[cur].scrollIntoView({block:'nearest'});
fMsg(_fMatches.length?`${_fMatches.length} kết quả — ${cur+1}/${_fMatches.length}`:'Không thấy.');
return true;}
function fNext(dir){if(!fPaint(_fIdx<0?0:_fIdx))return;
if(!_fMatches.length)return;
_fIdx=(_fIdx+dir+_fMatches.length)%_fMatches.length;fPaint(_fIdx);}
function fPlain(){const pane=fPane(); // gỡ mark, giữ nguyên text + caret
pane.querySelectorAll('mark').forEach(m=>m.replaceWith(document.createTextNode(m.textContent)));
pane.normalize();return pane.textContent;}
function fReplace(){const pane=fPane();if(!fPaint(Math.max(_fIdx,0)))return;
if(!_fMatches.length||_fIdx<0)return;
const m=_fMatches[_fIdx],text=fPlain(),single=new RegExp(fBuild().source,fBuild().flags.replace('g',''));
const rep=m[0].replace(single,$('fRepl').value);
pane.textContent=text.slice(0,m.index)+rep+text.slice(m.index+m[0].length);
_fIdx=-1;fPaint(0);}
function fReplaceAll(){if($('fScope').value!=='one'){fReplaceAllScope();return;}
const pane=fPane(),re=fBuild();if(!re)return;
const text=fPlain(),ms=[...text.matchAll(re)].filter(m=>m[0].length>0);
pane.textContent=text.replace(re,$('fRepl').value);
_fMatches=[];_fIdx=-1;fMsg(`Đã thay ${ms.length} chỗ.`);}
async function fReplaceAllScope(){const scope=$('fScope').value,p=wsProj();
if(!p){fMsg('Chọn dự án trước.');return;}
const d=await fetch(`/api/projects/${encodeURIComponent(p)}/files`).then(J);
const n=(scope==='sources'?d.sources:d.results).length;
if(!n||!confirm(`Thay hết trong ${n} file ${scope}? Không hoàn tác được.`))return;
try{const r=await fetch('/api/find-replace',{method:'POST',headers:{'Content-Type':'application/json'},
body:JSON.stringify({project:p,side:scope,pattern:$('fFind').value,repl:$('fRepl').value,
regex:$('fRegex').checked,case:$('fCase').checked,word:$('fWord').checked})}).then(J);
fMsg(`Đã thay ${r.total} chỗ trong ${Object.keys(r.files).length} file.`);
if(_wsSrc)wsOpen(encodeURIComponent(_wsSrc));listFiles();}
catch(e){fMsg(e.message);}}
$('tOut').addEventListener('input',()=>{if($('fTarget').value==='tOut'&&_fMatches.length){fPlain();_fMatches=[];_fIdx=-1;}});
