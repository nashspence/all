from pathlib import Path
import argparse,ast,json,os,subprocess,sys,tempfile
from unittest.mock import patch
parser=argparse.ArgumentParser(description="Compare audited Git history readers in a disposable repository.")
parser.add_argument('--repos',required=True,type=Path,help='Directory containing fishhat and guavajam checkouts at the audited commits')
ROOT=parser.parse_args().repos.resolve()
ENV={k:v for k,v in os.environ.items() if not k.startswith('GIT_')}
ENV.update(GIT_CONFIG_NOSYSTEM='1',GIT_CONFIG_GLOBAL=os.devnull)
EXPECTED={'fishhat':'f96b83dc20f059d62a4363a63c37bb0ef8c642e5','guavajam':'54fce07b619628a5e92be946be4b189873ddf1a0'}
for name,expected in EXPECTED.items():
 actual=subprocess.check_output(['git','-C',str(ROOT/name),'rev-parse','HEAD'],env=ENV,text=True).strip()
 if actual!=expected:raise SystemExit(name+' must be checked out at '+expected)
 if subprocess.check_output(['git','-C',str(ROOT/name),'status','--porcelain'],env=ENV,text=True).strip():raise SystemExit(name+' checkout must be clean')
sys.path.insert(0,str(ROOT/'guavajam/src'))
source=ROOT/'fishhat/scripts/project_policy.py'
function=next(n for n in ast.parse(source.read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='fixture_history_errors')
namespace={'Path':Path,'subprocess':subprocess}
exec(compile(ast.Module(body=[function],type_ignores=[]),str(source),'exec'),namespace)
fixture_history_errors=namespace['fixture_history_errors']
from guavajam.source_snapshot import snapshot
with patch.dict(os.environ,ENV,clear=True),tempfile.TemporaryDirectory() as td:
 root=Path(td)
 def git(*args):return subprocess.check_output(['git','-C',str(root),*args],text=True,stderr=subprocess.DEVNULL,env=ENV).strip()
 git('init','-q');git('config','user.name','Drift fixture');git('config','user.email','fixture@example.invalid');git('config','commit.gpgsign','false');git('config','core.hooksPath',os.devnull)
 (root/'state/fixtures').mkdir(parents=True);(root/'content').mkdir()
 for name in ('state/fixtures/accepted.json','content/input.txt'):(root/name).write_text('original\n')
 git('add','.');git('commit','-qm','accepted baseline');accepted=git('rev-parse','HEAD')
 for name in ('state/fixtures/accepted.json','content/input.txt'):(root/name).write_text('changed\n')
 git('add','.');git('commit','-qm','changed protected fixture')
 before=fixture_history_errors(root)
 replacement=git('commit-tree',git('rev-parse','HEAD^{tree}'),'-m','local replacement root')
 git('replace',accepted,replacement)
 after=fixture_history_errors(root)
 with snapshot(root,accepted) as (path,_):guavajam=(path/'content/input.txt').read_text()
 result={'fishhat_before_local_replace':before,'fishhat_after_local_replace':after,'guavajam_snapshot_of_named_original':guavajam,'working_tree_clean':not git('status','--porcelain'),'execution_scope':'Fishhat fixture_history_errors extracted verbatim by AST to avoid unrelated package dependencies; Guavajam snapshot imported normally'}
 assert before and after==[] and guavajam=='original\n' and result['working_tree_clean']
 print(json.dumps(result,indent=2))
