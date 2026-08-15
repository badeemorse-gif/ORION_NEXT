"""Safe ORION synchronization controller.

DEV sync pushes only the currently checked-out branch. MAIN and ALL are
external mirrors and are forbidden from writing inside PROJECT_ROOT.
"""
from __future__ import annotations
import hashlib, io, os, shutil, subprocess, sys, tarfile, uuid
from pathlib import Path
from typing import NoReturn
PROJECT_ROOT = Path(os.environ.get("ORION_PROJECT_ROOT", Path(__file__).resolve().parents[1])).resolve()
MAIN_ROOT = PROJECT_ROOT.parent / "ORION_NEXT_MAIN"
ALL_ROOT = PROJECT_ROOT.parent / "ORION_NEXT_ALL_BRANCHES"
REMOTE = os.environ.get("ORION_REMOTE", "origin")
def fail(message: str) -> NoReturn: raise RuntimeError(message)
def run_git(*args: str, cwd: Path = PROJECT_ROOT, check: bool = True) -> str:
    r=subprocess.run(["git",*args],cwd=str(cwd),text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,encoding="utf-8",errors="replace")
    out=r.stdout.strip()
    if check and r.returncode: fail(out or f"git {' '.join(args)} failed")
    return out
def require_checkout():
    if not (PROJECT_ROOT/".git").is_dir(): fail(f"PROJECT_ROOT is not a Git checkout: {PROJECT_ROOT}")
    remote=run_git("remote","get-url",REMOTE).replace("\\","/").rstrip("/")
    if "github.com/badeemorse-gif/ORION_NEXT" not in remote: fail(f"Unexpected Git remote: {remote}")
def current_branch():
    b=run_git("branch","--show-current")
    if not b: fail("Detached HEAD is refused for DEV sync")
    return b
def safe_branch_path(branch):
    parts=branch.split("/")
    if not branch or branch.startswith("/") or "\\" in branch or any(p in ("",".","..") for p in parts): fail(f"Unsafe branch name: {branch!r}")
    target=(ALL_ROOT/"__branches__"/Path(*parts)).resolve(); base=(ALL_ROOT/"__branches__").resolve()
    if os.path.commonpath([str(base),str(target)])!=str(base): fail(f"Unsafe branch destination: {target}")
    return target
def ensure_external(dest):
    dest=dest.resolve(); project=PROJECT_ROOT.resolve()
    if dest==project or project in dest.parents or dest==project.parent: fail(f"REFUSED mirror destination: {dest}")
    dest.parent.mkdir(parents=True,exist_ok=True)
def archive(ref): return subprocess.check_output(["git","archive","--format=tar",ref],cwd=str(PROJECT_ROOT),stderr=subprocess.STDOUT)
def manifest(data):
    out={}
    with tarfile.open(fileobj=io.BytesIO(data),mode="r:") as tar:
        for m in tar.getmembers():
            rel=m.name.replace("\\","/").strip("/")
            if not rel: continue
            if m.isdir(): out[rel]=("dir",)
            elif m.issym(): out[rel]=("link",m.linkname)
            elif m.isfile():
                s=tar.extractfile(m); payload=s.read() if s else fail(f"Cannot read {rel}")
                out[rel]=("file",len(payload),hashlib.sha256(payload).hexdigest())
            else: fail(f"Unsupported archive member: {rel}")
    for rel in list(out):
        p=Path(rel).parent
        while p!=Path("."): out.setdefault(p.as_posix(),("dir",)); p=p.parent
    return out
def local_manifest(root):
    out={}
    if not root.is_dir(): return out
    for base,dirs,files in os.walk(root,topdown=True,followlinks=False):
        bp=Path(base); dirs[:]=[d for d in dirs if d!=".git"]
        rb=bp.relative_to(root)
        if rb!=Path("."): out[rb.as_posix()]=("dir",)
        for name in files:
            p=bp/name; rel=p.relative_to(root).as_posix()
            if p.is_symlink(): out[rel]=("link",os.readlink(p))
            else: out[rel]=("file",p.stat().st_size,hashlib.sha256(p.read_bytes()).hexdigest())
    return out
def remove_path(p):
    if p.is_symlink() or p.is_file(): p.unlink()
    elif p.is_dir(): shutil.rmtree(p)
def materialize(branch,destination):
    destination=destination.resolve(); ensure_external(destination)
    data=archive(f"{REMOTE}/{branch}"); expected=manifest(data)
    stage=destination.parent/f".{destination.name}.stage-{uuid.uuid4().hex}"; backup=destination.parent/f".{destination.name}.backup-{uuid.uuid4().hex}"
    try:
        stage.mkdir();
        with tarfile.open(fileobj=io.BytesIO(data),mode="r:") as tar: tar.extractall(stage,filter="data")
        if local_manifest(stage)!=expected: fail(f"Snapshot verification failed: {branch}")
        if destination.exists(): destination.rename(backup)
        stage.rename(destination)
        if local_manifest(destination)!=expected:
            remove_path(destination)
            if backup.exists(): backup.rename(destination)
            fail(f"Post-install verification failed: {branch}")
        if backup.exists(): remove_path(backup)
    except Exception:
        if stage.exists(): remove_path(stage)
        if backup.exists() and not destination.exists(): backup.rename(destination)
        raise
def sync_development():
    require_checkout(); branch=current_branch();
    if not run_git("status","--short"): print(f"DEV SYNC: clean; branch={branch}"); return 0
    run_git("add","-A")
    if subprocess.run(["git","diff","--cached","--quiet"],cwd=str(PROJECT_ROOT)).returncode==0: return 0
    run_git("commit","-m",f"sync: update ORION ({branch})"); run_git("push","-u",REMOTE,branch); print(f"DEV SYNC SUCCESS: {branch}"); return 0
def sync_main(): require_checkout(); run_git("fetch","--prune",REMOTE,"main"); materialize("main",MAIN_ROOT); print(f"MAIN MIRROR SUCCESS: {MAIN_ROOT}"); return 0
def sync_all():
    require_checkout(); run_git("fetch","--prune",REMOTE)
    branches=sorted(b for b in run_git("for-each-ref","--format=%(refname:strip=3)",f"refs/remotes/{REMOTE}").splitlines() if b and b!="HEAD")
    for b in branches: materialize(b,safe_branch_path(b))
    print(f"ALL MIRRORS SUCCESS: {len(branches)}"); return 0
def main(argv):
    if len(argv)!=2 or argv[1] not in {"dev","main","all"}: print("Usage: python tools/orion_sync_safe.py {dev|main|all}"); return 2
    try: return {"dev":sync_development,"main":sync_main,"all":sync_all}[argv[1]]()
    except Exception as exc: print(f"SYNC REFUSED/FAILED: {exc}",file=sys.stderr); return 1
if __name__=="__main__": raise SystemExit(main(sys.argv))
