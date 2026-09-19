#!/usr/bin/env python3
"""AfterVolt's local-only editor. Never publish this server to the Internet."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json
import os
import re
import secrets
import subprocess
import webbrowser

ROOT = Path(__file__).resolve().parent
HOST, PORT = '127.0.0.1', 8765
CSRF = secrets.token_urlsafe(32)
CONTENT = ROOT / 'content.json'
ASSETS = ROOT / 'assets'
MAX_IMAGE_BYTES = 8 * 1024 * 1024
IMAGE_EXTENSIONS = {'image/jpeg': '.jpg', 'image/png': '.png', 'image/webp': '.webp', 'image/gif': '.gif'}
REMOTE = 'Neurvs/AfterVoltRecords'


def image_type(data):
    """Accept browser-safe raster images, never SVG/HTML or arbitrary file types."""
    if data.startswith(b'\xff\xd8\xff'): return 'image/jpeg'
    if data.startswith(b'\x89PNG\r\n\x1a\n') and data[12:16] == b'IHDR': return 'image/png'
    if data[:4] == b'RIFF' and data[8:12] == b'WEBP': return 'image/webp'
    if data.startswith((b'GIF87a', b'GIF89a')): return 'image/gif'
    return None

ADMIN = r'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AfterVolt · Content Studio</title><style>
:root{color-scheme:dark;--bg:#0b0712;--card:#1a1125;--accent:#bb80ff;--ink:#f8f2ff;--muted:#c4b3d5}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at top right,#382050,#0b0712 60%);color:var(--ink);font:16px/1.5 system-ui,sans-serif}
main{max-width:1100px;margin:auto;padding:32px 22px 100px}header{display:flex;align-items:center;justify-content:space-between;gap:15px;flex-wrap:wrap}h1{font-size:clamp(2rem,5vw,3.8rem);margin:0}h2{margin:0 0 14px;font-size:1.5rem}.sub{color:var(--muted);margin:2px 0 30px}
section{border:1px solid #634776;background:#190f25e8;border-radius:14px;padding:23px;margin:19px 0}label{display:block;font-size:.87rem;color:#e2cef8;margin:14px 0 5px;font-weight:650}
input,textarea{width:100%;background:#0d0814;border:1px solid #715888;border-radius:7px;padding:11px 12px;color:var(--ink);font:inherit}input[type=file]{font-size:.85rem}
textarea{min-height:95px;resize:vertical}input:focus,textarea:focus{outline:2px solid var(--accent)}button,a.action{background:var(--accent);color:#170c23;border:none;padding:11px 16px;border-radius:8px;font-weight:760;cursor:pointer;text-decoration:none;display:inline-block;font:inherit}
button.secondary,a.secondary{background:#30213e;color:var(--ink);border:1px solid #7c5895}button:disabled{opacity:.5;cursor:wait}.bar{display:flex;gap:9px;flex-wrap:wrap;align-items:center}.item{border:1px solid #4b375d;background:#120b1b;border-radius:11px;padding:17px;margin:14px 0}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.help{font-size:.8rem;color:var(--muted)}#status{white-space:pre-wrap;min-height:26px;color:#cbb6ed}#status.good{color:#8cedc6}#status.bad{color:#ff9fa9}code{color:#dfbeff}@media(max-width:650px){.grid{grid-template-columns:1fr}section{padding:15px}}
</style></head><body><main>
<header><div><p style="letter-spacing:.19em;color:#bb80ff;font-size:.8rem">AFTERVOLT / RECORDS</p><h1>Content Studio</h1><p class="sub">Edit the website without touching HTML. This editor runs only on this computer.</p></div><a class="action secondary" href="/" target="_blank">Preview site ↗</a></header>
<section><h2>Homepage and contact</h2><label for="tagline">Small headline</label><input id="tagline"><label for="intro">Homepage introduction</label><textarea id="intro"></textarea><label for="about">About the label</label><textarea id="about"></textarea><label for="contactText">Contact description</label><textarea id="contactText"></textarea><div class="grid"><div><label for="contactEmail">Public booking email (optional)</label><input id="contactEmail" type="email" placeholder="bookings@example.com"></div><div><label for="socialUrl">Main music/social URL (optional)</label><input id="socialUrl" type="url" placeholder="https://..."></div></div></section>
<section><div class="bar"><h2 style="flex:1">Releases</h2><button type="button" id="addRelease">+ Add release</button></div><p class="help">Select an image below and click <b>Upload cover</b>. Its path will be filled in automatically; click <b>Publish to website</b> to send the image and release details to GitHub. You can also paste a public HTTPS image URL.</p><div id="releases"></div></section>
<section><div class="bar"><h2 style="flex:1">Artists</h2><button type="button" id="addArtist">+ Add artist</button></div><div id="artists"></div></section>
<section><h2>Save and publish</h2><p class="help">Save draft updates files on this computer only. Publish commits <code>content.json</code> and any referenced local cover images, then pushes them to GitHub. GitHub Pages deploys the update automatically.</p><div class="bar"><button type="button" class="secondary" id="save">Save draft</button><button type="button" id="publish">Publish to website ↗</button></div><p id="status" role="status" aria-live="polite"></p></section>
</main><script>
const TOKEN='__CSRF__';let data,uploadsInProgress=0;
const byId=id=>document.getElementById(id);
function field(parent,label,value,key){const wrap=document.createElement('div'),lbl=document.createElement('label'),input=document.createElement('input');lbl.textContent=label;input.value=value||'';input.dataset.key=key;wrap.append(lbl,input);parent.append(wrap);return input;}
function drawRows(kind){const box=byId(kind);box.replaceChildren();(data[kind]||[]).forEach((entry,index)=>{const div=document.createElement('div');div.className='item';const top=document.createElement('div');top.className='bar';const title=document.createElement('strong');title.style.flex='1';title.textContent=kind==='releases'?`Release ${index+1}`:`Artist ${index+1}`;const del=document.createElement('button');del.type='button';del.className='secondary';del.textContent='Remove';del.onclick=()=>{if(confirm(`Remove this ${kind==='releases'?'release':'artist'}?`)){capture();data[kind].splice(index,1);drawRows(kind)}};top.append(title,del);div.append(top);const grid=document.createElement('div');grid.className='grid';if(kind==='releases'){field(grid,'Release title',entry.title,'title');field(grid,'Artist',entry.artist,'artist');field(grid,'Catalog number (optional)',entry.catalog,'catalog');field(grid,'Music URL (HTTPS)',entry.url,'url');const cover=field(grid,'Cover artwork URL or assets/ path',entry.cover,'cover');const wrap=document.createElement('div'),label=document.createElement('label'),choose=document.createElement('input'),upload=document.createElement('button'),note=document.createElement('p');label.textContent='Choose cover image (JPG, PNG, WebP or GIF · max 8 MB)';choose.type='file';choose.accept='image/jpeg,image/png,image/webp,image/gif';upload.type='button';upload.textContent='Upload cover';upload.style.marginTop='8px';note.className='help';note.setAttribute('role','status');wrap.append(label,choose,upload,note);grid.append(wrap);upload.onclick=async()=>{const file=choose.files[0];if(!file){note.textContent='Choose an image first.';return}if(file.size>8*1024*1024){note.textContent='Image is too large. Maximum: 8 MB.';return}upload.disabled=true;uploadsInProgress++;byId('publish').disabled=true;byId('save').disabled=true;note.textContent='Uploading image to this computer…';try{const response=await fetch('/api/upload',{method:'POST',headers:{'Content-Type':file.type||'application/octet-stream','X-AfterVolt-Token':TOKEN},body:file});const result=await response.json();if(!response.ok)throw new Error(result.error||'Upload failed');if(!data.releases.includes(entry))throw new Error('Release was removed during upload. Add it again to use the uploaded image.');cover.value=result.path;entry.cover=result.path;note.textContent='✓ Image uploaded locally. Click Publish to put it on the live website.';show('Image ready! Remember to Publish to website.',true);}catch(e){note.textContent='Upload error: '+e.message;show(e.message)}finally{uploadsInProgress--;upload.disabled=false;byId('save').disabled=false;byId('publish').disabled=uploadsInProgress>0}};}else{field(grid,'Artist name',entry.name,'name');field(grid,'Artist profile/music URL (HTTPS)',entry.url,'url');}div.append(grid);box.append(div);});}
function capture(){for(const key of ['tagline','intro','about','contactText','contactEmail','socialUrl'])data[key]=byId(key).value;for(const kind of ['releases','artists'])byId(kind).querySelectorAll('.item').forEach((div,i)=>{const target=data[kind][i];for(const input of div.querySelectorAll('input[data-key]'))target[input.dataset.key]=input.value;});}
function show(message,good=false){const el=byId('status');el.textContent=message;el.className=good?'good':'bad';}
async function api(path,payload){const response=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json','X-AfterVolt-Token':TOKEN},body:JSON.stringify(payload)});const result=await response.json();if(!response.ok)throw new Error(result.error||'Unknown error');return result;}
async function save(){capture();const result=await api('/api/save',data);show(result.message,true);return result;}
byId('save').onclick=async()=>{try{await save()}catch(e){show(e.message)}};
byId('publish').onclick=async()=>{if(uploadsInProgress){show('Wait until the image upload finishes.');return}const button=byId('publish');button.disabled=true;try{await save();show('Publishing…');const result=await api('/api/publish',{});show(result.message,true)}catch(e){show(e.message)}finally{button.disabled=uploadsInProgress>0}};
byId('addRelease').onclick=()=>{capture();data.releases.push({title:'',artist:'',catalog:'',url:'',cover:''});drawRows('releases')};
byId('addArtist').onclick=()=>{capture();data.artists.push({name:'',url:''});drawRows('artists')};
fetch('/api/content').then(r=>r.json()).then(json=>{data=json;for(const key of ['tagline','intro','about','contactText','contactEmail','socialUrl'])byId(key).value=data[key]||'';drawRows('releases');drawRows('artists');show('Ready. Changes are not published until you click Publish.',true)}).catch(e=>show(`Cannot load content: ${e.message}`));
</script></body></html>'''.replace('__CSRF__',CSRF)


def validate(raw):
    if not isinstance(raw,dict): raise ValueError('Invalid document.')
    result={}
    for key in ('tagline','intro','about','contactText','contactEmail','socialUrl'):
        value=raw.get(key,'')
        if not isinstance(value,str) or len(value)>10000: raise ValueError(f'Invalid {key}.')
        result[key]=value.strip()
    email=result['contactEmail']
    if email and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email): raise ValueError('Enter a valid contact email or leave it blank.')
    def valid_url(value,allow_asset=False):
        return not value or (len(value)<2048 and bool(re.fullmatch(r'https://[^\s<>"\']+',value,re.I))) or (allow_asset and bool(re.fullmatch(r'assets/[a-zA-Z0-9_./-]+',value)) and '..' not in value)
    if not valid_url(result['socialUrl']): raise ValueError('Social URL must start with https://')
    for kind,keys in [('releases',('title','artist','catalog','url','cover')),('artists',('name','url'))]:
        entries=raw.get(kind,[])
        if not isinstance(entries,list) or len(entries)>100: raise ValueError(f'Too many {kind}.')
        result[kind]=[]
        for entry in entries:
            if not isinstance(entry,dict): raise ValueError(f'Invalid {kind} entry.')
            item={}
            for key in keys:
                value=entry.get(key,'')
                if not isinstance(value,str) or len(value)>2048: raise ValueError(f'Invalid {kind} {key}.')
                item[key]=value.strip()
            if not item['title' if kind=='releases' else 'name']: raise ValueError(f'Each {kind[:-1]} needs a title/name.')
            if not valid_url(item['url']): raise ValueError('Music and artist links must start with https://')
            if 'cover' in item and not valid_url(item['cover'],allow_asset=True): raise ValueError('Artwork must be https:// URL or assets/file.jpg')
            result[kind].append(item)
    return result


def git(*args,timeout=30):
    env=os.environ.copy();env['GIT_TERMINAL_PROMPT']='0'
    process=subprocess.run(['git',*args],cwd=ROOT,capture_output=True,text=True,timeout=timeout,env=env)
    if process.returncode: raise RuntimeError((process.stderr or process.stdout or 'Git command failed').strip()[:650])
    return process.stdout.strip()


def publish():
    if not (ROOT/'.git').exists(): raise RuntimeError('This folder is not a Git clone. See README: clone the repo and copy these files into it first.')
    url=git('remote','get-url','origin')
    if not (url.rstrip('/').removesuffix('.git') in (f'https://github.com/{REMOTE}',f'git@github.com:{REMOTE}')):
        raise RuntimeError('Unexpected Git remote. Refusing to push to a different repository.')
    branch=git('branch','--show-current')
    if branch!='main': raise RuntimeError('Switch to the main branch before publishing.')
    git('fetch','origin','main',timeout=45)
    relation=git('rev-list','--left-right','--count','HEAD...origin/main').split()
    if len(relation)!=2 or int(relation[1])!=0:
        raise RuntimeError('GitHub has newer changes. Ask Agustin to sync this checkout with git pull --ff-only before publishing (preserve any local drafts).')
    content=json.loads(CONTENT.read_text(encoding='utf-8'))
    paths=['content.json']
    for release in content.get('releases',[]):
        cover=release.get('cover','')
        if cover.startswith('assets/'):
            if not valid_asset_path(cover) or not (ROOT/cover).is_file():
                raise RuntimeError(f'Cover image missing from the website folder: {cover}. Upload it again before publishing.')
            paths.append(cover)
    paths=list(dict.fromkeys(paths))
    tracked=git('status','--porcelain','--',*paths)
    if not tracked: return 'No new changes to publish. Website already matches the local draft.'
    git('add','--',*paths)
    git('commit','-m','Update AfterVolt website content and cover images','--only','--',*paths)
    git('push','origin','main',timeout=60)
    return 'Published! A Git commit was pushed to GitHub. The live site usually updates within a few minutes.'


def valid_asset_path(value):
    return bool(re.fullmatch(r'assets/[a-zA-Z0-9_./-]+',value)) and '..' not in value and Path(value).suffix.lower() in IMAGE_EXTENSIONS.values()


class Handler(BaseHTTPRequestHandler):
    def send(self,status,content,ctype='text/html; charset=utf-8'):
        body=content.encode('utf-8') if isinstance(content,str) else content
        self.send_response(status);self.send_header('Content-Type',ctype);self.send_header('Content-Length',str(len(body)))
        self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Security-Policy',"default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; img-src 'self' data: https:; connect-src 'self'; frame-ancestors 'none'")
        self.end_headers();self.wfile.write(body)
    def json(self,status,value):self.send(status,json.dumps(value,ensure_ascii=False),'application/json; charset=utf-8')
    def do_GET(self):
        if self.headers.get('Host')!=f'{HOST}:{self.server.server_port}':
            return self.send(403,'Invalid host','text/plain; charset=utf-8')
        if self.path in ('/','/index.html'):return self.send(200,(ROOT/'index.html').read_bytes())
        if self.path=='/editor':return self.send(200,ADMIN)
        if self.path in ('/api/content','/content.json'):return self.send(200,CONTENT.read_bytes(),'application/json; charset=utf-8')
        if self.path.startswith('/assets/'):
            path=self.path[1:].split('?',1)[0]
            if valid_asset_path(path):
                target=(ROOT/path).resolve()
                if target.is_relative_to(ASSETS.resolve()) and target.is_file():
                    content_type={'.jpg':'image/jpeg','.jpeg':'image/jpeg','.png':'image/png','.webp':'image/webp','.gif':'image/gif'}[target.suffix.lower()]
                    return self.send(200,target.read_bytes(),content_type)
        self.send(404,'Not found','text/plain; charset=utf-8')
    def do_POST(self):
        try:
            if self.headers.get('Host')!=f'{HOST}:{self.server.server_port}':raise ValueError('Invalid host.')
            origin=self.headers.get('Origin')
            if origin not in (f'http://{HOST}:{PORT}',None):raise ValueError('Invalid request origin.')
            if self.headers.get('X-AfterVolt-Token')!=CSRF:raise ValueError('Invalid editor session.')
            if self.path=='/api/upload':
                content_type=self.headers.get('Content-Type','').split(';')[0].strip().lower()
                if content_type not in (*IMAGE_EXTENSIONS,'application/octet-stream'):
                    raise ValueError('Choose a JPG, PNG, WebP or GIF image.')
                size=int(self.headers.get('Content-Length','0'))
                if size<16 or size>MAX_IMAGE_BYTES:raise ValueError('Image must be smaller than 8 MB.')
                raw=self.rfile.read(size)
                detected=image_type(raw)
                if not detected or (content_type!='application/octet-stream' and content_type!=detected):
                    raise ValueError('File contents are not a valid supported image type.')
                if ASSETS.is_symlink():raise ValueError('Artwork folder must not be a symbolic link.')
                ASSETS.mkdir(exist_ok=True)
                if not ASSETS.is_dir():raise ValueError('Artwork folder is not a directory.')
                relative=f'assets/cover-{secrets.token_hex(12)}{IMAGE_EXTENSIONS[detected]}'
                with (ROOT/relative).open('xb') as image: image.write(raw)
                return self.json(200,{'path':relative,'message':'Cover image saved locally.'})
            if self.headers.get('Content-Type','').split(';')[0].strip()!='application/json':raise ValueError('Expected JSON.')
            size=int(self.headers.get('Content-Length','0'))
            if size<2 or size>500000:raise ValueError('Invalid request size.')
            payload=json.loads(self.rfile.read(size))
            if self.path=='/api/save':
                value=validate(payload);tmp=CONTENT.with_suffix('.json.tmp')
                tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n');tmp.replace(CONTENT)
                return self.json(200,{'message':'Draft saved on this computer. Click Publish to update the live website.'})
            if self.path=='/api/publish':return self.json(200,{'message':publish()})
            self.json(404,{'error':'Not found.'})
        except (ValueError,RuntimeError,subprocess.TimeoutExpired,OSError,json.JSONDecodeError) as error:
            self.json(400,{'error':str(error)[:750]})
    def log_message(self,fmt,*args):pass

if __name__=='__main__':
    print(f'AfterVolt local editor: http://{HOST}:{PORT}/editor')
    print('Only this computer can access the editor. Press Ctrl+C to stop.')
    try:
        webbrowser.open(f'http://{HOST}:{PORT}/editor')
        ThreadingHTTPServer((HOST,PORT),Handler).serve_forever()
    except KeyboardInterrupt:
        print('\nEditor stopped.')
