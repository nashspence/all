import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
function analyze(p,logs){
 const errors=[],failures=[],workers=[],caps={cpu_serial:350000000,cpu_p4:300000000,sha256:250000000,warm_files:150000000,fdatasync64:250000000},profile="public-linux-x64-4cpu-native-api-v1",eq=(a,b)=>JSON.stringify(a)===JSON.stringify(b),sortObj=o=>JSON.stringify(Object.fromEntries(Object.entries(o??{}).sort(([a],[b])=>a.localeCompare(b)))),pos=n=>Number.isSafeInteger(n)&&n>0,check=(ok,msg,w)=>{if(!ok)errors.push({worker:w??null,error:msg})},distinct=a=>new Set(a).size;
 const stats=a=>{let s=a.filter(pos).sort((x,y)=>x-y);return {count:s.length,min_ms:s.length?s[0]/1e6:null,median_ms:s.length?(s[Math.floor((s.length-1)/2)]+s[Math.floor(s.length/2)])/2e6:null,max_ms:s.length?s.at(-1)/1e6:null}};
 const freq=a=>Object.fromEntries([...new Set(a)].sort().map(v=>[v,a.filter(x=>x===v).length]));
 check(p.run.id===45910890189&&p.run.run_attempt===1&&p.run.status==="completed"&&p.run.conclusion==="success"&&p.run.head_sha==="fdd5c7f7c333dfc7d5359af04f6c79045870da19"&&p.run.event==="push","first-attempt run identity");
 check(p.workflow_diff_only_trigger,"workflow differs only in trigger branch");
 check(p.jobs.length===12&&distinct(p.jobs.map(j=>j.id))===12&&distinct(p.jobs.map(j=>j.runner_id))===12&&p.jobs.every(j=>pos(j.runner_id)&&j.status==="completed"&&j.conclusion==="success"&&!p.original_runner_ids.includes(j.runner_id)),"complete distinct new allocations");
 check(p.artifacts.length===12&&distinct(p.artifacts.map(a=>a.name))===12&&p.artifacts.every(a=>!a.expired&&pos(a.size_in_bytes)&&/^sha256:[a-f0-9]{64}$/.test(a.digest??"")),"artifact metadata");
 check(logs.length===12&&distinct(logs.map(l=>l.id))===12,"original log inventory");
 for(const j of p.jobs){
  const w=Number(j.name.replace("common-","")),log=logs.find(l=>l.id===j.id);
  if(!log||log.records.length!==1){check(false,"missing or ambiguous original observation",w);continue}
  try{
  const v=JSON.parse(log.records[0]),f=p.frozen_source_inventory,r=v.result,n=v.native_qualification;
  check(v.worker===w&&v.job_name===j.name&&String(v.run_id)===String(p.run.id)&&v.run_attempt===1&&v.runner_name===j.runner_name&&v.repository==="nashspence/all"&&v.workflow_sha===p.run.head_sha&&v.activation_sha===p.run.head_sha&&v.workflow_ref.endsWith("@refs/heads/"+p.run.head_branch),"observation/run/worker identity",w);
  check(v.shared_revision===f.shared_revision&&v.subject_revision===f.shared_revision&&v.authority_revision===f.authority_revision&&v.python==="3.11.9"&&v.pyyaml==="6.0.3"&&v.collection_error===null,"frozen inputs/runtime",w);
  check(v.installed_source.package_sha256===f.package_sha256&&sortObj(v.installed_source.files_sha256)===sortObj(f.module_files_sha256)&&sortObj(r.shared_source.files_sha256)===sortObj(f.module_files_sha256)&&r.shared_source.package_sha256===f.package_sha256&&v.adapter_sha256===f.files_sha256["examples/performance/all_policy_case.py"],"installed module and adapter hashes",w);
  check(v.authority_documents_sha256.limits===f.publication_sha256.authority_limits&&v.authority_documents_sha256.bindings===f.publication_sha256.authority_bindings&&r.limits_sha256===f.publication_sha256.authority_limits&&r.bindings_sha256===f.publication_sha256.authority_bindings&&r.authority_revision===f.authority_revision&&r.candidate_revision===f.shared_revision,"authority/candidate identity",w);
  const entries=Object.values(r.preflights);check(entries.length===1,"one preflight",w);const e=entries[0],m=e.metadata,after=e.metadata_after;
  const reasons=[];
  for(const when of ["metadata","metadata_after"]){const a=e[when]??{},mount=a.mount??{};const checks=[[a.system==="Linux","Linux required"],[["x86_64","amd64"].includes((a.machine??"").toLowerCase()),"x64 required"],[a.python==="3.11.9","shared probe runtime Python 3.11.9 required"],[a.logical_cpus===4&&a.affinity_count===4,"four available CPUs required"],[Number.isInteger(a.memory_total_bytes)&&a.memory_total_bytes>=14*1024**3,"14 GiB memory required"],[a.free_bytes>=64*1024**2,"64 MiB scratch capacity required"],[["ext4","xfs","btrfs"].includes(mount.fstype),"incompatible storage semantics"],[!!mount.source&&!!mount.options,"mount options/source evidence required"],[!!a.topology&&Object.keys(a.topology).length>0,"native block topology evidence required"]];
   if(typeof a.cpu_max==="string"&&!a.cpu_max.startsWith("max ")){const q=a.cpu_max.split(/\s+/).map(Number);checks.push(q.length!==2||q.some(x=>!Number.isInteger(x))?[false,"invalid CPU quota"]:[q[1]>0&&q[0]>=4*q[1],"CPU quota below four CPUs"])}
   if(a.memory_max!=null&&a.memory_max!=="max")checks.push([/^\d+$/.test(String(a.memory_max))&&Number(a.memory_max)>=14*1024**3,"memory quota below 14 GiB"]);
   reasons.push(...checks.filter(([ok])=>!ok).map(([,why])=>when+": "+why));
  }
  if(["root","device","mount"].some(k=>!eq(m[k],after[k])))reasons.push("storage location or mount changed during preflight");
  for(const [name,cap] of Object.entries(caps)){const s=e.samples_ns[name]??[];check(s.length===3&&s.every(pos),"three positive probe samples "+name,w);if(name==="fdatasync64")continue;if(s.length!==3||s.some(x=>!pos(x)||x>cap))reasons.push(name+": missing, invalid or over-cap observation");if(e.errors.some(x=>[name,"metadata"].includes(x.probe)))reasons.push(name+": probe failed")}
  const admitted=reasons.length===0,operations={};
  check(eq(Object.keys(r.operations).sort(),Object.keys(p.limits.operations).sort()),"operation inventory",w);
  for(const [name,limit] of Object.entries(p.limits.operations)){const o=r.operations[name],binding=p.bindings.operations[name],obs=o.observations,raw=obs.map(x=>x.elapsed_ns),over=raw.map((x,i)=>x>limit.max_wall_ns?i:-1).filter(i=>i>=0),valid=obs.length===3&&obs.every(x=>pos(x.elapsed_ns)&&x.completed===true&&x.verified===true&&!x.error),verdict=!admitted?"unqualified":!valid?"failed":over.length?"miss":"pass";
   check(o.admission.admitted===admitted&&eq(o.admission.reasons,reasons)&&o.admission.profile===profile&&o.admission.persistence_qualified===false,"recomputed admission "+name,w);
   check(o.mode===binding.mode&&o.unit===binding.unit&&o.completion===binding.completion,"approved operation binding "+name,w);
   check(o.decision.profile===profile&&o.decision.budget_ns===limit.max_wall_ns&&eq(o.decision.samples_ns,raw)&&eq(o.decision.over_budget_indices,over)&&o.decision.verdict===verdict,"recomputed verdict "+name,w);
   if(verdict!=="pass")failures.push({worker:w,operation:name,verdict,raw});operations[name]={verdict,samples_ns:raw};
  }
  const aggregate=["failed","miss","unqualified","pass"].find(x=>Object.values(operations).some(o=>o.verdict===x));check(r.verdict===aggregate&&v.cli_exit_code==={pass:0,miss:1,unqualified:2,failed:3}[aggregate],"aggregate verdict/exit",w);
  const packet=n.packet,t=packet.topology,options=t.mount_options,bad=options.filter(x=>["nobarrier","barrier=0","data=writeback","journal_async_commit"].includes(x)).sort(),nativeReasons=[];
  if(!["ext4","xfs"].includes(t.filesystem))nativeReasons.push("first native qualification requires an observed ext4 or xfs filesystem");
  if(bad.length)nativeReasons.push("relaxed mount settings are outside this proposed native profile: "+bad.join(", "));
  const mounts=t.mount?.data?.filesystems??[];if(!mounts.length||!mounts[0].source||!t.device)nativeReasons.push("actual mount source/device evidence is missing");if(t.loop_backing!=null)nativeReasons.push("loop backing requires separately approved whole-stack storage qualification");if(options.includes("ro")||!options.includes("rw"))nativeReasons.push("writable mount evidence required");
  check(eq(nativeReasons,packet.configuration_reasons),"recomputed storage rejection",w);check(packet.resolved_root===m.root&&t.filesystem===m.mount.fstype&&eq([...options].sort(),m.mount.options.split(",").sort()),"same actual storage scope",w);
  const rejection=n.collection_error===null&&!n.not_run&&!n.outer_timed_out&&n.outer_watchdog_seconds===60&&n.package_deadline_seconds===300&&n.cli_exit_code===2&&n.summary.status==="environment_unqualified"&&n.summary.profile_approved===false&&packet.status==="environment_unqualified"&&packet.profile_approved===false&&packet.physical_persistence_proven===false&&Object.keys(packet.operations).length===0&&nativeReasons.length>0;
  if(!rejection)failures.push({worker:w,operation:"native_rejection_control",status:packet.status,exit:n.cli_exit_code});
  check(p.artifacts.some(a=>a.name==="common-package-"+w),"matching artifact",w);
  workers.push({worker:w,job_id:j.id,runner_id:j.runner_id,cpu_model:m.cpu_model,image_version:v.image_version,mount_source:m.mount.source,admitted,admission_reasons:reasons,operations,probes_ns:e.samples_ns,cli_wall_ns:v.cli_wall_ns,preflight_ns:e.total_ns,native_wall_ns:n.cli_wall_ns,native_rejection_complete:rejection,native_reasons:nativeReasons});
  }catch(err){check(false,"record shape/analysis failure: "+String(err),w)}
 }
 workers.sort((a,b)=>a.worker-b.worker);check(workers.length===12&&distinct(workers.map(w=>w.worker))===12,"complete analyzed cohort");
 const operations=Object.fromEntries(Object.entries(p.limits.operations).map(([name,limit])=>{const rows=workers.map(w=>w.operations[name]),values=rows.flatMap(o=>o.samples_ns);return [name,{budget_ms:limit.max_wall_ns/1e6,...stats(values),pass_workers:rows.filter(o=>o.verdict==="pass").length,verdicts:freq(rows.map(o=>o.verdict))}]}));
 const probes=Object.fromEntries(Object.entries(caps).map(([name,cap])=>[name,{...stats(workers.flatMap(w=>w.probes_ns[name]??[])),cap_ms:cap/1e6,binding:name!=="fdatasync64",over_cap:workers.flatMap(w=>(w.probes_ns[name]??[]).map((x,i)=>({worker:w.worker,repeat:i,ns:x})).filter(v=>v.ns>cap))}]));
 return {screen_passed:errors.length===0&&failures.length===0&&workers.length===12&&workers.every(w=>w.admitted&&w.native_rejection_complete)&&Object.values(operations).every(o=>o.pass_workers===12&&o.count===36),errors,failures,workers:workers.length,core_admitted:workers.filter(w=>w.admitted).length,product_observations:Object.values(operations).reduce((s,o)=>s+o.count,0),native_rejection_controls_complete:workers.filter(w=>w.native_rejection_complete).length,operations,probes,cli:stats(workers.map(w=>w.cli_wall_ns)),preflight:stats(workers.map(w=>w.preflight_ns)),native_cli:stats(workers.map(w=>w.native_wall_ns)),images:freq(workers.map(w=>w.image_version)),cpus:freq(workers.map(w=>w.cpu_model)),by_worker:workers};
}
const root=path.dirname(fileURLToPath(import.meta.url));
const read=name=>JSON.parse(fs.readFileSync(path.join(root,name),'utf8'));
const result=analyze(read('provenance.json'),[...read('observations-01-06.json'),...read('observations-07-12.json')]);
console.log(JSON.stringify(result,null,2));
process.exitCode=result.screen_passed?0:1;
