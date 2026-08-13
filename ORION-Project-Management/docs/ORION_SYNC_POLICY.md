# ORION — Sync & Final Materialization Policy

الإصدار: 1.0
الحالة: ACTIVE

## 1. مصدر الحقيقة

أثناء التطوير:

```text
GitHub = Source of Truth
```

المطورون داخل ChatGPT يعملون على فروع GitHub ويكملون حزمًا كاملة داخل نطاقاتهم.

لا تستخدم GITHUB → LOCAL كمزامنة يومية بعد كل تعديل صغير.

## 2. بيئة ORION_NEXT المحلية

```text
C:\Users\badee\Desktop\ORION_NEXT
```

هذه هي بيئة Development / Integration المحلية.

لا تعتبر وجهة لمرايا MAIN/ALL أثناء التطوير، ولا يجوز لأي Mirror مرجعي أن يكتب فوقها.

## 3. نموذج تطوير المطورين

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

لا يحتاج المطور إلى مزامنة Local أو الرد بعد كل ملف.

إذا احتاج إلى blocker حقيقي خارج نطاقه، يتوقف ويبلغ القيادة.

## 4. الاختبارات

يمكن للمطور كتابة Contract Tests وملفات الاختبار مع الحزمة.

لكن مطور ChatGPT لا يدعي تنفيذ اختبار محلي لم ينفذه فعليًا.

Full local verification وE2E تؤجل إلى Integration Gate أو بوابة تتطلب تشغيلًا محليًا فعليًا.

## 5. MAIN وALL

`ORION_NEXT_MAIN` و`ORION_NEXT_ALL_BRANCHES` هما مرايا مرجعية معزولة.

لا تستخدمهما كـDevelopment Working Trees، ولا تشغّل اختبارات المشروع النهائي منهما.

## 6. المزامنة القديمة

`tools/orion_sync.bat` وأي Workflow آلي يعتمد على GITHUB → LOCAL بعد كل تعديل صغير يعتبر:

```text
LEGACY / FROZEN
```

ولا يجوز استخدامه كمسار التطوير الجديد.

## 7. Final Materialization

عند اكتمال الحزم وقرار التكامل فقط:

```text
GitHub Integrated State
↓
Clean Final Materialization
↓
Local ORION_NEXT
↓
Full Verification / E2E / Parity
```

يجب أن تكون النسخة المحلية النهائية مبنية من branch/commit محدد ونسخة نظيفة.

## 8. السلامة

لا توجد أداة Mirror تملك صلاحية الكتابة في Development Working Tree.

لا توجد عمليات مزامنة يومية destructive داخل `ORION_NEXT`.

أي تغيير جوهري في سياسة المزامنة يحتاج قرار قيادة موثق.
