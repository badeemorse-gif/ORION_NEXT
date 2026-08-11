"""ORION Restore combined UI: MAIN official mirror + frozen ALL engine.

ALL is loaded from the existing orion_restore_gui.pyw without changing its
implementation. MAIN is an isolated second path that writes only PROJECT_ROOT.
"""

from __future__ import annotations

import json
import os
import runpy
import sys
import threading
import time
import uuid
from pathlib import Path

import tkinter as tk
from tkinter import messagebox, scrolledtext

CORE_PATH = Path(__file__).with_name("orion_restore_gui.pyw")
CORE = runpy.run_path(str(CORE_PATH))

PROJECT_ROOT = CORE["PROJECT_ROOT"]
REMOTE = CORE["REMOTE"]
ALL_ROOT = CORE["ALL_ROOT"]
GIT_TIMEOUT = CORE["GIT_TIMEOUT"]
Manifest = CORE["Manifest"]
RestoreError = CORE["RestoreError"]
BranchStats = CORE["BranchStats"]
run_git = CORE["run_git"]
safe_target = CORE["safe_target"]
remove_any = CORE["remove_any"]
archive_manifest = CORE["archive_manifest"]
assert_no_gitlinks = CORE["assert_no_gitlinks"]
sync_repository = CORE["sync_repository"]

MAIN_STATE_PATH = str(Path(PROJECT_ROOT).parent / "ORION_NEXT_MAIN_STATE.json")


def main_manifest(root: str) -> Manifest:
    """Use the proven ALL manifest logic while excluding the checkout's .git directory."""
    base = CORE["local_manifest"](root)
    return {rel: sig for rel, sig in base.items() if rel != ".git" and not rel.startswith(".git/")}


def tracked_files(project_root: str) -> set[str]:
    code, data, error = run_git(["ls-files", "-z"], project_root, binary=True)
    if code:
        raise RestoreError(f"git ls-files failed: {error.decode('utf-8', 'replace')}")
    return {os.fsdecode(item) for item in data.split(b"\0") if item}


