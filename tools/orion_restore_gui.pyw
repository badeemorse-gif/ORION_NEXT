"""ORION Restore: exact, isolated mirrors for every remote branch.

This module deliberately never checks out, resets, cleans, or writes to the
ORION project. Git is only read from PROJECT_ROOT; every write is under
ALL_ROOT/<safe branch name>.
"""

from __future__ import annotations

import hashlib
import io
import os
import re
import subprocess
import sys
import tarfile
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Iterable, Optional, Tuple

import tkinter as tk
from tkinter import messagebox, scrolledtext

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
REMOTE = "origin"
ALL_ROOT = str(Path(PROJECT_ROOT).parent / "ORION_NEXT_ALL_BRANCHES")
GIT_TIMEOUT = 120
Manifest = Dict[str, Tuple]

class RestoreError(RuntimeError):
    """An error that must prevent ALL SUCCESS from being shown."""

@dataclass(frozen=True)
class BranchStats:
    files: int
    added: int
    updated: int
    removed: int

def run_git(args: Iterable[str], cwd: str, timeout: int = GIT_TIMEOUT,
            binary: bool = False):
    """Run Git with a real timeout and no visible console window on Windows."""
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    command = ["git", *args]
    try:
        process = subprocess.Popen(
            command, cwd=cwd, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE if binary else subprocess.STDOUT,
            text=not binary, encoding=None if binary else "utf-8",
            errors=None if binary else "replace", creationflags=flags,
        )
    except OSError as exc:
        raise RestoreError(f"Unable to start Git: {exc}") from exc
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        process.kill(); process.communicate()
        raise RestoreError(f"Git timed out after {timeout}s: {' '.join(command)}") from exc
    if binary:
        return process.returncode, stdout or b"", stderr or b""
    return process.returncode, [line.rstrip() for line in (stdout or "").splitlines() if line.rstrip()]

def safe_branch_name(name: str) -> str:
    safe = re.sub(r'[<>:"/\\|?*]+', "__", name).strip(" .")
    if not safe: safe = "branch"
    return safe if safe == name else f"{safe}__{hashlib.sha1(name.encode('utf-8')).hexdigest()[:8]}"

def discover_remote_branches(project_root: str, remote: str) -> list[str]:
    code, lines = run_git(["ls-remote", "--heads", remote], project_root)
    if code: raise RestoreError("\n".join(lines) or "Could not read remote branches.")
    branches = [line.split("\t", 1)[1][11:] for line in lines if "\trefs/heads/" in line and line.split("\t", 1)[1][11:]]
    if not branches: raise RestoreError("No branches were found on the remote.")
    return sorted(set(branches), key=lambda value: (value.lower() != "main", value.lower()))

def discover_fetched_branches(project_root: str, remote: str) -> list[str]:
    prefix = f"refs/remotes/{remote}/"
    code, lines = run_git(["for-each-ref", "--format=%(refname)", prefix], project_root)
    if code: raise RestoreError("\n".join(lines) or "Could not enumerate fetched branches.")
    branches = [line[len(prefix):] for line in lines if line.startswith(prefix) and not line.endswith("/HEAD")]
    if not branches: raise RestoreError("The batch fetch produced no remote branch refs.")
    return sorted(set(branches), key=lambda value: (value.lower() != "main", value.lower()))

def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""): digest.update(chunk)
    return digest.hexdigest()

def _add_parent_dirs(manifest: Manifest) -> None:
    for rel in list(manifest):
        parent = rel.rpartition("/")[0]
        while parent:
            manifest.setdefault(parent, ("dir",)); parent = parent.rpartition("/")[0]

def archive_relpath(name: str) -> str:
    rel = name.replace("\\", "/")
    return rel[2:] if rel.startswith("./") else rel

