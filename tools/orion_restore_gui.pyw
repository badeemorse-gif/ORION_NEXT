import os
import subprocess
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext
import hashlib
import tarfile
import io
import re
import time

PROJECT_ROOT = r"C:\Users\badee\Desktop\ORION_NEXT"
REMOTE = "origin"
ALL_ROOT = os.path.join(os.path.dirname(PROJECT_ROOT), "ORION_NEXT_ALL_BRANCHES")
GIT_TIMEOUT = 120


def run_git(args, cwd=PROJECT_ROOT, timeout=GIT_TIMEOUT, binary=False):
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    if binary:
        p = subprocess.Popen(
            ["git", *args], cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            creationflags=flags
        )
        try:
            out, err = p.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            try:
                p.kill()
                p.communicate(timeout=5)
            except Exception:
                pass
            raise RuntimeError(f"Git timeout: {' '.join(args)}")
        return p.returncode, out, err

    p = subprocess.Popen(
        ["git", *args], cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace", creationflags=flags
    )
    try:
        out, _ = p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            p.kill()
            p.communicate(timeout=5)
        except Exception:
            pass
        raise RuntimeError(f"Git timeout after {timeout}s: {' '.join(args)}")
    return p.returncode, [x.rstrip() for x in (out or "").splitlines() if x.rstrip()]


def git_value(args):
    code, lines = run_git(args)
    if code:
        raise RuntimeError("\n".join(lines) or f"Git failed: {' '.join(args)}")
    return lines[-1].strip() if lines else ""


def safe_branch_name(name):
    safe = re.sub(r'[<>:"/\\|?*]+', "__", name).strip(" .")
    if not safe:
        safe = "branch"
    if safe != name:
        safe += "__" + hashlib.sha1(name.encode("utf-8")).hexdigest()[:8]
    return safe


def discover_branches():
    code, lines = run_git(["ls-remote", "--heads", REMOTE])
    if code:
        raise RuntimeError("\n".join(lines) or "تعذر قراءة فروع GitHub.")
    result = []
    for line in lines:
        parts = line.split("\t", 1)
        if len(parts) != 2:
            continue
        ref = parts[1].strip()
        if ref.startswith("refs/heads/"):
            branch = ref[len("refs/heads/"):]
            if branch and branch not in result:
                result.append(branch)
    if not result:
        raise RuntimeError("لم يتم العثور على فروع في GitHub.")
    return sorted(result, key=lambda x: (x.lower() != "main", x.lower()))


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def local_manifest(root):
    manifest = {}
    if not os.path.isdir(root):
        return manifest
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d != ".git"]
        for name in files:
            full = os.path.join(base, name)
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            try:
                manifest[rel] = ("file", os.path.getsize(full), sha256_file(full))
            except OSError:
                pass
        for name in dirs:
            full = os.path.join(base, name)
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            if os.path.islink(full):
                try:
                    manifest[rel] = ("link", os.readlink(full))
                except OSError:
                    pass
    return manifest


def read_archive_manifest(ref):
    code, archive, err = run_git(["archive", "--format=tar", ref], binary=True)
    if code:
        msg = err.decode("utf-8", "replace") if err else ""
        raise RuntimeError(f"git archive failed for {ref}: {msg}")

    manifest = {}
    tf = tarfile.open(fileobj=io.BytesIO(archive), mode="r:")
    for m in tf.getmembers():
        rel = m.name.replace("\\", "/").lstrip("./")
        if not rel:
            continue
        if m.isdir():
            manifest[rel] = ("dir",)
        elif m.issym():
            manifest[rel] = ("link", m.linkname)
        elif m.isfile():
            data = tf.extractfile(m).read()
            manifest[rel] = ("file", len(data), hashlib.sha256(data).hexdigest())
        else:
            manifest[rel] = ("special",)
    tf.close()
    return archive, manifest


