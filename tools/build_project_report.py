#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re
from datetime import datetime, timezone
from pathlib import Path

SENSITIVE_LINE=re.compile(r"(?i)(password|senha|passwd|secret|segredo|api[ _-]?key|access[ _-]?token|refresh[ _-]?token|authorization|database_url|connection[ _-]?string|private[ _-]?key|client[ _-]?secret)")
TOKEN=re.compile(r"(?i)\b(?:sk-[a-z0-9_-]{12,}|ghp_[a-z0-9]{12,}|github_pat_[a-z0-9_]{12,}|eyJ[a-z0-9_.-]{20,})\b")
URI_CREDENTIALS=re.compile(r"(://[^\s/:@]+:)[^@\s/]+(@)")
SAFE_TOP_LEVEL=("docs/DEVELOPMENT_GOVERNANCE.md","docs/PRODUCT_REPORTS.md")
SAFE_DIRS=(("docs/issues","Issues"),("docs/reviews","Revisões"),("docs/ideas","Ideias"))

def sanitize(text):
    out=[]
    for raw in text.splitlines():
        line=raw.rstrip()
        if SENSITIVE_LINE.search(line): out.append('[conteúdo sensível omitido]'); continue
        line=URI_CREDENTIALS.sub(r"\1[REDACTED]\2",line)
        line=TOKEN.sub('[REDACTED]',line)
        out.append(line[:2000]+(' …' if len(line)>2000 else ''))
    return '\n'.join(out).strip()[:24000]

def title_for(path,content):
    for line in content.splitlines():
        if line.startswith('# '): return line[2:].strip()[:180]
    return path.stem.replace('_',' ').replace('-',' ').title()

def collect(root):
    candidates=[]
    for item in SAFE_TOP_LEVEL:
        path=root/item
        if path.is_file(): candidates.append((path,'Governança'))
    for directory,category in SAFE_DIRS:
        base=root/directory
        if base.is_dir(): candidates.extend((p,category) for p in sorted(base.glob('*.md'),reverse=True))
    docs=[]
    for path,category in candidates[:80]:
        safe=sanitize(path.read_text(encoding='utf-8',errors='replace'))
        if safe: docs.append({'id':path.relative_to(root).as_posix().replace('/','-').replace('.md',''),'category':category,'title':title_for(path,safe),'source':path.relative_to(root).as_posix(),'content':safe})
    return docs

def main():
    p=argparse.ArgumentParser();p.add_argument('--project',required=True);p.add_argument('--output',required=True);a=p.parse_args();root=Path.cwd()
    payload={'schema_version':1,'project':a.project,'generated_at':datetime.now(timezone.utc).isoformat(),'privacy':{'mode':'sanitized_allowlist','notice':'Relatório gerado apenas de documentos permitidos. Padrões de credenciais e segredos são omitidos antes da publicação.'},'documents':collect(root)}
    output=root/a.output;output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
if __name__=='__main__': main()
