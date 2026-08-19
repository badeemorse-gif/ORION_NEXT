# ORION — Sync & Final Materialization Policy

الإصدار: 2.0  
الحالة: ACTIVE

## 1. مصدر الحقيقة

أثناء التطوير:

```text
GitHub = Source of Truth
```

المطورون داخل ChatGPT يعملون على فروع GitHub ويكملون حزمًا كاملة داخل نطاقاتهم.

لا تستخدم GITHUB → LOCAL كمزامنة يومية بعد كل تعديل صغير، ولا تعتبر أي Snapshot غير Git مرجعًا للتطوير.

## 2. بيئة ORION_NEXT المحلية

```text
C:\Users\badee\Desktop\ORION_NEXT
```

هذه هي بيئة Development / Integration المحلية.

أثناء البناء لا يجوز لأي sync/restore/mirror أن يكتب فوقها أو يستخدمها كوجهة لفرع آخر. لا توجد مزامنة تلقائية إلى هذه البيئة أثناء التطوير.

## 3. نموذج التطوير

```text
Architecture Boundary
↓
Complete Slice
↓
Contracts
↓
Implementation
↓
Compatibility / Documentation
↓
Commit to GitHub Branch
↓
Final Report
```

لا يحتاج المطور إلى نقل Local أثناء الحزمة. إذا ظهر blocker خارج نطاقه، يوثقه ولا يصلحه من تلقاء نفسه.

## 4. MAIN / ALL isolation

`ORION_NEXT_MAIN` و`ORION_NEXT_ALL_BRANCHES` مرايا مرجعية معزولة وليستا Development Working Trees.

القواعد الصارمة:

- MAIN لا يكتب `ORION_NEXT` أثناء التطوير.
- ALL لا يكتب `ORION_NEXT` إطلاقًا.
- لا يسمح لأي فرع بالكتابة داخل مجلد فرع آخر.
- لا يوجد `checkout`, `switch`, `reset --hard`, أو `clean -fdx` ضمن مسار materialization.
- file/directory/symlink collisions يجب أن تفشل بأمان أو تُعالج داخل staging فقط.

## 5. المزامنة القديمة

الأدوات القديمة مثل `tools/orion_sync.bat` وواجهات restore/sync التي تعتمد على النقل اليومي تعتبر:

```text
LEGACY / FROZEN
```

وجودها للحفاظ على lineage/compatibility ولا يعني أنها المسار المعتمد للتطوير أو finalization، ما لم يصدر قرار قيادة موثق.

## 6. Final Materialization — العقد المعتمد

عند اكتمال التكامل وصدور قرار materialization فقط:

```text
GitHub exact commit
        ↓
Fetch exact commit object
        ↓
git archive <commit>
        ↓
Clean isolated staging
        ↓
Manifest + SHA-256 parity verification
        ↓
Atomic install into external target
        ↓
Final parity verification
```

المسار التنفيذي المعتمد هو:

```text
tools/orion_final_materialize.py
```

ويجب إعطاؤه **40-character commit SHA** محددًا. لا يقبل branch name باعتباره مصدرًا نهائيًا، ولا يعتمد على working tree الحالي كمصدر snapshot.

الهدف الافتراضي `ORION_NEXT_FINAL` خارج `ORION_NEXT`، ويمكن تحديد target خارجي صريح عند بوابة التكامل.

## 7. Safe finalization invariants

قبل أي كتابة:

1. يتم التحقق من أن checkout المصدر هو مستودع ORION_NEXT وأن `origin` يشير إلى GitHub الرسمي.
2. يتم جلب commit المطلوب من `origin` والتحقق من مطابقته حرفيًا.
3. يتم إنشاء archive من commit نفسه، وليس من working tree.
4. يتم إنشاء staging جديد ومعزول.
5. تتم مقارنة manifest الكامل: paths + type + size + SHA-256.
6. لا يُستبدل target الموجود إلا بعد نجاح parity داخل staging.
7. بعد التثبيت تتم parity ثانية على target.
8. عند الفشل يعاد target السابق، ولا يترك staging/backup غير مكتملين.

## 8. Restore semantics

Restore في هذا السياق يعني **materialize snapshot Git محدد**، وليس إعادة إحياء حالة Local قديمة.

لذلك:

```text
GitHub commit → snapshot → isolated target
```

وليس:

```text
Local snapshot → ORION_NEXT
```

## 9. Verification

`tools/orion_main_sync_verify.py` يبقى verifier مستقلًا للـMAIN mirror المعزول.

التحقق النهائي للـmaterialization يستخدم نفس عقد parity داخل `orion_final_materialize.py` ويجب أن ينتهي إلى:

```text
PARITY: EXACT MATCH
RESULT: FINAL MATERIALIZATION SUCCESS
```

لا تُعتبر عملية ناجحة اعتمادًا على عدد الملفات أو commit label فقط.

## 10. الملكية

هذا المسار يملك Synchronization Architecture / Restore / MAIN-ALL isolation / Final Materialization / Parity Safety فقط.

لا يغيّر Core Intelligence أو Execution أو Opportunity أو Score أو Decision أو Reporting business semantics.

أي تغيير جوهري في السياسة يحتاج قرار قيادة موثق.
