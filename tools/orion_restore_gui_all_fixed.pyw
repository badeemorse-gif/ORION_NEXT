"""ORION Restore ALL-mode hardening layer.

Keeps individual-branch restore untouched and hardens only ALL mode.
Each GitHub branch is materialized into its own isolated worktree.
"""
import importlib.util
import os
import tkinter as tk

BASE_NAME = "orion_restore_gui_dynamic.pyw"
TARGET = os.path.join(os.path.dirname(__file__), BASE_NAME)
spec = importlib.util.spec_from_file_location("orion_restore_dynamic", TARGET)
if spec is None or spec.loader is None:
    raise RuntimeError("تعذر تحميل ORION Restore dynamic engine.")
dynamic = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dynamic)

base = dynamic.base
ALL_BRANCH = dynamic.ALL_BRANCH
ALL_WORKTREE_ROOT = dynamic.ALL_WORKTREE_ROOT


def _git(self, args):
    return dynamic._git(self, args)


def _git_value(self, args):
    return dynamic._git_value(self, args)


def _git_at(self, worktree, args):
    return dynamic._git_at(self, worktree, args)


def _git_at_value(self, worktree, args):
    return dynamic._git_at_value(self, worktree, args)


def _registered_worktrees(self):
    return dynamic._registered_worktrees(self)


def _safe_branch_dir(branch_name):
    return dynamic._safe_branch_dir(branch_name)


def _target_entries(self, worktree, target_ref):
    """Return target tree entries as (mode, object_id, path)."""
    code, lines = _git_at(self, worktree, ["ls-tree", "-r", target_ref])
    if code != 0:
        raise RuntimeError(
            "تعذر قراءة قائمة ملفات commit الهدف.\n" + ("\n".join(lines) or "")
        )
    entries = []
    for line in lines:
        parts = line.split("\t", 1)
        if len(parts) != 2:
            continue
        meta, rel = parts
        meta_parts = meta.split(" ", 2)
        if len(meta_parts) != 3:
            continue
        mode, _kind, object_id = meta_parts
        rel = rel.strip()
        if rel:
            entries.append((mode, object_id, rel))
    return entries


def _disable_sparse_checkout(self, worktree):
    """Remove sparse-checkout restrictions from this ALL worktree only."""
    code, lines = _git_at(self, worktree, ["sparse-checkout", "disable"])
    if code != 0:
        text = "\n".join(lines)
        # Older/non-sparse Git worktrees can report that sparse checkout is
        # already disabled. That state is safe and should not block ALL.
        lowered = text.lower()
        if "not a sparse checkout" not in lowered and "sparse-checkout is not enabled" not in lowered:
            raise RuntimeError(
                "تعذر تعطيل sparse-checkout داخل Worktree الخاص بالفرع.\n" + text
            )


def _materialize_full_tree(self, worktree, target_ref):
    """Materialize the complete target tree, even if a worktree was sparse."""
    # Remove local untracked/ignored blockers before checkout. This is safe
    # because ALL worktrees are created and owned by this utility.
    code, lines = _git_at(self, worktree, ["clean", "-fdx"])
    if code != 0:
        raise RuntimeError(
            "فشل تنظيف Worktree قبل التحميل الكامل.\n" + ("\n".join(lines) or "")
        )

    _disable_sparse_checkout(self, worktree)

    code, lines = _git_at(self, worktree, ["reset", "--hard", target_ref])
    if code != 0:
        raise RuntimeError(
            "فشل تحميل كامل ملفات الفرع داخل Worktree.\n" + ("\n".join(lines) or "")
        )

    # A second checkout forces the working tree to materialize every path
    # represented by the target tree after sparse-checkout has been disabled.
    code, lines = _git_at(
        self, worktree, ["checkout", "--force", target_ref, "--", "."]
    )
    if code != 0:
        raise RuntimeError(
            "فشل استكمال تحميل ملفات الفرع داخل Worktree.\n" + ("\n".join(lines) or "")
        )