def local_manifest(root: str) -> Manifest:
    result: Manifest = {}
    if not os.path.isdir(root): return result
    for base, dirs, files in os.walk(root, topdown=True, followlinks=False):
        rel_base = os.path.relpath(base, root).replace(os.sep, "/")
        if rel_base != ".": result[rel_base] = ("dir",)
        for name in dirs[:]:
            full=os.path.join(base,name); rel=os.path.relpath(full,root).replace(os.sep,"/")
            if os.path.islink(full): result[rel]=("link",os.readlink(full)); dirs.remove(name)
        for name in files:
            full=os.path.join(base,name); rel=os.path.relpath(full,root).replace(os.sep,"/")
            try: result[rel]=(("link",os.readlink(full)) if os.path.islink(full) else ("file",os.path.getsize(full),sha256_file(full)))
            except OSError as exc: raise RestoreError(f"Unable to read destination file {full}: {exc}") from exc
    return result

def archive_manifest(project_root: str, ref: str) -> tuple[bytes, Manifest]:
    code, archive, error = run_git(["archive", "--format=tar", ref], project_root, binary=True)
    if code: raise RestoreError(f"git archive failed for {ref}: {error.decode('utf-8','replace')}")
    manifest: Manifest={}
    with tarfile.open(fileobj=io.BytesIO(archive),mode="r:") as tar:
        for member in tar.getmembers():
            rel=archive_relpath(member.name)
            if not rel: continue
            if member.isdir(): manifest[rel.rstrip("/")]=( "dir", )
            elif member.issym(): manifest[rel]=( "link", member.linkname )
            elif member.isfile():
                src=tar.extractfile(member)
                if src is None: raise RestoreError(f"Archive entry could not be read: {rel}")
                data=src.read(); manifest[rel]=( "file", len(data), hashlib.sha256(data).hexdigest() )
    _add_parent_dirs(manifest); return archive,manifest

def assert_no_gitlinks(project_root: str, ref: str) -> None:
    code, lines = run_git(["ls-tree","-r",ref],project_root)
    if code: raise RestoreError("\n".join(lines) or f"Could not inspect gitlinks in {ref}.")
    gitlinks=[line.split("\t",1)[1] for line in lines if line.startswith("160000 ") and "\t" in line]
    if gitlinks: raise RestoreError(f"{ref} contains gitlink(s) not materialized by git archive: {', '.join(gitlinks)}. Configure those submodules for a dedicated recursive restore before declaring ALL SUCCESS.")

def safe_target(root: str, rel: str) -> str:
    root_abs=os.path.abspath(root); full=os.path.abspath(os.path.join(root_abs,rel.replace("/",os.sep)))
    if os.path.commonpath([root_abs,full])!=root_abs: raise RestoreError(f"Unsafe archive path: {rel}")
    return full

def remove_any(path: str) -> int:
    if not os.path.lexists(path): return 0
    if os.path.islink(path) or os.path.isfile(path): os.remove(path); return 1
    if os.path.isdir(path):
        count=0
        for name in os.listdir(path): count+=remove_any(os.path.join(path,name))
        os.rmdir(path); return count
    os.remove(path); return 1

def ensure_directory(path: str) -> int:
    removed=remove_any(path) if os.path.lexists(path) and (os.path.islink(path) or not os.path.isdir(path)) else 0
    os.makedirs(path,exist_ok=True); return removed

def ensure_parent_directory(path: str, root: str) -> int:
    root_abs=os.path.abspath(root); parent=os.path.abspath(os.path.dirname(path)); to_create=[]; removed=0
    while parent!=root_abs:
        if os.path.commonpath([root_abs,parent])!=root_abs: raise RestoreError(f"Unsafe destination parent: {path}")
        if os.path.lexists(parent) and (os.path.islink(parent) or not os.path.isdir(parent)): removed+=remove_any(parent)
        to_create.append(parent); parent=os.path.dirname(parent)
    for directory in reversed(to_create): os.makedirs(directory,exist_ok=True)
    return removed

def cleanup_orphan_temps(root: str, target: Manifest) -> int:
    removed=0
    if not os.path.isdir(root): return removed
    for base,dirs,files in os.walk(root,topdown=False):
        for name in files+dirs:
            if ".orion_tmp" not in name: continue
            full=os.path.join(base,name); rel=os.path.relpath(full,root).replace(os.sep,"/")
            if rel not in target: removed+=remove_any(full)
    return removed

