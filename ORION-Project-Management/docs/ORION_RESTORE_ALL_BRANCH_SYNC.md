# ORION Restore — ALL Branch Synchronization Contract

الإصدار: 1.0
الحالة: IMPLEMENTED — OPERATIONAL TOOLING

## الهدف

خيار `ALL` في ORION Restore يعني **مزامنة جميع الفروع الموجودة فعليًا على GitHub** في عملية واحدة.

## القاعدة الأساسية

لا يجوز دمج ملفات فرع داخل ملفات فرع آخر، ولا يجوز تبديل الـworking tree الرئيسي بين الفروع أثناء عملية `ALL`.

لذلك تستخدم `ALL` Git worktrees مستقلة:

```text
C:\Users\badee\Desktop\ORION_NEXT

C:\Users\badee\Desktop\ORION_NEXT_ALL_BRANCHES\
    main
    orion-canonical-pipeline-boundary
    phase2__core-intelligence-hardening
    future__...
    ops__...
```

كل worktree يمثل snapshot مستقلًا للفرع المقابل.

## سلوك ALL

1. يكتشف الفروع الحالية مباشرة من GitHub باستخدام `git ls-remote --heads`.
2. يجلب كل فرع إلى `origin/<branch>`.
3. ينشئ worktree مستقلًا للفرع إذا لم يكن موجودًا.
4. إذا كان worktree موجودًا ومسجلًا لدى Git، يعاد ضبطه إلى `origin/<branch>`.
5. يتم تنظيف tracked/untracked/ignored state داخل worktree الخاص بالفرع فقط.
6. يتم تحديث submodules داخل worktree الخاص بالفرع فقط.
7. يتم التحقق من:
   - تطابق `HEAD` مع `origin/<branch>`.
   - عدم وجود tracked differences.
   - عدم وجود untracked/ignored leftovers.
8. يتم تسجيل آخر commit لكل فرع في حالة المزامنة المحلية.
9. يبقى `C:\Users\badee\Desktop\ORION_NEXT` كما هو أثناء `ALL` ولا يتم تحويله من فرع إلى آخر.

## حماية الملفات المحلية

إذا وجد البرنامج مجلدًا يحمل اسم worktree المتوقع لكنه **ليس worktree مسجلًا لدى Git**، تتوقف عملية `ALL` ولا تحذف المجلد؛ وذلك لمنع فقد أي ملفات محلية غير معروفة.

## الوضع الفردي

اختيار فرع محدد لا يتغير سلوكه بسبب هذه الإضافة؛ يظل يستخدم Exact Restore على `PROJECT_ROOT` كما كان.

## النتيجة المعتمدة

`ALL` = **Fetch + Isolated Worktree Restore + Exact Verification لكل فرع**.

ولا يعني `ALL` دمج الفروع أو نسخها فوق مجلد واحد.