def load_main_state() -> set[str]:
    try:
        with open(MAIN_STATE_PATH, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        files = data.get("files", [])
        if not isinstance(files, list) or not all(isinstance(item, str) for item in files):
            raise ValueError("invalid MAIN state")
        return set(files)
    except FileNotFoundError:
        return set()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise RestoreError(f"MAIN state file is invalid: {MAIN_STATE_PATH}: {exc}") from exc


def save_main_state(paths: set[str]) -> None:
    state_path = Path(MAIN_STATE_PATH)
    temporary = state_path.with_name(f"{state_path.name}.orion_tmp.{uuid.uuid4().hex}")
    payload = {"version": 1, "files": sorted(paths)}
    state_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(temporary, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, state_path)
    except OSError as exc:
        if os.path.lexists(temporary):
            remove_any(str(temporary))
        raise RestoreError(f"Unable to save MAIN state: {state_path}: {exc}") from exc


def _remove_empty_parent_dirs(root: str, rel: str) -> None:
    root_abs = os.path.abspath(root)
    parent = os.path.abspath(os.path.dirname(safe_target(root_abs, rel)))
    while parent != root_abs and os.path.isdir(parent):
        try:
            os.rmdir(parent)
        except OSError:
            break
        parent = os.path.dirname(parent)


def _main_parent_directory(path: str, root: str) -> None:
    root_abs = os.path.abspath(root)
    parent = os.path.abspath(os.path.dirname(path))
    to_create = []
    while parent != root_abs:
        if os.path.commonpath([root_abs, parent]) != root_abs:
            raise RestoreError(f"Unsafe MAIN destination parent: {path}")
        if os.path.lexists(parent) and (os.path.islink(parent) or not os.path.isdir(parent)):
            raise RestoreError(
                f"MAIN refused an untracked file/directory collision at {parent}; "
                "untracked local content was not deleted."
            )
        to_create.append(parent)
        parent = os.path.dirname(parent)
    for directory in reversed(to_create):
        os.makedirs(directory, exist_ok=True)


def _write_main_file(full: str, data: bytes) -> None:
    temporary = f"{full}.orion_tmp.{uuid.uuid4().hex}"
    with open(temporary, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    try:
        os.replace(temporary, full)
    except OSError as exc:
        if os.path.lexists(temporary):
            remove_any(temporary)
        raise RestoreError(f"Unable to atomically replace {full}: {exc}") from exc


def materialize_main(archive: bytes, root: str, target: Manifest, tracked: set[str], previous: set[str]) -> BranchStats:
    """Materialize origin/main without changing Git branch/index state."""
    root_abs = os.path.abspath(root)
    if root_abs != os.path.abspath(PROJECT_ROOT):
        raise RestoreError("MAIN destination must be PROJECT_ROOT.")
    if not os.path.isdir(os.path.join(root_abs, ".git")):
        raise RestoreError(f"Project is not a Git checkout: {root_abs}")

    old = main_manifest(root_abs)
    known_official = tracked | previous
    target_paths = set(target)
    stale = sorted((rel for rel in known_official if rel not in target_paths), key=lambda item: item.count("/"), reverse=True)
    removed = 0
    for rel in stale:
        full = safe_target(root_abs, rel)
        if not os.path.lexists(full):
            continue
        if os.path.isdir(full) and not os.path.islink(full):
            raise RestoreError(f"MAIN found unexpected directory collision at official path: {rel}")
        removed += remove_any(full)
        _remove_empty_parent_dirs(root_abs, rel)

    added = updated = 0
    with __import__("tarfile").open(fileobj=__import__("io").BytesIO(archive), mode="r:") as tar:
        for member in tar.getmembers():
            rel = CORE["archive_relpath"](member.name)
            if not rel:
                continue
            full = safe_target(root_abs, rel)
            target_signature = target[rel]

            if member.isdir():
                if os.path.lexists(full) and (os.path.islink(full) or not os.path.isdir(full)):
                    if rel in known_official:
                        remove_any(full)
                    else:
                        raise RestoreError(
                            f"MAIN refused an untracked file/directory collision at {rel}; "
                            "untracked local content was not deleted."
                        )
                os.makedirs(full, exist_ok=True)
                continue

            if member.issym():
                existing = main_manifest(root_abs).get(rel)
                if existing == target_signature:
                    continue
                if os.path.lexists(full):
                    if rel not in known_official:
                        raise RestoreError(f"MAIN refused to overwrite differing untracked path: {rel}")
                    remove_any(full)
                _main_parent_directory(full, root_abs)
                try:
                    os.symlink(member.linkname, full)
                except OSError as exc:
                    raise RestoreError(f"Unable to create required symlink {full}: {exc}") from exc
                if rel in old:
                    updated += 1
                else:
                    added += 1
                continue

            if not member.isfile():
                continue
            source = tar.extractfile(member)
            if source is None:
                raise RestoreError(f"Archive entry could not be read: {rel}")
            data = source.read()
            new_signature = ("file", len(data), __import__("hashlib").sha256(data).hexdigest())
            existing = old.get(rel)
            if existing == new_signature:
                continue
            if os.path.lexists(full):
                if os.path.isdir(full) and not os.path.islink(full):
                    try:
                        os.rmdir(full)
                    except OSError as exc:
                        raise RestoreError(
                            f"MAIN refused to delete untracked content under directory {rel}: {exc}"
                        ) from exc
                elif rel not in known_official:
                    raise RestoreError(f"MAIN refused to overwrite differing untracked path: {rel}")
                else:
                    remove_any(full)
            _main_parent_directory(full, root_abs)
            _write_main_file(full, data)
            if rel in old:
                updated += 1
            else:
                added += 1

    verify_main_materialized(root_abs, target, known_official)
    return BranchStats(
        files=sum(1 for signature in target.values() if signature[0] in ("file", "link")),
        added=added,
        updated=updated,
        removed=removed,
    )


def verify_main_materialized(root: str, target: Manifest, known_official: set[str]) -> None:
    actual = main_manifest(root)
    missing = sorted(set(target) - set(actual))
    mismatched = sorted(rel for rel in set(actual) & set(target) if actual[rel] != target[rel])
    stale_official = sorted(rel for rel in known_official if rel not in target and rel in actual)
    details = []
    if missing:
        details.append("missing: " + ", ".join(missing[:5]))
    if mismatched:
        details.append("different: " + ", ".join(mismatched[:5]))
    if stale_official:
        details.append("stale official: " + ", ".join(stale_official[:5]))
    if details:
        raise RestoreError(f"MAIN verification failed: {'; '.join(details)}")
    for rel in actual:
        if ".orion_tmp" in rel and rel not in target:
            raise RestoreError(f"MAIN orphan temporary file remains: {rel}")


def sync_main(project_root: str, remote: str = REMOTE, report=None) -> BranchStats:
    project_root = os.path.abspath(project_root)
    if project_root != os.path.abspath(PROJECT_ROOT):
        raise RestoreError("MAIN must target PROJECT_ROOT only.")
    if not os.path.isdir(os.path.join(project_root, ".git")):
        raise RestoreError(f"Project is not a Git checkout: {project_root}")

    code, lines = run_git(["fetch", "--prune", remote, "main"], project_root)
    if code:
        raise RestoreError("\n".join(lines) or "git fetch origin main failed.")
    ref = f"{remote}/main"
    assert_no_gitlinks(project_root, ref)
    archive, target = archive_manifest(project_root, ref)
    tracked = tracked_files(project_root)
    previous = load_main_state()
    stats = materialize_main(archive, project_root, target, tracked, previous)
    save_main_state({rel for rel, signature in target.items() if signature[0] in ("file", "link")})
    if report:
        report(f"Files: {stats.files} | Added: {stats.added} | Updated: {stats.updated} | Removed: {stats.removed} | SUCCESS")
    return stats


class OrionRestore:
    def __init__(self, root):
        self.root=root; self.root.title("ORION Restore"); self.root.geometry("900x640"); self.root.minsize(780,550); self.root.configure(bg="#101820"); self.running=False
        self.status=tk.StringVar(value="Ready"); self.total_files=tk.StringVar(value="0"); self.total_added=tk.StringVar(value="0"); self.total_updated=tk.StringVar(value="0"); self.total_removed=tk.StringVar(value="0"); self.total_branches=tk.StringVar(value="0")
        self._build(); self.refresh_branches()

    def _build(self):
        tk.Label(self.root,text="ORION RESTORE",font=("Segoe UI",22,"bold"),bg="#101820",fg="#f2f5f7").pack(pady=(18,2)); tk.Label(self.root,text="GitHub → Local  |  MAIN + ALL",font=("Segoe UI",10),bg="#101820",fg="#9aa8b2").pack()
        panel=tk.Frame(self.root,bg="#17232d"); panel.pack(fill="x",padx=24,pady=10)
        for label,value in (("Repository","ORION_NEXT"),("Project",PROJECT_ROOT),("ALL Destination",ALL_ROOT)):
            row=tk.Frame(panel,bg="#17232d"); row.pack(fill="x",padx=12,pady=4); tk.Label(row,text=label+":",width=16,anchor="w",bg="#17232d",fg="#9aa8b2",font=("Segoe UI",8,"bold")).pack(side="left"); tk.Label(row,text=value,anchor="w",bg="#17232d",fg="#f2f5f7",font=("Segoe UI",8)).pack(side="left",fill="x",expand=True)
        sr=tk.Frame(self.root,bg="#101820"); sr.pack(fill="x",padx=24,pady=(3,4)); tk.Label(sr,text="STATUS:",bg="#101820",fg="#9aa8b2",font=("Segoe UI",9,"bold")).pack(side="left"); self.status_label=tk.Label(sr,textvariable=self.status,bg="#101820",fg="#3fc36b",font=("Segoe UI",9,"bold")); self.status_label.pack(side="left",padx=8)
        cards=tk.Frame(self.root,bg="#101820"); cards.pack(fill="x",padx=24,pady=3)
        for index,(title,variable,color) in enumerate((("BRANCHES",self.total_branches,"#2eaadc"),("FILES",self.total_files,"#2eaadc"),("ADDED",self.total_added,"#3fc36b"),("UPDATED",self.total_updated,"#2eaadc"),("REMOVED",self.total_removed,"#e05252"))):
            cards.grid_columnconfigure(index,weight=1); card=tk.Frame(cards,bg="#182538"); card.grid(row=0,column=index,sticky="nsew",padx=3); tk.Label(card,text=title,bg="#182538",fg="#9aa8b2",font=("Segoe UI",8,"bold")).pack(anchor="w",padx=8,pady=(6,0)); tk.Label(card,textvariable=variable,bg="#182538",fg=color,font=("Segoe UI",16,"bold")).pack(anchor="w",padx=8,pady=(0,6))
        buttons=tk.Frame(self.root,bg="#101820"); buttons.pack(pady=(9,6)); self.main_button=tk.Button(buttons,text="Sync MAIN",command=self.start_main,bg="#3fc36b",fg="white",activebackground="#3fc36b",relief="flat",font=("Segoe UI",11,"bold"),padx=25,pady=9); self.main_button.pack(side="left",padx=5); self.all_button=tk.Button(buttons,text="Sync ALL",command=self.start_all,bg="#2eaadc",fg="white",activebackground="#2eaadc",relief="flat",font=("Segoe UI",11,"bold"),padx=25,pady=9); self.all_button.pack(side="left",padx=5)
        tk.Label(self.root,text="MAIN writes only PROJECT_ROOT. ALL writes only isolated branch mirrors under ALL_ROOT.",bg="#101820",fg="#e0a52e",font=("Segoe UI",8)).pack(); tk.Label(self.root,text="Sync log",bg="#101820",fg="#9aa8b2",font=("Segoe UI",9,"bold")).pack(anchor="w",padx=24,pady=(8,3)); self.output=scrolledtext.ScrolledText(self.root,height=14,bg="#0b1116",fg="#d9e1e6",insertbackground="white",font=("Consolas",9),relief="flat",bd=0,wrap="word"); self.output.pack(fill="both",expand=True,padx=24,pady=(0,14))

    def ui(self,text): self.root.after(0,lambda:(self.output.insert("end",text+"\n"),self.output.see("end")))
    def set_status(self,text,color="#3fc36b"): self.root.after(0,self.status.set,text); self.root.after(0,self.status_label.configure,{"fg":color})
    def refresh_branches(self):
        def worker():
            try: branches=CORE["discover_remote_branches"](PROJECT_ROOT,REMOTE); self.root.after(0,self.total_branches.set,str(len(branches))); self.ui(f"Discovered {len(branches)} remote branches."); self.set_status("Ready to sync")
            except Exception as exc: self.ui(str(exc)); self.set_status("Branch discovery failed","#e05252")
        threading.Thread(target=worker,daemon=True).start()
    def _begin(self, mode):
        if self.running:return False
        self.running=True; self.main_button.configure(state="disabled"); self.all_button.configure(state="disabled"); self.total_files.set("0"); self.total_added.set("0"); self.total_updated.set("0"); self.total_removed.set("0"); self.ui(f"ORION {mode} SYNC"); return True
    def start_main(self):
        if self._begin("MAIN"): threading.Thread(target=self.sync_main_worker,daemon=True).start()
    def start_all(self):
        if self._begin("ALL"): threading.Thread(target=self.sync_all_worker,daemon=True).start()
    def _finish(self): self.root.after(0,self.main_button.configure,{"state":"normal"}); self.root.after(0,self.all_button.configure,{"state":"normal"}); self.running=False
    def sync_main_worker(self):
        started=time.time()
        try:
            self.set_status("Fetching origin/main…","#2eaadc"); self.ui("MAIN — origin/main → PROJECT_ROOT"); stats=sync_main(PROJECT_ROOT,REMOTE,self.ui); self.root.after(0,self.total_branches.set,"1"); self.root.after(0,self.total_files.set,str(stats.files)); self.root.after(0,self.total_added.set,str(stats.added)); self.root.after(0,self.total_updated.set,str(stats.updated)); self.root.after(0,self.total_removed.set,str(stats.removed)); self.ui(f"MAIN SUCCESS — {stats.files} files verified in {time.time()-started:.1f}s."); self.set_status("MAIN SUCCESS — PROJECT_ROOT verified"); self.root.after(0,messagebox.showinfo,"ORION Restore",f"MAIN SUCCESS\n\nFiles: {stats.files}\nAdded: {stats.added}\nUpdated: {stats.updated}\nRemoved: {stats.removed}")
        except Exception as exc: self.ui(f"ERROR — MAIN was not completed.\n{exc}"); self.set_status("MAIN sync failed","#e05252"); self.root.after(0,messagebox.showerror,"ORION Restore",str(exc))
        finally: self._finish()
    def sync_all_worker(self):
        started=time.time(); totals={"files":0,"added":0,"updated":0,"removed":0}
        try:
            self.set_status("Fetching all branches…","#2eaadc"); results=sync_repository(PROJECT_ROOT,ALL_ROOT,REMOTE,self.ui)
            for stats in results.values(): totals["files"]+=stats.files; totals["added"]+=stats.added; totals["updated"]+=stats.updated; totals["removed"]+=stats.removed
            self.root.after(0,self.total_branches.set,str(len(results))); self.root.after(0,self.total_files.set,str(totals["files"])); self.root.after(0,self.total_added.set,str(totals["added"])); self.root.after(0,self.total_updated.set,str(totals["updated"])); self.root.after(0,self.total_removed.set,str(totals["removed"])); self.ui(f"ALL SUCCESS — {len(results)} branches verified in {time.time()-started:.1f}s."); self.set_status(f"ALL SUCCESS — {len(results)} branches verified"); self.root.after(0,messagebox.showinfo,"ORION Restore",f"ALL SUCCESS\n\nBranches: {len(results)}\nAdded: {totals['added']}\nUpdated: {totals['updated']}\nRemoved: {totals['removed']}")
        except Exception as exc: self.ui(f"ERROR — ALL was not completed.\n{exc}"); self.set_status("ALL sync failed","#e05252"); self.root.after(0,messagebox.showerror,"ORION Restore",str(exc))
        finally: self._finish()


def _launch_smoke_test()->int:
    marker=os.environ.get("ORION_RESTORE_LAUNCH_MARKER")
    if marker: Path(marker).write_text("launched",encoding="utf-8")
    return 0

if __name__=="__main__":
    if "--launch-smoke-test" in sys.argv: raise SystemExit(_launch_smoke_test())
    root=tk.Tk(); OrionRestore(root); root.mainloop()
