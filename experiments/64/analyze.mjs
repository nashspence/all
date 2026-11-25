// Optional reproduction of the finite pilot report; no runtime or CI dependency.
import {readFileSync} from 'node:fs';
function analyze(rows){
  const avg=a=>a.reduce((x,y)=>x+y,0)/a.length, median=a=>{let b=[...a].sort((x,y)=>x-y);return b.length%2?b[(b.length-1)/2]:(b[b.length/2-1]+b[b.length/2])/2;};
  const range=a=>({min:Math.min(...a),median:median(a),max:Math.max(...a)});
  const groups={};let all={};
  const keys=Object.keys(rows[0].samples_ns);
  for(const k of keys){
    const means=rows.map(x=>avg(x.samples_ns[k])/1e6);const ref=median(means.slice(0,12));const dev=means.map(m=>Math.abs(m/ref-1));
    const train=Math.max(...dev.slice(0,12));const hold=Math.max(...dev.slice(12));const e=train+0.05;
    const spreads=rows.map(x=>Math.max(...x.samples_ns[k])/Math.min(...x.samples_ns[k])-1);
    all[k]={reference_ms:ref,means_ms:range(means),training_max_relative_error:train,holdout_max_relative_error:hold,candidate_allowance:e,holdout_outside_count:dev.slice(12).filter(x=>x>e).length,pilot_max_allowance:0.20,supported_in_pilot:e<=0.20&&hold<=e,within_three_run_relative_spread:range(spreads),max_single_ms:Math.max(...rows.flatMap(x=>x.samples_ns[k]))/1e6};
  }
  for(const row of rows){let key=row.cpu_model; (groups[key]??=[]).push(row);}
  const by_cpu=Object.fromEntries(Object.entries(groups).map(([k,rr])=>[k,{allocations:rr.length,policy_serial_mean_ms:range(rr.map(x=>avg(x.samples_ns.policy_p1)/1e6)),cpu_serial_mean_ms:range(rr.map(x=>avg(x.samples_ns.cpu_p1)/1e6)),sqlite_mean_ms:range(rr.map(x=>avg(x.samples_ns.sqlite_full)/1e6))}]));
  const parallel={};for(const name of ["cpu","policy"]){parallel[name]={};for(const p of [2,4])parallel[name][`p${p}`]=range(rows.map(x=>avg(x.samples_ns[`${name}_p1`])/avg(x.samples_ns[`${name}_p${p}`])));}
  return {cases:all,by_cpu,parallel,profile:{image_versions:[...new Set(rows.map(x=>x.image_version))],kernels:[...new Set(rows.map(x=>x.kernel))],sqlite_versions:[...new Set(rows.map(x=>x.sqlite))],filesystems:[...new Set(rows.map(x=>x.filesystem))],cpu_quota_values:[...new Set(rows.map(x=>x.cpu_max))],memory_quota_values:[...new Set(rows.map(x=>x.memory_max))]},single_allowance_candidate:Math.max(...Object.values(all).map(x=>x.candidate_allowance)),all_cases_supported:Object.values(all).every(x=>x.supported_in_pilot)};
}
const raw=JSON.parse(readFileSync(process.argv[2]||new URL('./observations.json',import.meta.url),'utf8'));
if(raw.complete!==true||raw.records.length!==24||raw.records.some((r,i)=>r.allocation!==i+1||r.verified!==true))throw Error('incomplete or unordered pilot');
console.log(JSON.stringify(analyze(raw.records),null,2));