def materialize_archive(archive: bytes, root: str, target: Manifest, old: Manifest) -> tuple[int,int,int]:
    root_abs=os.path.abspath(root)
    if root_abs==os.path.abspath(PROJECT_ROOT): raise RestoreError("Refusing to write the primary ORION project.")
    ensure_directory(root_abs); added=updated=0; removed=cleanup_orphan_temps(root_abs,target)
    stale=sorted((rel for rel in old if rel not in target),key=lambda item:item.count("/"),reverse=True)
    for rel in stale:
        full=safe_target(root_abs,rel)
        if os.path.lexists(full): removed+=remove_any(full)
    for rel,signature in sorted(target.items(),key=lambda item:item[0].count("/")):
        if signature[0]=="dir": removed+=ensure_directory(safe_target(root_abs,rel))
    with tarfile.open(fileobj=io.BytesIO(archive),mode="r:") as tar:
        for member in tar.getmembers():
            rel=archive_relpath(member.name)
            if not rel or member.isdir(): continue
            full=safe_target(root_abs,rel)
            if member.issym():
                new_signature=("link",member.linkname)
                if old.get(rel)==new_signature and os.path.islink(full) and os.readlink(full)==member.linkname: continue
                if os.path.lexists(full): remove_any(full)
                removed+=ensure_parent_directory(full,root_abs)
                try: os.symlink(member.linkname,full)
                except OSError as exc: raise RestoreError(f"Unable to create required symlink {full}: {exc}") from exc
                updated+=1 if rel in old else 0; added+=0 if rel in old else 1; continue
            if not member.isfile(): continue
            source=tar.extractfile(member)
            if source is None: raise RestoreError(f"Archive entry could not be read: {rel}")
            data=source.read(); new_signature=("file",len(data),hashlib.sha256(data).hexdigest())
            if old.get(rel)==new_signature and os.path.isfile(full) and not os.path.islink(full): continue
            existed=os.path.lexists(full)
            if existed and (os.path.islink(full) or os.path.isdir(full)): remove_any(full)
            removed+=ensure_parent_directory(full,root_abs)
            temporary=f"{full}.orion_tmp.{uuid.uuid4().hex}"
            with open(temporary,"wb") as handle:
                handle.write(data); handle.flush(); os.fsync(handle.fileno())
            try: os.replace(temporary,full)
            except OSError as exc:
                if os.path.lexists(temporary): remove_any(temporary)
                raise RestoreError(f"Unable to atomically replace {full}: {exc}") from exc
            updated+=1 if existed else 0; added+=0 if existed else 1
    for base,dirs,files in os.walk(root_abs,topdown=False):
        if base!=root_abs and not dirs and not files:
            try: os.rmdir(base)
            except OSError: pass
    return added,updated,removed

def verify_materialized(root: str, target: Manifest) -> None:
    actual=local_manifest(root)
    if actual!=target:
        missing=sorted(set(target)-set(actual)); extra=sorted(set(actual)-set(target)); mismatched=sorted(rel for rel in set(actual)&set(target) if actual[rel]!=target[rel]); details=[]
        if missing: details.append("missing: "+", ".join(missing[:5]))
        if extra: details.append("extra: "+", ".join(extra[:5]))
        if mismatched: details.append("different: "+", ".join(mismatched[:5]))
        raise RestoreError(f"Mirror verification failed for {root}: {'; '.join(details)}")
    for rel in actual:
        if ".orion_tmp" in rel and rel not in target: raise RestoreError(f"Orphan temporary file remains: {rel}")

