#!/usr/bin/env python3
"""Local-only AfterVolt content editor. Never expose port 8765 publicly."""
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
import json, os, re, secrets, subprocess, webbrowser

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'content.json'
TOKEN = secrets.token_urlsafe(32)
HOST, PORT = '127.0.0.1', 8765

HTML = r'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>AfterVolt Content Studio</title>
<style>:root{color-scheme:dark}*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 90% 0,#351747,#0b0712 60%);color:#f8f2ff;font:16px/1.5 system-ui,sans-serif}main{max-width:950px;margin:auto;padding:35px 20px}h1{font-size:clamp(2rem,5vw,3.5rem)}section{background:#1a1025;border:1px solid #654779;border-radius:14px;padding:20px;margin:20px 0}label{display:block;margin-top:14px;color:#dfc6fb;font-weight:600}input,textarea{width:100%;padding:11px;color:#fff;background:#100a19;border:1px solid #76578d;border-radius:6px;font:inherit}textarea{min-height:85px}button{background:#bd80ff;color:#160b21;border:0;border-radius:7px;padding:11px 16px;cursor:pointer;font:inherit;font-weight:700;margin:7px 7px 7px 0}button.secondary{background:#3b294b;color:#fff}button:disabled{opacity:.5}.item{padding:15px;border:1px solid #5c456c;margin:12px 0;border-radius:8px}#status{white-space:pre-wrap;color:#c9a7fa}a{color:#d6b5ff}</style>
<main><p style="letter-spacing:.2em;color:#c99aff">AFTERVOLT / RECORDS</p><h1>Content Studio</h1><p>Edit the label website without touching HTML. This editor works only on this computer.</p><p><a href="/" target="_blank">Preview local website ↗</a></p>
<section><h2>Homepage and contact</h2><label>Small headline<input id="tagline"></label><label>Introduction<textarea id="intro"></textarea></label><label>About<textarea id="about"></textarea></label><label>Contact text<textarea id="contactText"></textarea></label><label>Public booking email<input id="contactEmail" type="email"></label><label>Music or social HTTPS link<input id="socialUrl" type="url"></label></section>
<section><h2>Releases</h2><p>Add a Spotify, Bandcamp or other HTTPS link. Cover can be HTTPS or an image path in assets/.</p><button id="addRelease">+ Add release</button><div id="releases"></div></section>
<section><h2>Artists</h2><button id="addArtist">+ Add artist</button><div id="artists"></div></section>
<section><h2>Save and publish</h2><p>Save draft updates local content.json only. Publish makes a Git commit and pushes it to GitHub.</p><button class="secondary" id="save">Save draft</button><button id="publish">Publish to website ↗</button><p id="status" role="status"></p></section></main>
<script>
const TOKEN='__TOKEN__';let data;
const $=id=>document.getElementById(id);
const fields=['tagline','intro','about','contactText','contactEmail','socialUrl'];
function input(holder,label,key,value){const l=document.createElement('label'),i=document.createElement('input');l.textContent=label;i.dataset.key=key;i.value=value||'';l.append(i);holder.append(l)}
function capture(){fields.forEach(k=>data[k]=$(k).value);['releases','artists'].forEach(kind=>$(kind).querySelectorAll('.item').forEach((node,n)=>node.querySelectorAll('[data-key]').forEach(i=>data[kind][n][i.dataset.key]=i.value)))}
function render(kind){$(kind).replaceChildren();data[kind].forEach((entry,n)=>{let box=document.createElement('div');box.className='item';let h=document.createElement('strong');h.textContent=kind==='releases'?'Release '+(n+1):'Artist '+(n+1);box.append(h);let remove=document.createElement('button');remove.className='secondary';remove.textContent='Remove';remove.onclick=()=>{if(confirm('Remove this entry?')){capture();data[kind].splice(n,1);render(kind)}};box.append(remove);(kind==='releases'?[['Title','title'],['Artist','artist'],['Catalog number','catalog'],['Music link (HTTPS)','url'],['Cover URL or assets/ path','cover']]:[['Name','name'],['Artist URL (HTTPS)','url']]).forEach(([label,key])=>input(box,label,key,entry[key]));$(kind).append(box)})}
function status(text){$('status').textContent=text}
async function request(path,payload){const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json','X-AfterVolt-Token':TOKEN},body:JSON.stringify(payload)});const j=await r.json();if(!r.ok)throw Error(j.error||'Request failed');return j}
async function save(){capture();const r=await request('/api/save',data);status(r.message)}
$('save').onclick=async()=>{try{await save()}catch(e){status(e.message)}};
$('publish').onclick=async()=>{const b=$('publish');b.disabled=true;try{await save();status('Publishing...');const r=await request('/api/publish',{});status(r.message)}catch(e){status(e.message)}finally{b.disabled=false}};
$('addRelease').onclick=()=>{capture();data.releases.push({title:'',artist:'',catalog:'',url:'',cover:''});render('releases')};
$('addArtist').onclick=()=>{capture();data.artists.push({name:'',url:''});render('artists')};
fetch('/api/content').then(r=>r.json()).then(j=>{data=j;fields.forEach(k=>$(k).value=data[k]||'');render('releases');render('artists');status('Ready. Changes are local until published.')}).catch(e=>status(e.message));
</script>'''.replace('__TOKEN__',TOKEN)

def validate(raw):
    if not isinstance(raw,dict): raise ValueError('Expected a content object.')
    result={}
    for key in ('tagline','intro','about','contactText','contactEmail','socialUrl'):
        v=raw.get(key,'')
        if not isinstance(v,str) or len(v)>10000: raise ValueError('Invalid '+key)
        result[key]=v.strip()
    if result['contactEmail'] and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',result['contactEmail']): raise ValueError('Invalid email address.')
    def url(v,asset=False):
        return not v or (len(v)<2048 and bool(re.fullmatch(r'https://[^\s<>"\']+',v,re.I))) or (asset and bool(re.fullmatch(r'assets/[a-zA-Z0-9_./-]+',v)) and '..' not in v)
    if not url(result['socialUrl']): raise ValueError('Social link needs HTTPS.')
    for kind,keys in (('releases',('title','artist','catalog','url','cover')),('artists',('name','url'))):
        entries=raw.get(kind,[])
        if not isinstance(entries,list) or len(entries)>100: raise ValueError('Invalid '+kind)
        result[kind]=[]
        for entry in entries:
            if not isinstance(entry,dict): raise ValueError('Invalid item.')
            item={}
            for key in keys:
                v=entry.get(key,'')
                if not isinstance(v,str) or len(v)>2048: raise ValueError('Invalid '+key)
                item[key]=v.strip()
            if not item['title' if kind=='releases' else 'name']: raise ValueError('Each item needs a title/name.')
            if not url(item['url']) or ('cover' in item and not url(item['cover'],True)): raise ValueError('Invalid link; use HTTPS or assets/ for artwork.')
            result[kind].append(item)
    return result

def git(*args):
    env=os.environ.copy();env['GIT_TERMINAL_PROMPT']='0'
    p=subprocess.run(['git',*args],cwd=ROOT,env=env,capture_output=True,text=True,timeout=60)
    if p.returncode: raise RuntimeError((p.stderr or p.stdout or 'Git error').strip()[:650])
    return p.stdout.strip()

def publish():
    if not (ROOT/'.git').exists(): raise RuntimeError('Clone the repository first; see README.md.')
    remote=git('remote','get-url','origin').rstrip('/').removesuffix('.git')
    if remote not in ('https://github.com/Neurvs/AfterVoltRecords','git@github.com:Neurvs/AfterVoltRecords'): raise RuntimeError('Unexpected Git remote; refusing to publish.')
    if git('branch','--show-current')!='main': raise RuntimeError('Switch to main before publishing.')
    git('fetch','origin','main')
    behind=git('rev-list','--left-right','--count','HEAD...origin/main').split()
    if len(behind)!=2 or int(behind[1]): raise RuntimeError('GitHub has newer commits. Back up drafts and ask Agustin to synchronize before publishing.')
    if not git('status','--porcelain','--','content.json'): return 'No changes to publish.'
    git('add','--','content.json');git('commit','-m','Update AfterVolt content','--only','--','content.json');git('push','origin','main')
    return 'Published! GitHub Pages should update in a few minutes.'

class Handler(BaseHTTPRequestHandler):
    def send(self,code,text,kind='text/html; charset=utf-8'):
        buf=text.encode('utf-8') if isinstance(text,str) else text
        self.send_response(code);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(buf)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' https: data:; connect-src 'self'; frame-ancestors 'none'");self.end_headers();self.wfile.write(buf)
    def js(self,code,data):self.send(code,json.dumps(data),'application/json; charset=utf-8')
    def do_GET(self):
        if self.path in ('/','/index.html'): return self.send(200,(ROOT/'index.html').read_bytes())
        if self.path=='/editor': return self.send(200,HTML)
        if self.path in ('/api/content','/content.json'): return self.send(200,DATA.read_bytes(),'application/json; charset=utf-8')
        self.send(404,'Not found','text/plain; charset=utf-8')
    def do_POST(self):
        try:
            if self.headers.get('Origin') not in (None,f'http://{HOST}:{PORT}'): raise ValueError('Invalid origin.')
            if self.headers.get('X-AfterVolt-Token')!=TOKEN: raise ValueError('Invalid session.')
            if self.headers.get('Content-Type','').split(';')[0].strip()!='application/json': raise ValueError('JSON required.')
            size=int(self.headers.get('Content-Length','0'))
            if size<2 or size>500000: raise ValueError('Invalid request size.')
            data=json.loads(self.rfile.read(size))
            if self.path=='/api/save':
                value=validate(data);temporary=DATA.with_suffix('.tmp');temporary.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n');temporary.replace(DATA)
                return self.js(200,{'message':'Draft saved locally. Click Publish when ready.'})
            if self.path=='/api/publish': return self.js(200,{'message':publish()})
            self.js(404,{'error':'Not found.'})
        except (ValueError,RuntimeError,OSError,subprocess.TimeoutExpired,json.JSONDecodeError) as exc:self.js(400,{'error':str(exc)[:650]})
    def log_message(self,*args):pass

if __name__=='__main__':
    print(f'Local editor: http://{HOST}:{PORT}/editor (Ctrl+C to stop)')
    webbrowser.open(f'http://{HOST}:{PORT}/editor')
    try: ThreadingHTTPServer((HOST,PORT),Handler).serve_forever()
    except KeyboardInterrupt: print('Stopped')
