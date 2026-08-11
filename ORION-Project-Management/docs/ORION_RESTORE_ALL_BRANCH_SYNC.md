# ORION Restore — ALL Branch Synchronization Contract

الإصدار: 1.1
الحالة: IMPLEMENTED — HARDENED

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
2. يعرض بدء المزامنة لكل فرع قبل تنفيذ أوامر Git الخاصة به.
3. يجلب جميع الفروع دفعة واحدة عبر `git fetch --prune origin` بدل تنفيذ `fetch` شبكة مستقل لكل فرع؛ الهدف تقليل زمن المزامنة ومنع الانتظار المتكرر.
4. ينشئ worktree مستقلًا للفرع إذا لم يكن موجودًا.
5. إذا كان worktree موجودًا ومسجلًا لدى Git، يعاد ضبطه إلى `origin/<branch>` ثم ينظف حالته.
6. يتم تنظيف tracked/untracked/ignored state داخل worktree الخاص بالفرع فقط.
7. يتم تحديث submodules داخل worktree الخاص بالفرع فقط.
8. يتم التحقق من:
   - تطابق `HEAD` مع `origin/<branch>`.
   - عدم وجود tracked differences.
   - عدم وجود untracked/ignored leftovers.
9. يتم تسجيل آخر commit لكل فرع في حالة المزامنة المحلية.
10. يبقى `C:\Users\badee\Desktop\ORION_NEXT` كما هو أثناء `ALL` ولا يتم تحويله من فرع إلى آخر.

## حماية من التعليق

كل أمر Git في أداة ALL يعمل بحد زمني قدره **180 ثانية**. إذا علق أمر Git أو انقطع ولم يعد، يتم إنهاؤه بدل إبقاء الواجهة معلقة إلى أجل غير محدد.

في Windows يتم أيضًا محاولة إنهاء شجرة العملية المرتبطة بالأمر عند انتهاء المهلة.

هذا لا يفرض تأخيرًا على العمليات الناجحة: المهلة هي **حد أمان أقصى** وليست انتظارًا إضافيًا؛ الأوامر الطبيعية تنتهي فور اكتمالها.

## حماية الملفات المحلية

إذا وجد البرنامج مجلدًا يحمل اسم worktree المتوقع لكنه **ليس worktree مسجلًا لدى Git**، تتوقف عملية `ALL` ولا تحذف المجلد؛ وذلك لمنع فقد أي ملفات محلية غير معروفة.

كما أن أسماء worktrees المشتقة من أسماء الفروع تُعالج بطريقة آمنة لنظام Windows مع hash قصير عند الحاجة لمنع تصادم أسماء فرعين مختلفين.

## الوضع الفردي

اختيار فرع محدد لا يتغير سلوكه بسبب إضافة ALL؛ يظل يستخدم Exact Restore على `PROJECT_ROOT` كما كان.

## النتيجة المعتمدة

`ALL` = **Discover + Batch Fetch + Isolated Worktree Restore + Exact Verification لكل فرع**.

ولا يعني `ALL` دمج الفروع أو نسخها فوق مجلد واحد.

## مبدأ الاعتماد

لا نعلن نجاح ALL إلا بعد ظهور `EXACT MATCH` لكل فرع من الفروع المكتشفة. إذا فشل فرع واحد، تتوقف العملية وتظهر المشكلة بوضوح بدل إعلان نجاح جزئي.
