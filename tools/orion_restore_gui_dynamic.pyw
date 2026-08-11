import importlib.util,os,threading,tkinter as tk
from tkinter import messagebox
BASE_NAME="orion_restore_gui.pyw"; TARGET=os.path.join(os.path.dirname(__file__),BASE_NAME)
spec=importlib.util.spec_from_file_location("orion_restore_base",TARGET); base=importlib.util.module_from_spec(spec); spec.loader.exec_module(base)
ALL_BRANCH="ALL"; FALLBACK=("main","orion-canonical-pipeline-boundary","phase2/core-intelligence-hardening")
def discover(self):
 c,ls=self._git(["ls-remote","--heads",base.REMOTE])
 if c!=0: raise RuntimeError("تعذر قراءة فروع GitHub الحالية.\n"+("\n".join(ls) or "git ls-remote failed."))
 bs=[]
 for l in ls:
  p=l.split("\t",1)
  if len(p)==2 and p[1].strip().startswith("refs/heads/"):
   n=p[1].strip()[11:]
   if n and n not in bs: bs.append(n)
 if not bs: raise RuntimeError("لم يتم العثور على أي فرع في GitHub.")
 return sorted(bs,key=lambda x:(x!="main",x.lower()))
def branch(self):
 v=self.branch_var.get().strip(); return v if v==ALL_BRANCH or v in getattr(self,"branches",FALLBACK) else base.DEFAULT_BRANCH
def changed(self,_=None):
 if not self.running: self.source_label.configure(text=(f"GitHub → Git → Local  |  ALL ({len(self.branches)} branches)" if self.branch==ALL_BRANCH else f"GitHub → Git → Local  |  {self.branch}")); self._write(f"Target branch changed to: {self.branch}")
def apply(self,bs):
 cur=self.branch_var.get().strip(); self.branches=list(bs); vals=(ALL_BRANCH,*self.branches); self.branch_combo.configure(values=vals); self.branch_var.set(cur if cur in vals else (base.DEFAULT_BRANCH if base.DEFAULT_BRANCH in self.branches else self.branches[0])); changed(self); self._write(f"تم تحديث قائمة الفروع من GitHub: {len(self.branches)} فرعًا.")
def refresh(self):
 if self.running:return
 def w():
  try: bs=discover(self); self.root.after(0,apply,self,bs); self.root.after(0,self._status,"جاهز للاستعادة",self.success)
  except Exception as e: self._ui(f"تعذر تحديث قائمة الفروع: {e}")
 threading.Thread(target=w,daemon=True).start()
def restore(self):
 bs=discover(self); self.root.after(0,apply,self,bs)
 if self.branch==ALL_BRANCH: return restore_all(self,bs)
 old=getattr(base,"BRANCHES",()); olds=getattr(base,"SYNC_BRANCHES",()); base.BRANCHES=tuple(bs); base.SYNC_BRANCHES=tuple(bs)
 try: original(self)
 finally: base.BRANCHES=old; base.SYNC_BRANCHES=olds
def restore_all(self,bs):
 self._ui("ORION ALL-BRANCH SYNC STARTED"); self._ui(f"ALL = تحديث جميع فروع GitHub الحالية ({len(bs)} فرعًا) داخل مستودع Git المحلي."); self._ui("لن يتم تبديل working tree بين الفروع.")
 c,ls=self._git(["rev-parse","--is-inside-work-tree"])
 if c!=0 or (ls and ls[-1].strip()!="true"): raise RuntimeError("المجلد المحلي ليس مستودع Git صالحًا.")
 commits={}
 for i,b in enumerate(bs,1):
  c,ls=self._git(["fetch",base.REMOTE,b])
  if c!=0: raise RuntimeError(f"فشل جلب GitHub/{b}.\n"+("\n".join(ls) or "Git fetch failed."))
  commits[b]=self._git_value(["rev-parse","--verify",f"{base.REMOTE}/{b}"]); self._ui(f"[{i}/{len(bs)}] GitHub/{b}: {commits[b]}")
 self._save_all_sync_state(commits)
 for v in (self.files_var,self.added_var,self.updated_var,self.removed_var): self.root.after(0,v.set,"0")
 self.root.after(0,self._finish,True,f"تمت مزامنة جميع الفروع ({len(commits)}) محليًا. الإحصائيات: 0 لأن working tree لم يتغير.")
original=base.OrionRestoreApp._restore;base.OrionRestoreApp.branch=property(branch);base.OrionRestoreApp._discover_remote_branches=discover;base.OrionRestoreApp._branch_changed=changed;base.OrionRestoreApp.refresh_branches=refresh;base.OrionRestoreApp._restore=restore;base.OrionRestoreApp._restore_all=restore_all
def main():
 if not os.path.isdir(base.PROJECT_ROOT):
  r=tk.Tk();r.withdraw();messagebox.showerror("ORION Restore",f"مشروع ORION غير موجود:\n\n{base.PROJECT_ROOT}");r.destroy();return
 r=tk.Tk();a=base.OrionRestoreApp(r);r.after(250,a.refresh_branches);r.mainloop()
if __name__=="__main__":main()
