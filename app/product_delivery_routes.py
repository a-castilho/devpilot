from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import Project, ProviderCredential, Repository, Workspace
from app.security import Principal, Role, require_access, require_roles, require_super_admin
from app.services.audit import record
from app.services.vault import Vault

NEON_API="https://console.neon.tech/api/v2"; RENDER_API="https://api.render.com/v1"; VERCEL_API="https://api.vercel.com"; PROVIDERS=("neon","render","vercel"); CREDENTIAL_LABEL="Principal"
router=APIRouter(prefix="/api",dependencies=[Depends(require_access)])
class ProviderCredentialInput(BaseModel):
    token:str=Field(min_length=8,max_length=10_000); account_id:str=Field(default="",max_length=200)
def operator(principal:Principal=Depends(require_roles(Role.OWNER,Role.ADMIN)))->Principal:return principal
def workspace(db):
    item=db.scalar(select(Workspace).where(Workspace.slug=="default"))
    if not item:item=Workspace(name="DevPilot",slug="default");db.add(item);db.flush()
    return item
def project_or_404(db,project_id):
    ws=workspace(db);item=db.scalar(select(Project).where(Project.id==project_id,Project.workspace_id==ws.id))
    if not item:raise HTTPException(status_code=404,detail="Projeto não encontrado.")
    return item
def config_for(project):
    try:value=json.loads(project.codex_config or "{}")
    except (TypeError,ValueError,json.JSONDecodeError):value={}
    return value if isinstance(value,dict) else {}
def save_delivery(db,project,delivery):
    config=config_for(project);config["delivery"]=delivery;project.codex_config=json.dumps(config,ensure_ascii=False,separators=(",",":"));db.commit();db.refresh(project)
def credential_row(db,workspace_id,provider):return db.scalar(select(ProviderCredential).where(ProviderCredential.workspace_id==workspace_id,ProviderCredential.provider==f"cloud-{provider}",ProviderCredential.label==CREDENTIAL_LABEL))
def connection(db,workspace_id,provider):
    item=credential_row(db,workspace_id,provider)
    if not item or not item.enabled:return None
    try:payload=json.loads(Vault().decrypt(item.encrypted_secret))
    except (ValueError,TypeError,json.JSONDecodeError):return None
    token=str(payload.get("token") or "").strip() if isinstance(payload,dict) else ""
    return (token,str(payload.get("account_id") or "").strip()) if token else None
def headers(token):return {"Authorization":f"Bearer {token}","Accept":"application/json"}
def request_json(client,provider,method,url,token,*,payload=None,params=None):
    try:r=client.request(method,url,headers=headers(token),json=payload,params=params)
    except httpx.HTTPError as e:raise RuntimeError(f"{provider}: indisponível") from e
    if r.status_code>=400:raise RuntimeError(f"{provider}: HTTP {r.status_code}")
    if not r.content:return None
    try:return r.json()
    except ValueError as e:raise RuntimeError(f"{provider}: resposta inválida") from e
def repository_full_name(db,project):
    repo=db.scalar(select(Repository).where(Repository.project_id==project.id))
    if repo and repo.full_name:return repo.full_name
    value=str(project.repository_url or "").removesuffix(".git")
    if "github.com/" in value:return value.split("github.com/",1)[1].strip("/")
    if value.startswith("git@github.com:"):return value.split(":",1)[1].strip("/")
    return value.strip("/")
def initial_delivery(project):
    current=config_for(project).get("delivery")
    if isinstance(current,dict):current.setdefault("providers",{});current.setdefault("checks",[]);return current
    return {"status":"pending","url":"","providers":{},"checks":[],"last_error":"","updated_at":datetime.now(timezone.utc).isoformat()}
def selected_providers(project):
    blueprint=config_for(project).get("project_blueprint")
    if not isinstance(blueprint,dict):return list(PROVIDERS)
    databases={str(x).lower() for x in blueprint.get("databases",[]) if x};backend={str(x).lower() for x in blueprint.get("backend",[]) if x};frontend={str(x).lower() for x in blueprint.get("frontend",[]) if x};selected=[]
    if not databases or "postgresql" in databases:selected.append("neon")
    if not backend or any(x!="none" for x in backend):selected.append("render")
    if not frontend or any(x!="none" for x in frontend):selected.append("vercel")
    return selected