def safe_target(root, rel):
    full = os.path.abspath(os.path.join(root, rel.replace("/", os.sep)))
    root_abs = os.path.abspath(root)
    if os.path.commonpath([root_abs, full]) != root_abs:
        raise RuntimeError(f"مسار غير آمن داخل archive: {rel}")
    return full


def materialize_archive(archive, root, target_manifest, old_manifest):
    os.makedirs(root, exist_ok=True)
    added = updated = removed = 0

    # Exact mirror inside this branch folder only: remove paths absent from GitHub.
    for rel in old_manifest:
        if rel not in target_manifest:
            full = safe_target(root, rel)
            if os.path.isfile(full) or os.path.islink(full):
                try:
                    os.remove(full)
                    removed += 1
                except OSError:
                    pass

    tf = tarfile.open(fileobj=io.BytesIO(archive), mode="r:")
    for m in tf.getmembers():
        rel = m.name.replace("\\", "/").lstrip("./")
        if not rel:
            continue
        full = safe_target(root, rel)

        if m.isdir():
            os.makedirs(full, exist_ok=True)
            continue

        os.makedirs(os.path.dirname(full), exist_ok=True)

        if m.issym():
            old = old_manifest.get(rel)
            if old == ("link", m.linkname):
                continue
            if os.path.lexists(full):
                try:
                    os.remove(full)
                except OSError:
                    pass
            try:
                os.symlink(m.linkname, full)
            except OSError:
                # Windows may deny symlink creation. Preserve the link target text
                # rather than making the whole ALL operation fail.
                with open(full, "w", encoding="utf-8") as f:
                    f.write(m.linkname)
            if old:
                updated += 1
            else:
                added += 1
            continue

        if not m.isfile():
            continue

        data = tf.extractfile(m).read()
        new_sig = ("file", len(data), hashlib.sha256(data).hexdigest())
        if old_manifest.get(rel) == new_sig:
            continue

        existed = os.path.lexists(full)
        tmp = full + ".orion_tmp"
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, full)
        if existed:
            updated += 1
        else:
            added += 1

    tf.close()

    # Remove now-empty directories that are no longer needed.
    for base, dirs, files in os.walk(root, topdown=False):
        if base != root and not dirs and not files:
            try:
                os.rmdir(base)
            except OSError:
                pass

    return added, updated, removed


