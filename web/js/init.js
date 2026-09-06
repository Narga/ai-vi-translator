listProjects().then(listFiles);loadMeta().then(loadProvDetail);loadProfiles();
$('wProfile').onchange=applyProfile;
$('wProj').onchange=()=>{_wsSrc=null;_wsRes=null;_sel.clear();
Object.assign(_flt,{sortBy:'name',sortOrder:'asc',keyword:''});
const kw=$('fltKw');if(kw)kw.value='';listFiles();};
$('wProv').onchange=fillModels;
try{if(localStorage.getItem('ct_wrap')==='0'){$('tSrc').classList.add('nowrap');$('tOut').classList.add('nowrap');}}catch(e){}
$('wPrompt').onchange=updExtraEst;
$('wExtra').onchange=updExtraEst;
// panel Tập tin (tiêu đề + hint + card) là drop target
const _dz=$('wFilesWrap');
['dragover','dragenter'].forEach(e=>_dz.addEventListener(e,ev=>{ev.preventDefault();$('wFiles').style.outline='2px dashed #2563eb';}));
['dragleave','drop'].forEach(e=>_dz.addEventListener(e,ev=>{ev.preventDefault();$('wFiles').style.outline='';}));
_dz.addEventListener('drop',ev=>{if(ev.dataTransfer.files.length)wsUpload(ev.dataTransfer.files);});
$('wFileInput').onchange=()=>wsUpload($('wFileInput').files);
