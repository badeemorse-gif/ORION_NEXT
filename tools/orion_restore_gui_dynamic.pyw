import importlib.util
import os
import re
import threading
import tkinter as tk
from tkinter import messagebox

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

# ALL never mixes branches into PROJECT_ROOT. Each remote branch gets its own
# dedicated detached Git worktree beside the main repository.
ALL_WORKTREE_ROOT = os.path.join(
    os.path.dirname(base.PROJECT_ROOT),
    "ORION_NEXT_ALL_BRANCHES",
)


def discover(self):
    code, lines = self._git(["ls-remote", "--heads", base.REMOTE])
    if code != 0:
        raise RuntimeError(
            "تعذر قراءة فروع GitHub الحالية.\n"
            + ("\n".join(lines) or "git ls-remote failed.")
        )

    branches = []
    for line in lines:
        parts = line.split("\t", 1)
        if len(parts) != 2:
            continue
        ref = parts[1].strip()
        if not ref.startswith("refs/heads/"):
            continue
        name = ref[len("refs/heads/"):]
        if name and name not in branches:
            branches.append(name)

    if not branches:
        raise RuntimeError("لم يتم العثور على أي فرع في GitHub.")

    return sorted(branches, key=lambda x: (x != "main", x.lower()))


def branch(self):
    value = self.branch_var.get().strip()
    return (
        value
        if value == ALL_BRANCH or value in getattr(self, "branches", FALLBACK)
        else base.DEFAULT_BRANCH
    )


def changed(self, _event=None):
    if not self.running:
        if self.branch == ALL_BRANCH:
            text = (
                "GitHub → Git → Local  |  ALL "
                f"({len(self.branches)} branches → separate worktrees)"
            )
        else:
            text = f"GitHub → Git → Local  |  {self.branch}"
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
            self.root.after(
                0,
                self._status,
                "تعذر تحديث الفروع — القائمة السابقة متاحة",
                self.warning,
            )

    threading.Thread(target=worker, daemon=True).start()


def restore(self):
    branches = discover(self)
    self.root.after(0, apply_branches, self, branches)

    if self.branch == ALL_BRANCH:
        restore_all(self, branches)
        return

    # Single-branch mode remains the original Exact Restore path.
    old_branches = getattr(base, "BRANCHES", ())
    old_sync = getattr(base, "SYNC_BRANCHES", ())
    base.BRANCHES = tuple(branches)
    base.SYNC_BRANCHES = tuple(branches)
    try:
        original_restore(self)
    finally:
        base.BRANCHES = old_branches
        base.SYNC_BRANCHES = old_sync


def _safe_branch_dir(branch_name):
    # Keep slash-separated Git branch names readable while avoiding accidental
    # traversal or Windows-invalid filename characters.
    safe = re.sub(r'[<>:"/\\|?*]+', "__", branch_name).strip(" .")
    return os.path.join(ALL_WORKTREE_ROOT, safe or "branch")