class OrionAllRestore:
    def __init__(self, root):
        self.root = root
        self.root.title("ORION Restore — ALL")
        self.root.geometry("900x610")
        self.root.minsize(780, 520)
        self.root.configure(bg="#101820")
        self.running = False
        self.branches = []
        self.status = tk.StringVar(value="جاهز")
        self.total_files = tk.StringVar(value="0")
        self.total_added = tk.StringVar(value="0")
        self.total_updated = tk.StringVar(value="0")
        self.total_removed = tk.StringVar(value="0")
        self._build()
        self.refresh_branches()

    def _build(self):
        tk.Label(self.root, text="ORION RESTORE", font=("Segoe UI", 22, "bold"),
                 bg="#101820", fg="#f2f5f7").pack(pady=(18, 2))
        tk.Label(self.root, text="GitHub → Local  |  ALL — كل الفروع منفصلة",
                 font=("Segoe UI", 10), bg="#101820", fg="#9aa8b2").pack()

        panel = tk.Frame(self.root, bg="#17232d")
        panel.pack(fill="x", padx=24, pady=10)
        self._row(panel, "Repository", "ORION_NEXT")
        self._row(panel, "Project", PROJECT_ROOT)
        self._row(panel, "Destination", ALL_ROOT)

        s = tk.Frame(self.root, bg="#101820")
        s.pack(fill="x", padx=24, pady=(3, 4))
        tk.Label(s, text="الحالة:", bg="#101820", fg="#9aa8b2",
                 font=("Segoe UI", 9, "bold")).pack(side="left")
        self.status_label = tk.Label(s, textvariable=self.status, bg="#101820",
                                     fg="#3fc36b", font=("Segoe UI", 9, "bold"))
        self.status_label.pack(side="left", padx=8)

        cards = tk.Frame(self.root, bg="#101820")
        cards.pack(fill="x", padx=24, pady=3)
        self.branch_count_label = None
        for i, (title, var, color) in enumerate([
            ("BRANCHES", None, "#2eaadc"),
            ("FILES", self.total_files, "#2eaadc"),
            ("ADDED", self.total_added, "#3fc36b"),
            ("UPDATED", self.total_updated, "#2eaadc"),
            ("REMOVED", self.total_removed, "#e05252"),
        ]):
            cards.grid_columnconfigure(i, weight=1)
            c = tk.Frame(cards, bg="#182538")
            c.grid(row=0, column=i, sticky="nsew", padx=3)
            tk.Label(c, text=title, bg="#182538", fg="#9aa8b2",
                     font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=8, pady=(6, 0))
            if title == "BRANCHES":
                self.branch_count_label = tk.Label(c, text="0", bg="#182538", fg=color,
                                                   font=("Segoe UI", 16, "bold"))
                self.branch_count_label.pack(anchor="w", padx=8, pady=(0, 6))
            else:
                tk.Label(c, textvariable=var, bg="#182538", fg=color,
                         font=("Segoe UI", 16, "bold")).pack(anchor="w", padx=8, pady=(0, 6))

        self.button = tk.Button(
            self.root, text="⬇  مزامنة ALL — جميع الفروع", command=self.start,
            bg="#2eaadc", fg="white", activebackground="#2eaadc",
            relief="flat", font=("Segoe UI", 12, "bold"), padx=25, pady=10
        )
        self.button.pack(pady=(9, 6))

        tk.Label(
            self.root,
            text="كل فرع يُحفظ في مجلد مستقل. لا توجد Worktrees ولا تبديل للفرع الرئيسي.",
            bg="#101820", fg="#e0a52e", font=("Segoe UI", 8)
        ).pack()

        tk.Label(self.root, text="سجل المزامنة", bg="#101820", fg="#9aa8b2",
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=24, pady=(8, 3))
        self.output = scrolledtext.ScrolledText(
            self.root, height=13, bg="#0b1116", fg="#d9e1e6",
            insertbackground="white", font=("Consolas", 9), relief="flat", bd=0,
            wrap="word"
        )
        self.output.pack(fill="both", expand=True, padx=24, pady=(0, 14))

    def _row(self, parent, label, value):
        row = tk.Frame(parent, bg="#17232d")
        row.pack(fill="x", padx=12, pady=4)
        tk.Label(row, text=label + ":", width=12, anchor="w",
                 bg="#17232d", fg="#9aa8b2", font=("Segoe UI", 8, "bold")).pack(side="left")
        tk.Label(row, text=value, anchor="w", bg="#17232d", fg="#f2f5f7",
                 font=("Segoe UI", 8)).pack(side="left", fill="x", expand=True)

    def write(self, text):
        self.output.insert("end", text + "\n")
        self.output.see("end")

    def ui(self, text):
        self.root.after(0, self.write, text)

    def set_status(self, text, color="#3fc36b"):
        self.root.after(0, self.status.set, text)
        self.root.after(0, self.status_label.configure, {"fg": color})

    def refresh_branches(self):
        def worker():
            try:
                branches = discover_branches()
                self.branches = branches
                self.root.after(0, self.branch_count_label.configure, {"text": str(len(branches))})
                self.write(f"تم اكتشاف {len(branches)} فرعًا من GitHub.")
            except Exception as exc:
                self.set_status("تعذر اكتشاف الفروع", "#e05252")
                self.ui(str(exc))
        threading.Thread(target=worker, daemon=True).start()

    def start(self):
        if self.running:
            return
        self.running = True
        self.button.configure(state="disabled", text="⏳ جاري مزامنة ALL...")
        for v in (self.total_files, self.total_added, self.total_updated, self.total_removed):
            v.set("0")
        threading.Thread(target=self.sync_all, daemon=True).start()

    def sync_all(self):
        started = time.time()
        try:
            if not os.path.isdir(PROJECT_ROOT):
                raise RuntimeError(f"المشروع المحلي غير موجود:\n{PROJECT_ROOT}")

            self.set_status("جاري جلب جميع الفروع...", "#2eaadc")
            self.ui("=" * 68)
            self.ui("ORION ALL SYNC — FAST ARCHIVE MODE")
            self.ui("لا يتم إنشاء Git Worktree؛ يتم نقل محتوى كل branch مباشرة إلى مجلده المستقل.")

            code, lines = run_git([
                "fetch", "--prune", REMOTE,
                "+refs/heads/*:refs/remotes/origin/*"
            ])
            if code:
                raise RuntimeError("\n".join(lines) or "فشل git fetch.")
            for line in lines:
                self.ui(line)

            branches = discover_branches()
            self.branches = branches
            self.root.after(0, self.branch_count_label.configure, {"text": str(len(branches))})
            os.makedirs(ALL_ROOT, exist_ok=True)

            grand = {"files": 0, "added": 0, "updated": 0, "removed": 0}
            for i, branch in enumerate(branches, 1):
                self.set_status(f"مزامنة {i}/{len(branches)}: {branch}", "#2eaadc")
                ref = f"{REMOTE}/{branch}"
                dest = os.path.join(ALL_ROOT, safe_branch_name(branch))
                self.ui(f"[{i}/{len(branches)}] {branch}")
                self.ui(f"    الهدف: {dest}")

                archive, target = read_archive_manifest(ref)
                old = local_manifest(dest)
                added, updated, removed = materialize_archive(archive, dest, target, old)
                files = sum(1 for x in target.values() if x[0] in ("file", "link", "special"))

                grand["files"] += files
                grand["added"] += added
                grand["updated"] += updated
                grand["removed"] += removed
                self.ui(
                    f"    ✓ Files: {files} | Added: {added} | Updated: {updated} | Removed: {removed}"
                )
                self.root.after(0, self.total_files.set, str(grand["files"]))
                self.root.after(0, self.total_added.set, str(grand["added"]))
                self.root.after(0, self.total_updated.set, str(grand["updated"]))
                self.root.after(0, self.total_removed.set, str(grand["removed"]))

            elapsed = time.time() - started
            self.ui("=" * 68)
            self.ui(f"ALL COMPLETED ✓ — {len(branches)} branches synchronized.")
            self.ui(f"Total branch-files: {grand['files']}")
            self.ui(
                f"Transferred: +{grand['added']} added | ~{grand['updated']} updated | -{grand['removed']} removed"
            )
            self.ui(f"Destination: {ALL_ROOT}")
            self.ui(f"Elapsed: {elapsed:.1f}s")
            self.set_status(f"تمت مزامنة {len(branches)} فرعًا بنجاح ✓", "#3fc36b")
            self.root.after(
                0, messagebox.showinfo, "ORION RESTORE",
                f"تمت مزامنة جميع الفروع بنجاح.\n\n"
                f"الفروع: {len(branches)}\n"
                f"Added: {grand['added']}\n"
                f"Updated: {grand['updated']}\n"
                f"Removed: {grand['removed']}\n\n"
                f"المجلد: {ALL_ROOT}"
            )
        except Exception as exc:
            self.ui("=" * 68)
            self.ui("ERROR — لم تكتمل المزامنة.")
            self.ui(str(exc))
            self.set_status("فشلت المزامنة", "#e05252")
            self.root.after(0, messagebox.showerror, "ORION RESTORE", str(exc))
        finally:
            self.root.after(0, self.button.configure, {"state": "normal", "text": "⬇  مزامنة ALL — جميع الفروع"})
            self.running = False


if __name__ == "__main__":
    root = tk.Tk()
    OrionAllRestore(root)
    root.mainloop()