def sync_repository(project_root: str, all_root: str, remote: str=REMOTE, report: Optional[Callable[[str],None]]=None)->dict[str,BranchStats]:
    project_root=os.path.abspath(project_root); all_root=os.path.abspath(all_root)
    if not os.path.isdir(os.path.join(project_root,".git")): raise RestoreError(f"Project is not a Git checkout: {project_root}")
    if all_root==project_root or os.path.commonpath([project_root,all_root])==project_root: raise RestoreError("ALL destination must be outside the primary project.")
    code,lines=run_git(["fetch","--prune",remote,f"+refs/heads/*:refs/remotes/{remote}/*"],project_root)
    if code: raise RestoreError("\n".join(lines) or "git fetch failed.")
    branches=discover_fetched_branches(project_root,remote); os.makedirs(all_root,exist_ok=True); result={}
    for index,branch in enumerate(branches,1):
        if report: report(f"[{index}/{len(branches)}] {branch}")
        ref=f"{remote}/{branch}"; assert_no_gitlinks(project_root,ref); archive,target=archive_manifest(project_root,ref); destination=os.path.join(all_root,safe_branch_name(branch)); old=local_manifest(destination); added,updated,removed=materialize_archive(archive,destination,target,old); verify_materialized(destination,target); stats=BranchStats(sum(1 for item in target.values() if item[0] in ("file","link")),added,updated,removed); result[branch]=stats
        if report: report(f"    Files: {stats.files} | Added: {stats.added} | Updated: {stats.updated} | Removed: {stats.removed} | SUCCESS")
    return result