def _git_at(self, worktree, args):
    process = subprocess.Popen(
        ["git", "-C", worktree, *args],
        cwd=base.PROJECT_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    lines = [line.rstrip() for line in process.stdout if line.rstrip()]
    return process.wait(), lines


def _git_at_value(self, worktree, args):
    code, lines = _git_at(self, worktree, args)
    if code != 0:
        raise RuntimeError("\n".join(lines) or "Git command failed.")
    return lines[-1].strip() if lines else ""


def _registered_worktrees(self):
    code, lines = self._git(["worktree", "list", "--porcelain"])
    if code != 0:
        raise RuntimeError("تعذر قراءة Git worktrees.")
    paths = set()
    for line in lines:
        if line.startswith("worktree "):
            raw = line[len("worktree "):].strip()
            paths.add(os.path.normcase(os.path.abspath(raw)))
    return paths


def _preview_changes(self, worktree, target_ref):
    code, lines = _git_at(
        self,
        worktree,
        ["diff", "--name-status", "--find-renames", target_ref],
    )
    if code != 0:
        raise RuntimeError("تعذر حساب تغييرات الفرع الهدف.")

    added = sum(1 for line in lines if line.startswith("A"))
    removed = sum(1 for line in lines if line.startswith("D"))
    updated = len(lines) - added - removed

    code, clean_lines = _git_at(self, worktree, ["clean", "-fdxn"])
    if code != 0:
        raise RuntimeError("تعذر فحص الملفات الزائدة في worktree.")
    extras = [line for line in clean_lines if line.startswith("Would remove ")]
    return len(lines), added, updated, removed, len(extras)


def _sync_one_worktree(self, branch_name, index, total):
    target_ref = f"{base.REMOTE}/{branch_name}"
    worktree = _safe_branch_dir(branch_name)
    worktree_norm = os.path.normcase(os.path.abspath(worktree))
    registered = _registered_worktrees(self)
    exists = os.path.isdir(worktree)

    # Never delete or repurpose an arbitrary existing directory. Only Git
    # worktrees created/registered by this utility are eligible for ALL sync.
    if exists and worktree_norm not in registered:
        raise RuntimeError(
            f"مسار ALL موجود لكنه ليس Git worktree مُسجلاً:\n{worktree}\n"
            "لن يتم لمس هذا المسار منعًا لفقد أي ملفات محلية."
        )

    if not exists:
        os.makedirs(os.path.dirname(worktree), exist_ok=True)
        code, lines = self._git(
            ["worktree", "add", "--detach", worktree, target_ref]
        )
        if code != 0:
            raise RuntimeError(
                f"فشل إنشاء worktree للفرع {branch_name}.\n"
                + ("\n".join(lines) or "Git worktree add failed.")
            )
        before = (0, 0, 0, 0, 0)
        for line in lines:
            self._ui(f"[{index}/{total}] {branch_name}: {line}")
    else:
        before = _preview_changes(self, worktree, target_ref)
        code, lines = _git_at(self, worktree, ["reset", "--hard", target_ref])
        if code != 0:
            raise RuntimeError(
                f"فشل ضبط worktree للفرع {branch_name}.\n"
                + ("\n".join(lines) or "Git reset failed.")
            )
        for line in lines:
            self._ui(f"[{index}/{total}] {branch_name}: {line}")
        code, lines = _git_at(self, worktree, ["clean", "-fdx"])
        if code != 0:
            raise RuntimeError(
                f"فشل تنظيف worktree للفرع {branch_name}.\n"
                + ("\n".join(lines) or "Git clean failed.")
            )
        for line in lines:
            self._ui(f"[{index}/{total}] {branch_name}: {line}")

    # Submodules live inside each dedicated worktree, so their state cannot
    # bleed into another branch's worktree.
    code, lines = _git_at(self, worktree, ["submodule", "update", "--init", "--recursive"])
    if code != 0:
        raise RuntimeError(
            f"فشل تحديث submodules للفرع {branch_name}.\n"
            + ("\n".join(lines) or "Submodule update failed.")
        )
    code, lines = _git_at(
        self,
        worktree,
        ["submodule", "foreach", "--recursive", "git", "reset", "--hard"],
    )
    if code != 0:
        raise RuntimeError(f"فشل تنظيف تغييرات submodules للفرع {branch_name}.")
    code, lines = _git_at(
        self,
        worktree,
        ["submodule", "foreach", "--recursive", "git", "clean", "-fdx"],
    )
    if code != 0:
        raise RuntimeError(f"فشل تنظيف ملفات submodules للفرع {branch_name}.")

    final_commit = _git_at_value(self, worktree, ["rev-parse", "HEAD"])
    remote_commit = self._git_value(["rev-parse", "--verify", target_ref])
    if final_commit != remote_commit:
        raise RuntimeError(
            f"الـ commit النهائي للفرع {branch_name} لا يطابق GitHub.\n"
            f"Local: {final_commit}\nGitHub: {remote_commit}"
        )

    code, _ = _git_at(self, worktree, ["diff", "--quiet", target_ref, "HEAD"])
    if code != 0:
        raise RuntimeError(f"ملفات worktree للفرع {branch_name} لا تطابق GitHub.")

    code, status_lines = _git_at(self, worktree, ["status", "--porcelain", "--ignored"])
    if code != 0 or status_lines:
        detail = "\n".join(status_lines[:50])
        raise RuntimeError(
            f"بقيت حالة محلية في worktree للفرع {branch_name}; لم نعلن التطابق.\n{detail}"
        )

    self._ui(
        f"[{index}/{total}] {branch_name}: EXACT MATCH | "
        f"Local worktree = {worktree} | Commit = {final_commit}"
    )
    return {
        "branch": branch_name,
        "worktree": worktree,
        "commit": remote_commit,
        "files": before[0],
        "added": before[1],
        "updated": before[2],
        "removed": before[3],
        "extra": before[4],
    }


def restore_all(self, branches):
    self._ui("=" * 72)
    self._ui("ORION ALL-BRANCH EXACT SYNC STARTED")
    self._ui("=" * 72)
    self._ui(
        f"ALL = مزامنة {len(branches)} فرعًا من GitHub إلى worktrees مستقلة."
    )
    self._ui("لن يتم تبديل أو الكتابة فوق working tree الرئيسي.")
    self._ui(f"Worktrees root: {ALL_WORKTREE_ROOT}")

    if self._git_value(["rev-parse", "--is-inside-work-tree"]) != "true":
        raise RuntimeError("المجلد المحلي ليس مستودع Git صالحًا.")

    remote_url = self._git_value(["remote", "get-url", base.REMOTE])
    self._ui(f"Remote: {remote_url}")

    results = []
    for index, branch_name in enumerate(branches, 1):
        code, lines = self._git(["fetch", base.REMOTE, branch_name])
        if code != 0:
            raise RuntimeError(
                f"فشل جلب GitHub/{branch_name}.\n"
                + ("\n".join(lines) or "Git fetch failed.")
            )
        results.append(_sync_one_worktree(self, branch_name, index, len(branches)))

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
    self._ui(f"ALL SYNC COMPLETED — {len(results)}/{len(branches)} branches EXACT MATCH")
    for item in results:
        self._ui(
            f"{item['branch']} → {item['worktree']} → {item['commit'][:12]}"
        )
    self._ui("كل فرع محفوظ في worktree مستقل؛ لا يوجد خلط بين الفروع.")
    self._ui("الـworking tree الرئيسي لم يتم تبديله أثناء ALL.")
    self._ui("=" * 72)
    self.root.after(
        0,
        self._finish_all,
        True,
        f"تمت مزامنة جميع الفروع ({len(results)}) بنجاح دون خلط بينها.",
    )


def finish_all(self, success, message):
    self._write("=" * 72)
    self._write("ORION ALL-BRANCH SYNC COMPLETED SUCCESSFULLY")
    self._write("GitHub → Git → Local worktrees")
    self._write(message)
    self._write(f"Worktrees root: {ALL_WORKTREE_ROOT}")
    self._write("كل فرع موجود في مجلد مستقل؛ working tree الرئيسي لم يتغير.")
    self._write("FINAL REPOSITORY STATE: ALL BRANCH WORKTREES EXACT MATCH")
    self._write("=" * 72)
    self._status(f"{message} ✅", self.success)
    self.running = False
    self.button.configure(state="normal", text="⬇  استعادة مطابقة للمستودع")
    self.branch_combo.configure(state="readonly")


original_restore = base.OrionRestoreApp._restore
base.OrionRestoreApp.branch = property(branch)
base.OrionRestoreApp._discover_remote_branches = discover
base.OrionRestoreApp._branch_changed = changed
base.OrionRestoreApp._apply_branches = apply_branches
base.OrionRestoreApp.refresh_branches = refresh
base.OrionRestoreApp._restore = restore
base.OrionRestoreApp._restore_all = restore_all
base.OrionRestoreApp._finish_all = finish_all


def main():
    if not os.path.isdir(base.PROJECT_ROOT):
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "ORION Restore",
            f"مشروع ORION غير موجود:\n\n{base.PROJECT_ROOT}",
        )
        root.destroy()
        return

    root = tk.Tk()
    app = base.OrionRestoreApp(root)
    app.source_label.configure(text=f"GitHub → Git → Local  |  {app.branch}")
    root.after(250, app.refresh_branches)
    root.mainloop()


if __name__ == "__main__":
    main()