def _verify_full_materialization(self, worktree, target_ref):
    """Verify physical materialization, not only commit equality."""
    entries = _target_entries(self, worktree, target_ref)
    missing = []

    for mode, _object_id, rel in entries:
        path = os.path.join(worktree, rel.replace("/", os.sep))
        if mode == "160000":
            # Git submodules are gitlinks in the superproject and are expected
            # to materialize as directories after `submodule update`.
            present = os.path.isdir(path)
        elif mode == "120000":
            present = os.path.islink(path)
        else:
            present = os.path.isfile(path)

        if not present:
            missing.append(rel)
            if len(missing) >= 30:
                break

    if missing:
        raise RuntimeError(
            "تم ضبط commit الفرع لكن بعض المسارات لم تُكتب فعليًا على القرص.\n"
            + "\n".join(missing)
        )

    # HEAD/tree equality is required in addition to physical existence.
    code, diff_lines = _git_at(self, worktree, ["diff", "--quiet", target_ref, "HEAD"])
    if code != 0:
        raise RuntimeError(
            "ملفات Worktree لا تطابق GitHub رغم اكتمال وجود المسارات على القرص.\n"
            + "\n".join(diff_lines[:30])
        )

    return len(entries)


def _sync_one_worktree(self, branch_name, index, total, registered):
    target_ref = f"{base.REMOTE}/{branch_name}"
    worktree = _safe_branch_dir(branch_name)
    worktree_norm = os.path.normcase(os.path.abspath(worktree))
    exists = os.path.isdir(worktree)

    self._ui(f"[{index}/{total}] {branch_name}: مزامنة فعلية → {worktree}")
    if exists and worktree_norm not in registered:
        raise RuntimeError(
            f"مسار ALL موجود لكنه ليس Git worktree مُسجلاً:\n{worktree}\n"
            "لن يتم لمس هذا المسار منعًا لفقد أي ملفات محلية."
        )

    target_commit = _git_value(self, ["rev-parse", "--verify", target_ref])

    if not exists:
        os.makedirs(os.path.dirname(worktree), exist_ok=True)
        code, lines = _git(
            self,
            ["worktree", "add", "--detach", "--no-checkout", worktree, target_ref],
        )
        if code != 0:
            raise RuntimeError(
                f"فشل إنشاء Worktree للفرع {branch_name}.\n"
                + ("\n".join(lines) or "")
            )
        registered.add(worktree_norm)

    # ALL intentionally does NOT use the single-branch zero-change shortcut.
    # Every branch gets a real materialization pass so a previously incomplete
    # worktree can never be reported as successful merely because HEAD matches.
    _materialize_full_tree(self, worktree, target_ref)

    code, lines = _git_at(
        self, worktree, ["submodule", "update", "--init", "--recursive"]
    )
    if code != 0:
        raise RuntimeError(
            f"فشل تحديث submodules للفرع {branch_name}.\n"
            + ("\n".join(lines) or "")
        )

    for args, label in [
        (["submodule", "foreach", "--recursive", "git", "reset", "--hard"], "تنظيف تغييرات submodules"),
        (["submodule", "foreach", "--recursive", "git", "clean", "-fdx"], "تنظيف ملفات submodules"),
    ]:
        code, lines = _git_at(self, worktree, args)
        if code != 0:
            raise RuntimeError(
                f"فشل {label} للفرع {branch_name}.\n" + ("\n".join(lines) or "")
            )

    final_commit = _git_at_value(self, worktree, ["rev-parse", "HEAD"])
    if final_commit != target_commit:
        raise RuntimeError(
            f"الـ commit النهائي للفرع {branch_name} لا يطابق GitHub.\n"
            f"Local: {final_commit}\nGitHub: {target_commit}"
        )

    file_count = _verify_full_materialization(self, worktree, target_ref)

    code, status_lines = _git_at(
        self, worktree, ["status", "--porcelain", "--ignored"]
    )
    if code != 0 or status_lines:
        raise RuntimeError(
            f"بقيت حالة محلية في Worktree للفرع {branch_name}; لم نعلن التطابق.\n"
            + "\n".join(status_lines[:50])
        )

    self._ui(
        f"[{index}/{total}] {branch_name}: EXACT MATCH ✓ | "
        f"Commit {final_commit[:12]} | Files materialized: {file_count}"
    )

    return {
        "branch": branch_name,
        "worktree": worktree,
        "commit": target_commit,
        "files": file_count,
        "added": file_count if not exists else 0,
        "updated": 0,
        "removed": 0,
        "extra": 0,
    }


