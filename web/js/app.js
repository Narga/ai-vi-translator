
const $=id=>document.getElementById(id);
document.querySelectorAll('#side [data-v]').forEach(b=>b.onclick=()=>{
document.querySelectorAll('#side [data-v]').forEach(x=>x.classList.remove('on'));
b.classList.add('on');document.querySelectorAll('.view').forEach(v=>v.classList.remove('on'));
$('v-'+b.dataset.v).classList.add('on');try{localStorage.setItem('ct_view',b.dataset.v);}catch(e){}});
try{const _v0=localStorage.getItem('ct_view');
if(_v0){const _t=document.querySelector('#side [data-v="'+_v0+'"]');if(_t)_t.click();}}catch(e){}
$('tog').onclick=()=>$('side').classList.toggle('mini');
const J=r=>{if(!r.ok)return r.json().then(j=>{throw new Error(j.error||r.status)});return r.json()};

// toast dùng chung (thay alert; restart giữ alert vì reload xóa DOM)
function toast(msg, isErr){let d=$('toast');if(!d){d=document.createElement('div');d.id='toast';d.className='toast';document.body.appendChild(d);}
d.textContent=msg;d.className='toast show'+(isErr?' err':'');clearTimeout(window._toastT);window._toastT=setTimeout(()=>{d.className='toast';},3000);}
// SSE reader dùng chung (startTl + bulk + merge)
async function readSSE(resp, h){
const rd=resp.body.getReader(),dec=new TextDecoder();let buf='';
while(true){const{done,value}=await rd.read();if(done)break;buf+=dec.decode(value,{stream:true});
let idx;while((idx=buf.indexOf('\n\n'))>=0){const blk=buf.slice(0,idx);buf=buf.slice(idx+2);
const ev=(blk.match(/event: (\w+)/)||[])[1],dt=(blk.match(/data: ([\s\S]*)/)||[])[1];if(!ev)continue;
const j=JSON.parse(dt);
if(ev==='chunk')h.onChunk&&h.onChunk(j);
else if(ev==='progress')h.onProgress&&h.onProgress(j);
else if(ev==='done'){h.onDone&&h.onDone(j);return {done:j};}
else if(ev==='error'){h.onError&&h.onError(j);return {error:j.error};}}}
return {done:false};}
async function restartSrv(){if(!confirm('Khởi động lại server? Trang sẽ tự tải lại.'))return;
try{await fetch('/api/restart',{method:'POST'}).then(J);}catch(e){}
alert('Server đang khởi động lại… bấm OK rồi chờ 3 giây, trang tự tải lại.');
setTimeout(()=>location.reload(),3000);}
