# ORION Restore — MAIN / ALL / Final Materialization Contract

الإصدار: 3.0  
الحالة: ACTIVE — FINAL MATERIALIZATION CONTRACT

## 1. قاعدة الحوكمة

أثناء التطوير:

```text
GitHub = Source of Truth
```

`ORION_NEXT` هو Development / Integration Working Tree محلي، وليس mirror destination.

أي Snapshot غير مرتبط بــ Git commit محدد لا يُعامل كمصدر تطوير أو Restore مرجعي.

## 2. MAIN وALL isolation

المسارات المرجعية المعزولة هي:

```text
ORION_NEXT_MAIN
ORION_NEXT_ALL_BRANCHES
```

ولا يجوز لأي مسار MAIN/ALL أن يكتب فوق:

```text
ORION_NEXT
```

أثناء التطوير.

القواعد المشتركة:

- لا `checkout` أو `switch` إلى فرع بهدف materialization.
- لا `reset --hard`.
- لا `clean -fdx`.
- لا mirror يومي destructive داخل `ORION_NEXT`.
- لا branch يكتب في target فرع آخر.
- file/directory/symlink collisions لا تتجاوز حدود staging.
- لا target داخل `PROJECT_ROOT` أو داخل parent Git checkout.

## 3. MAIN mirror — legacy/reference isolation

الأدوات القديمة التي كانت تعرّف MAIN باعتباره كاتبًا داخل `ORION_NEXT` محفوظة كـ`LEGACY / FROZEN`.

أما المسار الآمن الحالي فيستخدم snapshot معزولًا ومتحققًا. `tools/orion_main_sync_verify.py` يبقى verifier مستقلًا ولا يكتب إلى المشروع.

عند وجود حاجة إلى MAIN mirror مرجعي، تكون الوجهة المعزولة خارج `ORION_NEXT`، ويجب أن يطابق manifest المصدر كاملًا.

## 4. ALL mirror — legacy/reference isolation

ALL يحتفظ بفكرة snapshots مستقلة لكل branch، لكن لا يملك صلاحية الكتابة في `ORION_NEXT`.

التصميم لا يعتمد على `git worktree` ولا على تبديل الفرع الحالي. الأدوات القديمة وواجهات GUI التي تقوم بالنقل التقليدي تبقى `LEGACY / FROZEN` ما لم يصدر قرار قيادة مختلف.

## 5. Final Materialization — المسار المعتمد

Final Materialization ليست Sync يومية وليست Restore من Local snapshot.

العقد هو:

```text
GitHub exact commit
        ↓
Fetch exact commit object
        ↓
git archive <commit>
        ↓
Clean isolated staging
        ↓
Complete manifest + SHA-256 parity
        ↓
Atomic target replacement
        ↓
Complete target parity
```

المحرك المعتمد:

```text
tools/orion_final_materialize.py
```

### المدخلات

- `--commit`: SHA كامل من 40 خانة.
- `--target`: مسار خارجي عن `ORION_NEXT`.
- `--remote`: افتراضيًا `origin`، ويجب أن يشير إلى مستودع ORION_NEXT الرسمي.

### المخرجات

نجاح العملية لا يُعلن إلا بعد:

```text
SOURCE: GitHub exact commit <SHA>
PARITY: EXACT MATCH
RESULT: FINAL MATERIALIZATION SUCCESS
```

## 6. Atomicity / rollback

لا يكتب المحرك مباشرة في target أثناء بناء snapshot.

يُنشأ staging جديد، ثم:

1. يُستخرج archive داخله.
2. يُتحقق من المسارات والأنواع والبصمات.
3. بعد نجاح staging فقط يُنقل target القديم إلى backup مؤقت.
4. يُنقل staging إلى target.
5. تُعاد parity كاملة.
6. عند النجاح يُحذف backup.
7. عند الفشل يُعاد target السابق ويُحذف staging غير المكتمل.

وبذلك لا توجد حالة نجاح تعتمد على نقل جزئي.

## 7. Parity contract

المقارنة ليست بعدد الملفات فقط.

لكل path تتم مطابقة:

```text
type
size
SHA-256(content)
```

وتشمل directories وfiles وsymlinks المدعومة.

أي:

```text
missing path   → FAIL
extra path     → FAIL
different type → FAIL
different size → FAIL
different hash → FAIL
```

## 8. Collision safety

إذا كان المصدر يحتوي على تعارض من نوع:

```text
file ↔ directory
file ↔ symlink
directory ↔ symlink
```

فلا يجوز الكتابة فوق `ORION_NEXT` ولا target أثناء بناء snapshot. المعالجة تتم داخل staging فقط، وأي archive غير صالح أو غير قابل للتمثيل بأمان يؤدي إلى رفض العملية.

## 9. الأدوات والحالة

```text
tools/orion_sync.bat              LEGACY / FROZEN
tools/orion_main_sync.bat         LEGACY / FROZEN
tools/orion_all_sync.bat          LEGACY / FROZEN
tools/orion_restore_gui.pyw       LEGACY / FROZEN
tools/orion_restore_main_gui.pyw  compatibility launcher
tools/orion_sync_safe.py          guarded legacy/reference controller
tools/orion_sync_guard.py         safety guard
tools/orion_main_sync_verify.py   independent MAIN parity verifier
tools/orion_final_materialize.py  ACTIVE final materialization engine
```

وجود الأدوات القديمة لا يجعلها مسار التطوير الجديد.

## 10. Definition of Done لهذا العقد

يُعتبر المسار مكتملًا عندما تكون القواعد التالية قابلة للتحقق:

- GitHub commit محدد هو المصدر.
- `ORION_NEXT` لا يُستخدم كهدف mirror أثناء التطوير.
- MAIN وALL معزولان عن Development Working Tree.
- لا cross-branch contamination.
- لا destructive sync غير مقصود.
- لا file/directory collision يتجاوز staging.
- لا نقل لملفات خارج target snapshot.
- staging parity وtarget parity كاملتان.
- rollback موجود عند فشل post-install verification.
- الأدوات القديمة باقية كـLEGACY/FROZEN.
- لا تغيير في Production Logic أو business semantics.