def restore_all(self, branches):
    self._ui("=" * 76)
    self._ui("ORION ALL-BRANCH FULL MATERIALIZATION SYNC STARTED")
    self._ui("ALL = كل فرع في Worktree مستقل + تحميل فعلي لكل ملفات المشروع")
    self._ui("PROJECT_ROOT لن يتم تبديله أو الكتابة فوقه أثناء ALL")
    self._ui(f"الفروع المكتشفة: {len(branches)}")
    self._ui(f"Worktrees root: {ALL_WORKTREE_ROOT}")

    self._ui("[1/3] فحص المستودع المحلي...")
    if _git_value(self, ["rev-parse", "--is-inside-work-tree"]) != "true":
        raise RuntimeError("المجلد المحلي ليس مستودع Git صالحًا.")

    self._ui("[2/3] جلب جميع فروع GitHub دفعة واحدة...")
    code, lines = _git(
        self,
        ["fetch", "--prune", base.REMOTE, "+refs/heads/*:refs/remotes/origin/*"],
    )
    if code != 0:
        raise RuntimeError(
            "فشل جلب الفروع من GitHub.\n"
            + ("\n".join(lines) or "Git fetch failed.")
        )
    for line in lines:
        self._ui(line)

    self._ui("[3/3] تحميل ملفات كل فرع فعليًا في Worktree مستقل...")
    registered = _registered_worktrees(self)
    results = []
    for index, branch_name in enumerate(branches, 1):
        results.append(
            _sync_one_worktree(self, branch_name, index, len(branches), registered)
        )

    commits = {item["branch"]: item["commit"] for item in results}
    self._save_all_sync_state(commits)
    total_files = sum(item["files"] for item in results)
    total_added = sum(item["added"] for item in results)
    total_updated = sum(item["updated"] for item in results)
    total_removed = sum(item["removed"] + item["extra"] for item in results)

    self.root.after(0, self.files_var.set, str(total_files))
    self.root.after(0, self.added_var.set, str(total_added))
    self.root.after(0, self.updated_var.set, str(total_updated))
    self.root.after(0, self.removed_var.set, str(total_removed))

    self._ui("=" * 76)
    self._ui(
        f"ALL SYNC COMPLETED — {len(results)}/{len(branches)} branches EXACT MATCH ✓"
    )
    self._ui(
        f"إجمالي الملفات/المسارات الموجودة فعليًا داخل Worktrees: {total_files}"
    )
    self._ui(f"مكان المحتوى الكامل لكل الفروع: {ALL_WORKTREE_ROOT}")
    self._ui("كل فرع محفوظ منفصلًا؛ لا يوجد خلط بين فرع وآخر.")
    self._ui("PROJECT_ROOT لم يتم تبديله أو الكتابة فوقه أثناء ALL.")
    self._ui("=" * 76)

    # Make the actual ALL destination visible immediately after success.
    if os.name == "nt":
        try:
            os.startfile(ALL_WORKTREE_ROOT)
        except OSError:
            pass

    self.root.after(
        0,
        self._finish_all,
        True,
        f"تمت مزامنة وتحميل محتويات جميع الفروع ({len(results)}) بنجاح دون خلط بينها.",
    )


# Preserve the proven individual-branch path; replace only ALL.
base.OrionRestoreApp._restore_all = restore_all

if __name__ == "__main__":
    root = tk.Tk()
    app = base.OrionRestoreApp(root)
    app.source_label.configure(
        text=(
            "GitHub → Git → Local  |  ALL (full separate worktrees)"
            if app.branch == ALL_BRANCH
            else f"GitHub → Git → Local  |  {app.branch}"
        )
    )
    root.mainloop()
