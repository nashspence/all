from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import argparse,json,os,subprocess,sys,threading,urllib.request
from unittest.mock import patch
parser=argparse.ArgumentParser(description="Compare audited credential transports using synthetic local requests only.")
parser.add_argument('--repos',required=True,type=Path,help='Directory containing all and guavajam checkouts at the audited commits')
ROOT=parser.parse_args().repos.resolve()
EXPECTED={'all':'03de186a044c9c6b365347485a6c4093ce831c79','guavajam':'54fce07b619628a5e92be946be4b189873ddf1a0'}
for name,expected in EXPECTED.items():
 env={k:v for k,v in os.environ.items() if not k.startswith('GIT_')}
 actual=subprocess.check_output(['git','-C',str(ROOT/name),'rev-parse','HEAD'],env=env,text=True).strip()
 if actual!=expected:raise SystemExit(name+' must be checked out at '+expected)
 if subprocess.check_output(['git','-C',str(ROOT/name),'status','--porcelain'],env=env,text=True).strip():raise SystemExit(name+' checkout must be clean')
sys.path.insert(0,str(ROOT/'all'));sys.path.insert(0,str(ROOT/'guavajam/src'))
import importlib
audit=importlib.import_module('all_policy.audit')
from guavajam import deploy_asset_gateway
from guavajam.asset_policy import AssetError
seen=[]
class Receiver(BaseHTTPRequestHandler):
 def do_GET(self):
  seen.append(self.headers.get('Authorization'))
  body=b'{"success": true, "result": {"observed": true}}'
  self.send_response(200);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
 def log_message(self,*args):pass
receiver=ThreadingHTTPServer(('127.0.0.1',0),Receiver)
target=f'http://127.0.0.1:{receiver.server_port}/target'
class Redirector(BaseHTTPRequestHandler):
 def do_GET(self):
  self.send_response(302);self.send_header('Location',target);self.send_header('Content-Length','0');self.end_headers()
 def log_message(self,*args):pass
redirector=ThreadingHTTPServer(('127.0.0.1',0),Redirector)
start=f'http://127.0.0.1:{redirector.server_port}/start'
threads=[]
for server in (receiver,redirector):
 thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();threads.append(thread)
original=urllib.request.Request
os.environ['NO_PROXY']='127.0.0.1,localhost'
os.environ['no_proxy']='127.0.0.1,localhost'
try:
 def map_initial(url,*args,**kwargs):
  return original(start if url.startswith(('https://api.github.com','https://api.cloudflare.com')) else url,*args,**kwargs)
 with patch.object(audit,'Request',side_effect=map_initial):audit.GitHub('synthetic-test-token').get('/repos/fixture')
 forwarded=list(seen);seen.clear()
 refused=False
 with patch.object(urllib.request,'Request',side_effect=map_initial):
  try:deploy_asset_gateway.cf_request('a'*32,'scripts/fixture','synthetic-test-token')
  except AssetError:refused=True
 assert forwarded==['Bearer synthetic-test-token'] and refused and seen==[]
 print(json.dumps({'all_default_transport_forwarded_synthetic_authorization_to_other_origin':bool(forwarded),'guavajam_refused_redirect_before_other_origin_request':refused and not seen,'scope':'actual clients with only initial URL mapped to disposable loopback origins; no external service or real credential used'},indent=2))
finally:
 for server in (receiver,redirector):server.shutdown();server.server_close()
 for thread in threads:thread.join(timeout=2)
