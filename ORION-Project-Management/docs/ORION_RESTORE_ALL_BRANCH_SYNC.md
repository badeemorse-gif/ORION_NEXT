# ORION Restore — ALL Branch Synchronization Contract

الإصدار: 2.0
الحالة: REBUILT — FAST ALL-ONLY SYNCHRONIZER

## الهدف

خيار `ALL` هو الوظيفة الوحيدة في أداة ORION Restore.

يقوم البرنامج باكتشاف **جميع الفروع الموجودة فعليًا على GitHub** ثم مزامنة محتوى كل فرع إلى مجلد مستقل محليًا، مع منع اختلاط محتويات الفروع.

## التصميم المعتمد

تمت إعادة بناء `tools` من الصفر لأن تصميم Worktree السابق كان يسبب توقف ALL أثناء materialization.

التصميم الجديد **لا يستخدم `git worktree` نهائيًا**.

بدلًا من ذلك:

1. `git fetch --prune origin +refs/heads/*:refs/remotes/origin/*` يتم مرة واحدة لجلب جميع الفروع.
2. لكل فرع يتم استخدام `git archive origin/<branch>` لاستخراج snapshot كامل للفرع.
3. يتم وضع المحتوى مباشرة داخل مجلد مستقل للفرع تحت:

```text
C:\Users\badee\Desktop\ORION_NEXT_ALL_BRANCHES\
    main\
    future__opportunity-evaluation-contract__...
    phase2__core-intelligence-hardening__...
    ops__...
```

4. لا يتم تبديل `PROJECT_ROOT` إلى أي فرع أثناء ALL.
5. لا يتم تنفيذ `reset --hard` أو `clean -fdx` أو `worktree add` داخل المشروع الرئيسي.

## المزامنة الفعلية

ALL ليست عملية استكشاف أو فحص فقط.

لكل فرع يتم:

- قراءة snapshot الفعلي من GitHub عبر `git archive`.
- مقارنة المحتوى الموجود محليًا مع snapshot الهدف باستخدام SHA-256.
- نقل الملفات الجديدة فعليًا.
- تحديث الملفات التي تغير محتواها فعليًا.
- حذف الملفات التي لم تعد موجودة في الفرع الهدف.
- الإبقاء على الملفات المطابقة دون إعادة كتابتها لتقليل الزمن والـI/O.

وبالتالي فإن كل مجلد فرع يصبح **Exact Mirror** لمحتوى GitHub لذلك الفرع.

## لماذا هذا أسرع وأكثر ثباتًا؟

التصميم السابق كان يعتمد على إنشاء Worktree ثم `reset` و`checkout` و`clean` وsubmodules، وكان يمكن أن يتوقف عند أول فرع.

التصميم الجديد لا يعتمد على Worktree ولا على حالة Git الداخلية لكل مجلد فرع.

`git fetch` يتم مرة واحدة فقط، وبعد ذلك القراءة من الـremote refs المحلية تتم محليًا.

هذا يلغي:

- انتظار إنشاء 19 Worktree.
- مشاكل sparse-checkout القديمة.
- تعارضات Worktree registration.
- تبديل الفرع الرئيسي أثناء ALL.
- إعادة كتابة الملفات المطابقة بلا داعٍ.

## إحصائيات الشاشة

واجهة ALL أصبحت مركزة فقط على ما يحتاجه المستخدم:

- `BRANCHES` — عدد الفروع المكتشفة.
- `FILES` — عدد ملفات snapshot الموجودة لكل الفروع.
- `ADDED` — عدد الملفات التي نُقلت فعليًا لأول مرة.
- `UPDATED` — عدد الملفات التي تغيرت ونُقلت نسختها الجديدة.
- `REMOVED` — عدد الملفات التي حُذفت من نسخة الفرع المحلي لأنها لم تعد موجودة في GitHub.

كما يظهر في سجل العملية سطر مستقل لكل فرع:

```text
[1/19] main
    ✓ Files: 478 | Added: 478 | Updated: 0 | Removed: 0

[2/19] future/...
    ✓ Files: 482 | Added: 12 | Updated: 7 | Removed: 3
```

وهذا يجعل واضحًا **ماذا نُقل من كل فرع** بدل عرض سجل Git طويل وغير مفيد للمستخدم.

## العزل

كل فرع له مجلد مستقل.

لا يجوز أن يكتب فرع في مجلد فرع آخر، ولا أن يكتب ALL فوق:

```text
C:\Users\badee\Desktop\ORION_NEXT
```

المجلد الرئيسي يبقى كما هو.

## أسماء الفروع

يتم تحويل `/` والأحرف غير الآمنة في Windows إلى `__`، مع إضافة hash قصير عند الحاجة حتى لا يحدث تصادم بين أسماء فروع مختلفة.

## الحماية من التعليق

كل أمر Git له timeout واضح.

إذا توقف `git fetch` أو `git archive` بدل الاستمرار إلى أجل غير محدد، يتم إنهاء العملية وإظهار الخطأ في الواجهة.

الـtimeout هو حد أمان فقط؛ لا توجد فترة انتظار مصطنعة للأوامر الناجحة.

## الأدوات

تم تنظيف `tools` وإعادة بنائها بحيث تبقى أداة ALL فقط:

```text
tools/
    orion_restore_gui.pyw
    orion_restore_gui.vbs
```

`orion_restore_gui.vbs` هو launcher آمن لـWindows ويشغل الواجهة الجديدة مباشرة.

## النتيجة المعتمدة

`ALL` =

**Discover all branches → Batch Fetch → Archive each branch → Compare SHA-256 → Transfer only required files → Remove obsolete files → Show per-branch statistics.**

ولا يعلن البرنامج نجاح المزامنة إلا بعد اكتمال materialization الفعلي لكل الفروع المكتشفة.
