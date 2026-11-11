const $ = id => document.getElementById(id);
let current = null;
async function api(path, body) {
  const response = await fetch(path, body === undefined ? {} : {method:'POST',headers:{'Content-Type':'application/json','X-Filework':'1'},body:JSON.stringify(body)});
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'The request could not be completed.');
  return data;
}
function node(tag, text, className) { const n=document.createElement(tag); n.textContent=text; if(className)n.className=className;return n; }
function clearError() { $('error').hidden=true; }
function error(e) { $('error').textContent=e.message;$('error').hidden=false; }
function render(task) {
 current=task;$('result').hidden=false;$('empty').hidden=true;
 $('result-title').textContent=task.proposal?(task.status==='completed'?'Report saved':'Report preview'):task.status==='failed'?'Task stopped':'A little more detail';
 $('status').textContent=task.status.replaceAll('_',' ');$('answer').textContent=task.answer;
 const p=task.proposal;$('table-wrap').hidden=!p;$('totals').replaceChildren();$('warnings').replaceChildren();$('rows').replaceChildren();
 $('scope').textContent=p?'Scope: '+[p.filters.start_date||'earliest',p.filters.end_date||'latest'].join(' to ')+(p.filters.currency?' · '+p.filters.currency:' · separate currency totals')+(p.filters.supplier?' · '+p.filters.supplier:''):'';
 if(p) {
  Object.entries(p.totals).forEach(([currency,total])=>{const c=node('div','','total-card');c.append(node('small',currency+' TOTAL'),node('strong',Number(total).toLocaleString('en-IE',{minimumFractionDigits:2,maximumFractionDigits:2})));$('totals').append(c);});
  p.warnings.forEach(w=>$('warnings').append(node('p',w)));
  if(p.duplicates.length)$('warnings').append(node('p',`${p.duplicates.length} identical duplicate copy/copies ignored. Conflicting copies stop the task.`));
  p.rows.forEach(row=>{const tr=node('tr','');[row.invoice_id,row.supplier,row.date,row.currency+' '+row.total,row.source].forEach(v=>tr.append(node('td',v)));$('rows').append(tr);});
 }
 $('approve').hidden=task.status!=='awaiting_approval';$('approve').disabled=false;
 $('download').hidden=!task.download_url;if(task.download_url)$('download').href=task.download_url;
 $('report-note').textContent=p?(task.status==='completed'?'Report saved. Source files were not changed.':p.warnings.length?'Some documents could not be checked. Review the warnings before saving.':'Preview only. Saving creates a new CSV; source files stay unchanged.') : '';
 $('events').replaceChildren();task.events.forEach(e=>$('events').append(node('li',e.summary)));
 $('steps-count').textContent=task.events.length+' steps';
 $('metrics').replaceChildren(...[`${task.elapsed_ms.toLocaleString()} ms`,`${task.usage.model_calls} model calls`,`${task.usage.prompt_tokens+task.usage.completion_tokens} tokens`,task.estimated_cost_usd===null?'Cost not configured':`Estimated model cost: $${Number(task.estimated_cost_usd).toFixed(6)}`].map(s=>node('span',s)));
}
async function history() {
 const tasks=await api('/api/history');$('history').replaceChildren();
 tasks.forEach(t=>{const b=node('button',t.request);b.addEventListener('click',async()=>{try{render(await api('/api/tasks/'+t.id));}catch(e){error(e);}});$('history').append(b);});
}
$('task-form').addEventListener('submit',async e=>{
 e.preventDefault();clearError();$('run').disabled=true;$('busy').hidden=false;
 try{render(await api('/api/tasks',{request:$('request').value,mode:$('mode').value}));await history();}catch(e){error(e);}finally{$('run').disabled=false;$('busy').hidden=true;}
});
$('approve').addEventListener('click',async()=>{if(!current)return;clearError();$('approve').disabled=true;try{render(await api(`/api/tasks/${current.id}/approve`,{}));await history();}catch(e){error(e);$('approve').disabled=false;}});
document.querySelectorAll('[data-prompt]').forEach(b=>b.addEventListener('click',()=>{$('request').value=b.dataset.prompt;$('request').focus();}));
$('mode').addEventListener('change',()=>{$('mode-note').textContent=$('mode').value==='baseline'?'Offline baseline · No API key needed · Supports a month and year, or all invoices.':'LLM agent · Document text may be sent to your configured provider · Up to 10 model turns.';});
(async()=>{try{const w=await api('/api/workspace');$('workspace-name').textContent=w.name;$('file-count').textContent=w.files.length+' documents';$('files').replaceChildren(...w.files.map(f=>node('li',f)));$('mode').querySelector('[value=llm]').disabled=!w.llm_configured;await history();}catch(e){error(e);}})();
