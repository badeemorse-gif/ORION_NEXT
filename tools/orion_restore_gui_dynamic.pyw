import importlib.util,os,threading,tkinter as tk
from tkinter import messagebox
TARGET=os.path.join(os.path.dirname(__file__),"orion_restore_gui.pyw");s=importlib.util.spec_from_file_location("orion_restore_base",TARGET);base=importlib.util.module_from_spec(s);s.loader.exec_module(base)
ALL="ALL";FALLBACK=("main","orion-canonical-pipeline-boundary","phase2/core-intelligence-hardening")
def discover(self):
 c,ls=self._git(["ls-remote","--heads",base.REMOTE])
 if c: raise RuntimeError("تعذر قراءة فروع GitHub الحالية.\n"+"\n".join(ls))
 bs=[]
 for l in ls:
  p=l.split("\t",1)
  if len(p)==2 and p[1].strip().startswith("refs/heads/"):
   n=p[1].strip()[11:]
   if n and n not in bs:bs.append(n)
 return sorted(bs,key=lambda x:(x!="main",x.lower())) or list(FALLBACK)
def br(self):
 v=self.branch_var.get().strip();return v if v==ALL or v in getattr(self,"branches",FALLBACK) else base.DEFAULT_BRANCH
def apply(self,bs):
 self.branches=list(bs);self.branch_combo.configure(values=(ALL,*self.branches));v=self.branch_var.get().strip();self.branch_var.set(v if v in (ALL,*self.branches) else (base.DEFAULT_BRANCH if base.DEFAULT_BRANCH in self.branches else self.branches[0]));self._write(f"تم تحديث قائمة الفروع من GitHub: {len(self.branches)} فرعًا.")
def refresh(self):
 if self.running:return
 def w():
  try:self.root.after(0,apply,self,discover(self));self.root.after(0,self._status,"جاهز للاستعادة",self.success)
  except Exception as e:self._ui(f"تعذر تحديث قائمة الفروع: {e}")
 threading.Thread(target=w,daemon=True).start()
def restore(self):
 bs=discover(self);self.root.after(0,apply,self,bs)
 if self.branch==ALL:return allsync(self,bs)
 old=getattr(base,"BRANCHES",());base.BRANCHES=tuple(bs)
 try:original(self)
 finally:base.BRANCHES=old
def allsync(self,bs):
 self._ui(f"ALL = تحديث جميع فروع GitHub الحالية ({len(bs)} فرعًا) داخل مستودع Git المحلي.")
 for i,b in enumerate(bs,1):
  c,ls=self._git(["fetch",base.REMOTE,b])
  if c:raise RuntimeError(f"فشل جلب GitHub/{b}.\n"+"\n".join(ls))
  self._ui(f"[{i}/{len(bs)}] GitHub/{b}: "+self._git_value(["rev-parse","--verify",f"{base.REMOTE}/{b}"]))
 self._save_all_sync_state({b:self._git_value(["rev-parse","--verify",f"{base.REMOTE}/{b}"]) for b in bs})
 for v in(self.files_var,self.added_var,self.updated_var,self.removed_var):self.root.after(0,v.set,"0")
 self.root.after(0,self._finish,True,f"تمت مزامنة جميع الفروع ({len(bs)}) محليًا. الإحصائيات: 0 لأن working tree لم يتغير.")
original=base.OrionRestoreApp._restore;base.OrionRestoreApp.branch=property(br);base.OrionRestoreApp._restore=restore;base.OrionRestoreApp.refresh_branches=refresh
r=tk.Tk() if os.path.isdir(base.PROJECT_ROOT) else None
if r:
 a=base.OrionRestoreApp(r);r.after(250,a.refresh_branches);r.mainloop()
else:
 r=tk.Tk();r.withdraw();messagebox.showerror("ORION Restore",f"مشروع ORION غير موجود:\n\n{base.PROJECT_ROOT}")
