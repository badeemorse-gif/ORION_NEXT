import hashlib
import importlib.util
import os
import re
import subprocess
import threading
import tkinter as tk

BASE_NAME = "orion_restore_gui.pyw"
TARGET = os.path.join(os.path.dirname(__file__), BASE_NAME)
spec = importlib.util.spec_from_file_location("orion_restore_base", TARGET)
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)

ALL_BRANCH = "ALL"
FALLBACK = (
    "main",
    "orion-canonical-pipeline-boundary",
    "phase2/core-intelligence-hardening",
)
ALL_WORKTREE_ROOT = os.path.join(os.path.dirname(base.PROJECT_ROOT), "ORION_NEXT_ALL_BRANCHES")
GIT_TIMEOUT = 180


def _run_git(cwd, args, timeout=GIT_TIMEOUT):
    process = subprocess.Popen(
        ["git", *args], cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace",
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    try:
        stdout, _ = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            process.kill()
            process.communicate(timeout=5)
        except Exception:
            pass
        if os.name == "nt":
            try:
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    timeout=10, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            except Exception:
                pass
        return 124, [f"Git command timeout after {timeout}s: git {' '.join(args)}"]
    lines = [line.rstrip() for line in (stdout or "").splitlines() if line.rstrip()]
    return process.returncode, lines


def _git(self, args):
    return _run_git(base.PROJECT_ROOT, args)


def _git_value(self, args):
    code, lines = _git(self, args)
    if code != 0:
        raise RuntimeError("\n".join(lines) or "Git command failed.")
    return lines[-1].strip() if lines else ""


def _git_at(self, worktree, args):
    return _run_git(worktree, args)


def _git_at_value(self, worktree, args):
    code, lines = _git_at(self, worktree, args)
    if code != 0:
        raise RuntimeError("\n".join(lines) or "Git command failed.")
    return lines[-1].strip() if lines else ""


def discover(self):
    code, lines = _git(self, ["ls-remote", "--heads", base.REMOTE])
    if code != 0:
        raise RuntimeError("تعذر قراءة فروع GitHub الحالية.\n" + ("\n".join(lines) or "git ls-remote failed."))
    branches = []
    for line in lines:
        parts = line.split("\t", 1)
        if len(parts) != 2:
            continue
        ref = parts[1].strip()
        if ref.startswith("refs/heads/"):
            name = ref[len("refs/heads/"):]
            if name and name not in branches:
                branches.append(name)
    if not branches:
        raise RuntimeError("لم يتم العثور على أي فرع في GitHub.")
    return sorted(branches, key=lambda x: (x != "main", x.lower()))


def branch(self):
    value = self.branch_var.get().strip()
    return value if value == ALL_BRANCH or value in getattr(self, "branches", FALLBACK) else base.DEFAULT_BRANCH


def changed(self, _event=None):
    if not self.running:
        text = (
            "GitHub → Git → Local  |  ALL "
            f"({len(self.branches)} branches → separate worktrees)"
            if self.branch == ALL_BRANCH else f"GitHub → Git → Local  |  {self.branch}"
        )
        self.source_label.configure(text=text)
        self._write(f"Target branch changed to: {self.branch}")


def apply_branches(self, branches):
    current = self.branch_var.get().strip()
    self.branches = list(branches)
    values = (ALL_BRANCH, *self.branches)
    self.branch_combo.configure(values=values)
    if current in values:
        self.branch_var.set(current)
    elif base.DEFAULT_BRANCH in self.branches:
        self.branch_var.set(base.DEFAULT_BRANCH)
    else:
        self.branch_var.set(self.branches[0])
    changed(self)
    self._write(f"تم تحديث قائمة الفروع من GitHub: {len(self.branches)} فرعًا.")


def refresh(self):
    if self.running:
        return
    def worker():
        try:
            branches = discover(self)
            self.root.after(0, apply_branches, self, branches)
            self.root.after(0, self._status, "جاهز للاستعادة", self.success)
        except Exception as exc:
            self._ui(f"تعذر تحديث قائمة الفروع: {exc}")
            self.root.after(0, self._status, "تعذر تحديث الفروع — القائمة السابقة متاحة", self.warning)
    threading.Thread(target=worker, daemon=True).start()


def _safe_branch_dir(branch_name):
    safe = re.sub(r'[<>:"/\\|?*]+', "__", branch_name).strip(" .") or "branch"
    if safe != branch_name:
        safe += "__" + hashlib.sha1(branch_name.encode("utf-8")).hexdigest()[:8]
    return os.path.join(ALL_WORKTREE_ROOT, safe)


def _registered_worktrees(self):
    code, lines = _git(self, ["worktree", "list", "--porcelain"])
    if code != 0:
        raise RuntimeError("تعذر قراءة Git worktrees.\n" + ("\n".join(lines) or ""))
    paths = set()
    for line in lines:
        if line.startswith("worktree "):
            paths.add(os.path.normcase(os.path.abspath(line[9:].strip())))
    return paths


def _preview_changes(self, worktree, target_ref):
    code, lines = _git_at(self, worktree, ["diff", "--name-status", "--find-renames", "HEAD", target_ref])
    if code != 0:
        raise RuntimeError("تعذر حساب تغييرات الفرع الهدف.\n" + ("\n".join(lines) or ""))
    added = sum(1 for line in lines if line.startswith("A"))
    removed = sum(1 for line in lines if line.startswith("D"))
    updated = len(lines) - added - removed
    code, clean_lines = _git_at(self, worktree, ["clean", "-fdxn"])
    if code != 0:
        raise RuntimeError("تعذر فحص الملفات الزائدة في worktree.")
    extras = [line for line in clean_lines if line.startswith("Would remove ")]
    return len(lines), added, updated, removed, len(extras)


def _sync_one_worktree(self, branch_name, index, total, registered):
    target_ref = f"{base.REMOTE}/{branch_name}"
    worktree = _safe_branch_dir(branch_name)
    worktree_norm = os.path.normcase(os.path.abspath(worktree))
    exists = os.path.isdir(worktree)

    self._ui(f"[{index}/{total}] {branch_name}: بدء المزامنة → {worktree}")
    if exists and worktree_norm not in registered:
        raise RuntimeError(f"مسار ALL موجود لكنه ليس Git worktree مُسجلاً:\n{worktree}\nلن يتم لمس هذا المسار منعًا لفقد أي ملفات محلية.")

    if not exists:
        os.makedirs(os.path.dirname(worktree), exist_ok=True)
        code, lines = _git(self, ["worktree", "add", "--detach", worktree, target_ref])
        if code != 0:
            raise RuntimeError(f"فشل إنشاء worktree للفرع {branch_name}.\n" + ("\n".join(lines) or ""))
        before = (0, 0, 0, 0, 0)
        registered.add(worktree_norm)
    else:
        before = _preview_changes(self, worktree, target_ref)
        code, lines = _git_at(self, worktree, ["reset", "--hard", target_ref])
        if code != 0:
            raise RuntimeError(f"فشل ضبط worktree للفرع {branch_name}.\n" + ("\n".join(lines) or ""))
        code, lines = _git_at(self, worktree, ["clean", "-fdx"])
        if code != 0:
            raise RuntimeError(f"فشل تنظيف worktree للفرع {branch_name}.\n" + ("\n".join(lines) or ""))

    code, lines = _git_at(self, worktree, ["submodule", "update", "--init", "--recursive"])
    if code != 0:
        raise RuntimeError(f"فشل تحديث submodules للفرع {branch_name}.\n" + ("\n".join(lines) or ""))
    for args, label in [
        (["submodule", "foreach", "--recursive", "git", "reset", "--hard"], "تنظيف تغييرات submodules"),
        (["submodule", "foreach", "--recursive", "git", "clean", "-fdx"], "تنظيف ملفات submodules"),
    ]:
        code, lines = _git_at(self, worktree, args)
        if code != 0:
            raise RuntimeError(f"فشل {label} للفرع {branch_name}.")

    final_commit = _git_at_value(self, worktree, ["rev-parse", "HEAD"])
    remote_commit = _git_value(self, ["rev-parse", "--verify", target_ref])
    if final_commit != remote_commit:
        raise RuntimeError(f"الـ commit النهائي للفرع {branch_name} لا يطابق GitHub.\nLocal: {final_commit}\nGitHub: {remote_commit}")
    code, _ = _git_at(self, worktree, ["diff", "--quiet", target_ref, "HEAD"])
    if code != 0:
        raise RuntimeError(f"ملفات worktree للفرع {branch_name} لا تطابق GitHub.")
    code, status_lines = _git_at(self, worktree, ["status", "--porcelain", "--ignored"])
    if code != 0 or status_lines:
        raise RuntimeError(f"بقيت حالة محلية في worktree للفرع {branch_name}; لم نعلن التطابق.\n" + "\n".join(status_lines[:50]))

    self._ui(f"[{index}/{total}] {branch_name}: EXACT MATCH ✓ | Commit {final_commit[:12]}")
    return {"branch": branch_name, "worktree": worktree, "commit": remote_commit, "files": before[0], "added": before[1], "updated": before[2], "removed": before[3], "extra": before[4]}


def restore_all(self, branches):
    self._ui("=" * 72)
    self._ui("ORION ALL-BRANCH EXACT SYNC STARTED")
    self._ui("ALL = مزامنة جميع الفروع في Worktrees مستقلة دون لمس PROJECT_ROOT")
    self._ui(f"الفروع المكتشفة: {len(branches)}")
    self._ui(f"Worktrees root: {ALL_WORKTREE_ROOT}")
    self._ui("[1/3] فحص المستودع المحلي...")
    if _git_value(self, ["rev-parse", "--is-inside-work-tree"]) != "true":
        raise RuntimeError("المجلد المحلي ليس مستودع Git صالحًا.")
    self._ui("[2/3] جلب جميع فروع GitHub دفعة واحدة...")
    code, lines = _git(self, ["fetch", "--prune", base.REMOTE])
    if code != 0:
        raise RuntimeError("فشل جلب الفروع من GitHub.\n" + ("\n".join(lines) or "Git fetch failed."))
    for line in lines:
        self._ui(line)
    self._ui("[3/3] مزامنة كل فرع في Worktree مستقل...")
    registered = _registered_worktrees(self)
    results = []
    for index, branch_name in enumerate(branches, 1):
        results.append(_sync_one_worktree(self, branch_name, index, len(branches), registered))

    commits = {item["branch"]: item["commit"] for item in results}
    self._save_all_sync_state(commits)
    total_files = sum(item["files"] for item in results)
    total_added = sum(item["added"] for item in results)
    total_updated = sum(item["updated"] for item in results)
    total_removed = sum(item["removed"] + item["extra"] for item in results)
    self.root.after(0, self.files_var.set, str(total_files + total_removed))
    self.root.after(0, self.added_var.set, str(total_added))
    self.root.after(0, self.updated_var.set, str(total_updated))
    self.root.after(0, self.removed_var.set, str(total_removed))
    self._ui("=" * 72)
    self._ui(f"ALL SYNC COMPLETED — {len(results)}/{len(branches)} branches EXACT MATCH ✓")
    self._ui("كل فرع محفوظ في Worktree مستقل؛ لا يوجد خلط بين الفروع.")
    self._ui("PROJECT_ROOT لم يتم تبديله أو الكتابة فوقه أثناء ALL.")
    self._ui("=" * 72)
    self.root.after(0, self._finish_all, True, f"تمت مزامنة جميع الفروع ({len(results)}) بنجاح دون خلط بينها.")


def finish_all(self, success, message):
    self._write("=" * 72)
    self._write("ORION ALL-BRANCH SYNC COMPLETED SUCCESSFULLY")
    self._write("GitHub → Git → Local worktrees")
    self._write(message)
    self._write(f"Worktrees root: {ALL_WORKTREE_ROOT}")
    self._write("FINAL STATE: ALL BRANCH WORKTREES EXACT MATCH")
    self._write("=" * 72)
    self._status(f"{message} ✅", self.success)
    self.running = False
    self.button.configure(state="normal", text="⬇  استعادة مطابقة للمستودع")
    self.branch_combo.configure(state="readonly")


def restore(self):
    branches = discover(self)
    self.root.after(0, apply_branches, self, branches)
    if self.branch == ALL_BRANCH:
        restore_all(self, branches)
        return
    old_branches = getattr(base, "BRANCHES", ())
    old_sync = getattr(base, "SYNC_BRANCHES", ())
    base.BRANCHES = tuple(branches)
    base.SYNC_BRANCHES = tuple(branches)
    try:
        original_restore(self)
    finally:
        base.BRANCHES = old_branches
        base.SYNC_BRANCHES = old_sync


original_restore = base.OrionRestoreApp._restore
base.OrionRestoreApp._git = _git
base.OrionRestoreApp._git_value = _git_value
base.OrionRestoreApp.branch = property(branch)
base.OrionRestoreApp._discover_remote_branches = discover
base.OrionRestoreApp._branch_changed = changed
base.OrionRestoreApp._apply_branches = apply_branches
base.OrionRestoreApp.refresh_branches = refresh
base.OrionRestoreApp._restore = restore
base.OrionRestoreApp._restore_all = restore_all
base.OrionRestoreApp._finish_all = finish_all

if __name__ == "__main__":
    root = tk.Tk()
    app = base.OrionRestoreApp(root)
    app.source_label.configure(text=("GitHub → Git → Local  |  ALL" if app.branch == ALL_BRANCH else f"GitHub → Git → Local  |  {app.branch}"))
    root.mainloop()