def provision_neon(client,token,account_id,project,state):
    neon=state.setdefault("providers",{}).setdefault("neon",{})
    if not neon.get("project_id"):
        body={"name":project.slug,"pg_version":18,"branch":{"name":"main","role_name":"app","database_name":"app"}}
        if account_id:body["org_id"]=account_id
        created=request_json(client,"neon","POST",f"{NEON_API}/projects",token,payload={"project":body}) or {};pd=created.get("project") or {};branch=created.get("branch") or {};neon.update({"project_id":str(pd.get("id") or ""),"main_branch_id":str(branch.get("id") or ""),"database_name":str(((created.get("databases") or [{}])[0]).get("name") or "app"),"role_name":str(((created.get("roles") or [{}])[0]).get("name") or "app")})
        if not neon["project_id"] or not neon["main_branch_id"]:raise RuntimeError("neon: IDs não retornados")
    if not neon.get("homolog_branch_id"):
        created=request_json(client,"neon","POST",f"{NEON_API}/projects/{neon['project_id']}/branches",token,payload={"branch":{"name":"homolog","parent_id":neon["main_branch_id"]},"endpoints":[{"type":"read_write"}]}) or {};neon["homolog_branch_id"]=str((created.get("branch") or {}).get("id") or "")
        if not neon["homolog_branch_id"]:raise RuntimeError("neon: homologação não retornada")
    uri=request_json(client,"neon","GET",f"{NEON_API}/projects/{neon['project_id']}/connection_uri",token,params={"branch_id":neon["homolog_branch_id"],"database_name":neon.get("database_name") or "app","role_name":neon.get("role_name") or "app","pooled":"true"}) or {};database_url=str(uri.get("uri") or "")
    if not database_url:raise RuntimeError("neon: DATABASE_URL não retornada")
    neon["status"]="ready";return database_url
def provision_render(client,token,account_id,project,state,database_url):
    render=state.setdefault("providers",{}).setdefault("render",{})
    if render.get("service_id") and render.get("url"):return str(render["url"])
    if not account_id:raise RuntimeError("render: account ID não configurado")
    body={"type":"web_service","name":f"{project.slug}-homolog","ownerId":account_id,"repo":project.repository_url,"branch":project.default_branch or "main","autoDeploy":"yes","envVars":[{"key":"APP_ENV","value":"homolog"}],"serviceDetails":{"runtime":"docker","plan":"free","healthCheckPath":"/health","envSpecificDetails":{"dockerfilePath":"./Dockerfile"}}}
    if database_url:body["envVars"].append({"key":"DATABASE_URL","value":database_url})
    created=request_json(client,"render","POST",f"{RENDER_API}/services",token,payload=body) or {};service=created.get("service") if isinstance(created.get("service"),dict) else created;render["service_id"]=str(service.get("id") or "");render["url"]=str((service.get("serviceDetails") or {}).get("url") or service.get("url") or "")
    if not render["service_id"]:raise RuntimeError("render: serviço não retornado")
    render["status"]="provisioned";return str(render.get("url") or "")
