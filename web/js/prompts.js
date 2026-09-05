async function loadPrompt(){const n=$('prList').value;const d=await fetch('/api/prompts/'+encodeURIComponent(n)).then(J);$('prBody').value=d.content;}
async function newPrompt(){const n=$('prNew').value.trim();if(!n)return;
await fetch('/api/prompts/'+encodeURIComponent(n),{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({content:''})}).then(J);loadMeta();}
async function savePrompt(){const n=$('prList').value;
await fetch('/api/prompts/'+encodeURIComponent(n),{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({content:$('prBody').value})}).then(J);
toast('Đã lưu '+n);}
async function renamePrompt(){const o=$('prList').value;
const n=prompt('Tên mới:',o);if(!n||n===o)return;
try{await fetch('/api/prompts/rename',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({old:o,new:n})}).then(J);}
catch(e){toast(e.message,true);return;}
toast('Đã đổi thành '+n);loadMeta();}
async function delPrompt(){const n=$('prList').value;
if(!confirm('Xóa prompt '+n+'?'))return;
try{await fetch('/api/prompts/'+encodeURIComponent(n),{method:'DELETE'}).then(J);}
catch(e){toast(e.message,true);return;}
toast('Đã xóa '+n);loadMeta();}
async function backupPrompt(){const n=$('prList').value,p=$('prProj').value;if(!p){toast('Chọn dự án đích trước.',true);return;}
try{const r=await fetch('/api/projects/'+encodeURIComponent(p)+'/prompt-backup',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:n})}).then(J);
toast('Đã lưu vào '+p+'/'+r.path);}catch(e){toast(e.message,true);}}
async function setDefault(){const n=$('prList').value;
try{await fetch('/api/settings',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({default_prompt:n})}).then(J);
toast('Đã đặt mặc định: '+n);}catch(e){toast(e.message,true);}}