class OrionAllRestore:
    def __init__(self,root):
        self.root=root; self.root.title("ORION Restore — ALL"); self.root.geometry("900x610"); self.root.minsize(780,520); self.root.configure(bg="#101820"); self.running=False; self.status=tk.StringVar(value="Discovering remote branches…"); self.total_files=tk.StringVar(value="0"); self.total_added=tk.StringVar(value="0"); self.total_updated=tk.StringVar(value="0"); self.total_removed=tk.StringVar(value="0"); self._build(); self.refresh_branches()
    def _build(self):
        tk.Label(self.root,text="ORION RESTORE",font=("Segoe UI",22,"bold"),bg="#101820",fg="#f2f5f7").pack(pady=(18,2)); tk.Label(self.root,text="GitHub → Local  |  ALL — isolated branch mirrors",font=("Segoe UI",10),bg="#101820",fg="#9aa8b2").pack(); panel=tk.Frame(self.root,bg="#17232d"); panel.pack(fill="x",padx=24,pady=10)
        for label,value in (("Repository","ORION_NEXT"),("Project",PROJECT_ROOT),("Destination",ALL_ROOT)):
            row=tk.Frame(panel,bg="#17232d"); row.pack(fill="x",padx=12,pady=4); tk.Label(row,text=label+":",width=12,anchor="w",bg="#17232d",fg="#9aa8b2",font=("Segoe UI",8,"bold")).pack(side="left"); tk.Label(row,text=value,anchor="w",bg="#17232d",fg="#f2f5f7",font=("Segoe UI",8)).pack(side="left",fill="x",expand=True)
        sr=tk.Frame(self.root,bg="#101820"); sr.pack(fill="x",padx=24,pady=(3,4)); tk.Label(sr,text="STATUS:",bg="#101820",fg="#9aa8b2",font=("Segoe UI",9,"bold")).pack(side="left"); self.status_label=tk.Label(sr,textvariable=self.status,bg="#101820",fg="#3fc36b",font=("Segoe UI",9,"bold")); self.status_label.pack(side="left",padx=8); cards=tk.Frame(self.root,bg="#101820"); cards.pack(fill="x",padx=24,pady=3); self.branch_count_label=None
        for index,(title,variable,color) in enumerate((("BRANCHES",None,"#2eaadc"),("FILES",self.total_files,"#2eaadc"),("ADDED",self.total_added,"#3fc36b"),("UPDATED",self.total_updated,"#2eaadc"),("REMOVED",self.total_removed,"#e05252"))):
            cards.grid_columnconfigure(index,weight=1); card=tk.Frame(cards,bg="#182538"); card.grid(row=0,column=index,sticky="nsew",padx=3); tk.Label(card,text=title,bg="#182538",fg="#9aa8b2",font=("Segoe UI",8,"bold")).pack(anchor="w",padx=8,pady=(6,0))
            if title=="BRANCHES": self.branch_count_label=tk.Label(card,text="0",bg="#182538",fg="#2eaadc",font=("Segoe UI",16,"bold")); self.branch_count_label.pack(anchor="w",padx=8,pady=(0,6))
            else: tk.Label(card,textvariable=variable,bg="#182538",fg=color,font=("Segoe UI",16,"bold")).pack(anchor="w",padx=8,pady=(0,6))
        self.button=tk.Button(self.root,text="Sync ALL — all branches",command=self.start,bg="#2eaadc",fg="white",activebackground="#2eaadc",relief="flat",font=("Segoe UI",12,"bold"),padx=25,pady=10); self.button.pack(pady=(9,6)); tk.Label(self.root,text="No worktrees. The primary project is never switched or written during ALL sync.",bg="#101820",fg="#e0a52e",font=("Segoe UI",8)).pack(); tk.Label(self.root,text="Sync log",bg="#101820",fg="#9aa8b2",font=("Segoe UI",9,"bold")).pack(anchor="w",padx=24,pady=(8,3)); self.output=scrolledtext.ScrolledText(self.root,height=13,bg="#0b1116",fg="#d9e1e6",insertbackground="white",font=("Consolas",9),relief="flat",bd=0,wrap="word"); self.output.pack(fill="both",expand=True,padx=24,pady=(0,14))
    def ui(self,text): self.root.after(0,lambda:(self.output.insert("end",text+"\n"),self.output.see("end")))
    def set_status(self,text,color="#3fc36b"): self.root.after(0,self.status.set,text); self.root.after(0,self.status_label.configure,{"fg":color})
    def refresh_branches(self):
        def worker():
            try: branches=discover_remote_branches(PROJECT_ROOT,REMOTE); self.root.after(0,self.branch_count_label.configure,{"text":str(len(branches))}); self.ui(f"Discovered {len(branches)} remote branches."); self.set_status("Ready to sync")
            except Exception as exc: self.ui(str(exc)); self.set_status("Branch discovery failed","#e05252")
        threading.Thread(target=worker,daemon=True).start()
    def start(self):
        if self.running:return
        self.running=True; self.button.configure(state="disabled",text="Syncing ALL…")
        for value in (self.total_files,self.total_added,self.total_updated,self.total_removed): value.set("0")
        threading.Thread(target=self.sync_all,daemon=True).start()
    def sync_all(self):
        started=time.time(); totals={"files":0,"added":0,"updated":0,"removed":0}
        try:
            self.set_status("Fetching all branches…","#2eaadc"); self.ui("ORION ALL SYNC — one fetch, local refs, exact mirrors"); results=sync_repository(PROJECT_ROOT,ALL_ROOT,REMOTE,self.ui)
            for stats in results.values(): totals["files"]+=stats.files; totals["added"]+=stats.added; totals["updated"]+=stats.updated; totals["removed"]+=stats.removed
            for key,value in totals.items(): self.root.after(0,getattr(self,f"total_{key}").set,str(value))
            self.ui(f"ALL SUCCESS — {len(results)} branches verified in {time.time()-started:.1f}s."); self.set_status(f"ALL SUCCESS — {len(results)} branches verified"); self.root.after(0,messagebox.showinfo,"ORION Restore",f"ALL SUCCESS\n\nBranches: {len(results)}\nAdded: {totals['added']}\nUpdated: {totals['updated']}\nRemoved: {totals['removed']}")
        except Exception as exc: self.ui(f"ERROR — ALL was not completed.\n{exc}"); self.set_status("Sync failed","#e05252"); self.root.after(0,messagebox.showerror,"ORION Restore",str(exc))
        finally: self.root.after(0,self.button.configure,{"state":"normal","text":"Sync ALL — all branches"}); self.running=False

def _launch_smoke_test()->int:
    marker=os.environ.get("ORION_RESTORE_LAUNCH_MARKER")
    if marker: Path(marker).write_text("launched",encoding="utf-8")
    return 0

if __name__=="__main__":
    if "--launch-smoke-test" in sys.argv: raise SystemExit(_launch_smoke_test())
    root=tk.Tk(); OrionAllRestore(root); root.mainloop()
