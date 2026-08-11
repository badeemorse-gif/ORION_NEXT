import importlib.util
import os
import threading
import tkinter as tk
from tkinter import messagebox
BASE_NAME="orion_restore_gui.pyw"
TARGET=os.path.join(os.path.dirname(__file__),BASE_NAME)
spec=importlib.util.spec_from_file_location("orion_restore_base",TARGET); base=importlib.util.module_from_spec(spec); spec.loader.exec_module(base)
ALL_BRANCH="ALL"; FALLBACK=("main","orion-canonical-pipeline-boundary","phase2/core-intelligence-hardening")
def discover(self):
 code,lines=self._git(["ls-remote","--heads",base.REMOTE])
 if code!=0: raise RuntimeError("تعذر قراءة فروع GitHub الحالية.\n"+("\n".join(lines) or "git ls-remote failed."))
 branches=[]
 for line in lines:
  parts=line.split("\t",1)
  if len(parts)==2 and parts[1].strip().startswith("refs/heads/"):
   name=parts[1].strip()[11:]
   if name and name not in branches: branches.append(name)
 if not branches: raise RuntimeError("لم يتم العثور على أي فرع في GitHub.")
 return sorted(branches,key=lambda x:(x!="main",x.lower()))
def branch(self):
 value=self.branch_var.get().strip(); return value if value==ALL_BRANCH or value in getattr(self,"branches",FALLBACK) else base.DEFAULT_BRANCH
def changed(self,_event=None):
 if not self.running: self.source_label.configure(text=(f"GitHub → Git → Local  |  ALL ({len(self.branches)} branches)" if self.branch==ALL_BRANCH else f"GitHub → Git → Local  |  {self.branch}")); self._write(f"Target branch changed to: {self.branch}")
def apply_branches(self,branches):
 current=self.branch_var.get().strip(); self.branches=list(branches); values=(ALL_BRANCH,*self.branches); self.branch_combo.configure(values=values)
 self.branch_var.set(current if current in values else (base.DEFAULT_BRANCH if base.DEFAULT_BRANCH in self.branches else self.branches[0])); changed(self); self._write(f"تم تحديث قائمة الفروع من GitHub: {len(self.branches)} فرعًا.")
def refresh(self):
 if self.running:return
 def worker():
  try: branches=discover(self); self.root.after(0,apply_branches,self,branches); self.root.after(0,self._status,"جاهز للاستعادة",self.success)
  except Exception as exc: self._ui(f"تعذر تحديث قائمة الفروع: {exc}"); self.root.after(0,self._status,"تعذر تحديث الفروع — القائمة السابقة متاحة",self.warning)
 threading.Thread(target=worker,daemon=True).start()
def restore(self):
 branches=discover(self); self.root.after(0,apply_branches,self,branches)
 if self.branch==ALL_BRANCH: restore_all(self,branches); return
 old_branches=getattr(base,"BRANCHES",()); old_sync=getattr(base,"SYNC_BRANCHES",()); base.BRANCHES=tuple(branches); base.SYNC_BRANCHES=tuple(branches)
 try: original_restore(self)
 finally: base.BRANCHES=old_branches; base.SYNC_BRANCHES=old_sync
def restore_all(self,branches):
 self._ui("="*64); self._ui("ORION ALL-BRANCH SYNC STARTED"); self._ui("="*64); self._ui(f"ALL = تحديث جميع فروع GitHub الحالية ({len(branches)} فرعًا) داخل مستودع Git المحلي."); self._ui("لن يتم تبديل working tree بين الفروع.")
 code,lines=self._git(["rev-parse","--is-inside-work-tree"])
 if code!=0 or (lines and lines[-1].strip()!="true"): raise RuntimeError("المجلد المحلي ليس مستودع Git صالحًا.")
 commits={}
 for index,b in enumerate(branches,1):
  code,lines=self._git(["fetch",base.REMOTE,b])
  if code!=0: raise RuntimeError(f"فشل جلب GitHub/{b}.\n"+("\n".join(lines) or "Git fetch failed."))
  commit=self._git_value(["rev-parse","--verify",f"{base.REMOTE}/{b}"]); commits[b]=commit; self._ui(f"[{index}/{len(branches)}] GitHub/{b}: {commit}")
 self._save_all_sync_state(commits); [self.root.after(0,v.set,"0") for v in (self.files_var,self.added_var,self.updated_var,self.removed_var)]; self.root.after(0,self._finish,True,f"تمت مزامنة جميع الفروع ({len(commits)}) محليًا. الإحصائيات: 0 لأن working tree لم يتغير.")
original_restore=base.OrionRestoreApp._restore
base.OrionRestoreApp.branch=property(branch); base.OrionRestoreApp._discover_remote_branches=discover; base.OrionRestoreApp._branch_changed=changed; base.OrionRestoreApp._apply_branches=apply_branches; base.OrionRestoreApp.refresh_branches=refresh; base.OrionRestoreApp._restore=restore; base.OrionRestoreApp._restore_all=restore_all
def main():
 if not os.path.isdir(base.PROJECT_ROOT):
  root=tk.Tk(); root.withdraw(); messagebox.showerror("ORION Restore",f"مشروع ORION غير موجود:\n\n{base.PROJECT_ROOT}"); root.destroy(); return
 root=tk.Tk(); app=base.OrionRestoreApp(root); app.source_label.configure(text=f"GitHub → Git → Local  |  {app.branch}"); root.after(250,app.refresh_branches); root.mainloop()
if __name__=="__main__": main()