def provision_vercel(client,token,account_id,project,state,backend_url,repo_full_name):
    vercel=state.setdefault("providers",{}).setdefault("vercel",{});params={"teamId":account_id} if account_id else None
    if not vercel.get("project_id"):
        created=request_json(client,"vercel","POST",f"{VERCEL_API}/v11/projects",token,params=params,payload={"name":project.slug,"gitRepository":{"type":"github","repo":repo_full_name}}) or {};vercel["project_id"]=str(created.get("id") or "")
        if not vercel["project_id"]:raise RuntimeError("vercel: projeto não retornado")
    if backend_url and not vercel.get("backend_configured"):
        ep={"upsert":"true"};ep.update({"teamId":account_id} if account_id else {});request_json(client,"vercel","POST",f"{VERCEL_API}/v10/projects/{vercel['project_id']}/env",token,params=ep,payload=[{"key":key,"value":backend_url,"type":"encrypted","target":["production","preview"]} for key in ("APP_BACKEND_URL","NEXT_PUBLIC_API_URL","VITE_API_URL")]);vercel["backend_configured"]=True
    # A deployment id without a public URL is stale/incomplete. Recreate it instead of waiting forever.
    if not vercel.get("deployment_id") or not str(vercel.get("url") or "").strip():
        dp={"skipAutoDetectionConfirmation":"1"};dp.update({"teamId":account_id} if account_id else {});parts=repo_full_name.split("/",1)
        if len(parts)!=2:raise RuntimeError("vercel: repositório GitHub inválido")
        deployed=request_json(client,"vercel","POST",f"{VERCEL_API}/v13/deployments",token,params=dp,payload={"name":project.slug,"project":vercel["project_id"],"target":"production","gitSource":{"type":"github","org":parts[0],"repo":parts[1],"ref":project.default_branch or "main"}}) or {};new_id=str(deployed.get("id") or "");raw=str(deployed.get("url") or "").strip()
        if not new_id:raise RuntimeError("vercel: deployment não retornado")
        vercel["deployment_id"]=new_id;vercel["url"]=raw if raw.startswith(("http://","https://")) else (f"https://{raw}" if raw else "")
    vercel["status"]="deploying";return str(vercel.get("url") or "")
def verify(state):
    providers=state.get("providers") if isinstance(state.get("providers"),dict) else {};requested={str(x).lower() for x in state.get("requested",[]) if x}
    if not requested:requested={n for n in PROVIDERS if n in providers}
    render_url=str((providers.get("render") or {}).get("url") or "").rstrip("/");vercel_url=str((providers.get("vercel") or {}).get("url") or "").rstrip("/");targets=[]
    if "render" in requested and render_url:targets.append(("backend",f"{render_url}/health"))
    if "vercel" in requested and vercel_url:targets.append(("frontend",vercel_url))
    checks=[]
    with httpx.Client(timeout=12.0,follow_redirects=True) as client:
        for name,url in targets:
            try:r=client.get(url,headers={"Accept":"application/json,text/html"});code=r.status_code;ok=200<=code<300
            except httpx.HTTPError:code=0;ok=False
            checks.append({"name":name,"ok":ok,"status_code":code,"url":url})
    if "neon" in requested:
        neon=providers.get("neon") or {};ok=str(neon.get("status") or "").lower() in {"ready","provisioned"} and bool(neon.get("project_id") or neon.get("homolog_branch_id"));checks.append({"name":"database","ok":ok,"status_code":200 if ok else 0,"url":"neon://provisioned" if ok else ""})
    required=set();required.update({"database"} if "neon" in requested else set());required.update({"backend"} if "render" in requested else set());required.update({"frontend"} if "vercel" in requested else set());seen={x["name"] for x in checks if x["ok"]};ready=bool(required) and required.issubset(seen)
    return {"status":"ready" if ready else "deploying","url":vercel_url or render_url,"checks":checks,"verified_at":datetime.now(timezone.utc).isoformat()}
def run_delivery(db,project,actor):
    if not project.repository_url:raise HTTPException(status_code=409,detail="O projeto ainda não possui repositório.")
    state=initial_delivery(project);state["status"]="provisioning";state["last_error"]="";state.pop("failed_provider",None);state.pop("blocked_providers",None);state["updated_at"]=datetime.now(timezone.utc).isoformat();selected=selected_providers(project);state["requested"]=selected;missing=[n for n in selected if connection(db,project.workspace_id,n) is None]
    if missing:state["status"]="blocked";state["blocked_providers"]=missing;state["last_error"]="Infraestrutura ainda não configurada pela administração.";save_delivery(db,project,state);return state
    database_url=backend_url=None
    try:
        with httpx.Client(timeout=30.0,follow_redirects=True) as client:
            if "neon" in selected:
                token,account_id=connection(db,project.workspace_id,"neon") or ("","");database_url=provision_neon(client,token,account_id,project,state);save_delivery(db,project,state)
            if "render" in selected:
                token,account_id=connection(db,project.workspace_id,"render") or ("","");backend_url=provision_render(client,token,account_id,project,state,database_url);save_delivery(db,project,state)
            if "vercel" in selected:
                token,account_id=connection(db,project.workspace_id,"vercel") or ("","");provision_vercel(client,token,account_id,project,state,backend_url,repository_full_name(db,project));save_delivery(db,project,state)
    except RuntimeError as e:
        provider=str(e).split(":",1)[0].strip().lower();state["status"]="failed";state["failed_provider"]=provider if provider in PROVIDERS else "cloud";state["last_error"]=str(e)[:300];state["updated_at"]=datetime.now(timezone.utc).isoformat();record(db,workspace_id=project.workspace_id,project_id=project.id,actor=actor,action="project.delivery_failed",outcome="failed",details={"provider":state["failed_provider"],"error":str(e)[:300]});save_delivery(db,project,state);return state
    state.update(verify(state));state["updated_at"]=datetime.now(timezone.utc).isoformat()
    if state["status"]=="ready":state.pop("failed_provider",None);state.pop("blocked_providers",None)
    record(db,workspace_id=project.workspace_id,project_id=project.id,actor=actor,action="project.delivery_verified",outcome="success" if state["status"]=="ready" else "pending",details={"status":state["status"]});save_delivery(db,project,state);return state
@router.get("/delivery/providers")
def provider_status(db:Session=Depends(get_db),_:str=Depends(require_super_admin)):
    ws=workspace(db);return [{"provider":p,"configured":connection(db,ws.id,p) is not None,"account_id":(connection(db,ws.id,p) or ("",""))[1]} for p in PROVIDERS]
@router.put("/delivery/providers/{provider}")
def configure_provider(provider:str,payload:ProviderCredentialInput,db:Session=Depends(get_db),actor:str=Depends(require_super_admin)):
    provider=provider.strip().lower()
    if provider not in PROVIDERS:raise HTTPException(status_code=404,detail="Provedor não suportado.")
    ws=workspace(db);item=credential_row(db,ws.id,provider)
    if not item:item=ProviderCredential(workspace_id=ws.id,provider=f"cloud-{provider}",label=CREDENTIAL_LABEL,encrypted_secret="",models="[]");db.add(item)
    item.encrypted_secret=Vault().encrypt(json.dumps({"token":payload.token,"account_id":payload.account_id.strip()},ensure_ascii=False,separators=(",",":")));item.enabled=True;item.models="[]";record(db,workspace_id=ws.id,actor=actor,action="delivery.provider_configured",details={"provider":provider,"has_account_id":bool(payload.account_id.strip())});db.commit();return {"provider":provider,"configured":True,"account_id":payload.account_id.strip()}
@router.get("/projects/{project_id}/delivery")
def delivery_status(project_id:str,db:Session=Depends(get_db)):return initial_delivery(project_or_404(db,project_id))
@router.post("/projects/{project_id}/delivery/start")
def delivery_start(project_id:str,db:Session=Depends(get_db),principal:Principal=Depends(operator)):return run_delivery(db,project_or_404(db,project_id),principal.actor)
@router.post("/projects/{project_id}/delivery/retry")
def delivery_retry(project_id:str,db:Session=Depends(get_db),principal:Principal=Depends(operator)):return run_delivery(db,project_or_404(db,project_id),principal.actor)
@router.post("/projects/{project_id}/delivery/verify")
def delivery_verify(project_id:str,db:Session=Depends(get_db),principal:Principal=Depends(operator)):
    project=project_or_404(db,project_id);state=initial_delivery(project);state.update(verify(state));state["updated_at"]=datetime.now(timezone.utc).isoformat();record(db,workspace_id=project.workspace_id,project_id=project.id,actor=principal.actor,action="project.delivery_verified",outcome="success" if state["status"]=="ready" else "pending",details={"status":state["status"]});save_delivery(db,project,state);return state
