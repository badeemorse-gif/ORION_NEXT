# ORION Restore — ALL Branch Synchronization Contract

الإصدار: 2.2
الحالة: MAIN + FAST ISOLATED ALL

## الهدف

أداة ORION Restore تحتوي الآن على مسارين مستقلين:

- `MAIN` = نسخة مطابقة رسميًا لـ `origin/main` داخل المشروع الرئيسي.
- `ALL` = نسخ معزولة لجميع الفروع داخل `ORION_NEXT_ALL_BRANCHES`.

لا يوجد أي تداخل بين المسارين.

## ALL — التصميم المعتمد

تم تثبيت تصميم ALL الحالي بعد نجاح اختبارات المزامنة.

التصميم **لا يستخدم `git worktree` نهائيًا**.

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

## ALL — المزامنة الفعلية

لكل فرع يتم:

- قراءة snapshot الفعلي من GitHub عبر `git archive`.
- مقارنة المحتوى الموجود محليًا مع snapshot الهدف باستخدام SHA-256.
- نقل الملفات الجديدة فعليًا.
- تحديث الملفات التي تغير محتواها فعليًا.
- حذف الملفات التي لم تعد موجودة في الفرع الهدف.
- الإبقاء على الملفات المطابقة دون إعادة كتابتها لتقليل الزمن والـI/O.

وبالتالي فإن كل مجلد فرع يصبح **Exact Mirror** لمحتوى GitHub لذلك الفرع.

## ALL — الحماية والعزل

كل فرع له مجلد مستقل.

لا يجوز أن يكتب فرع في مجلد فرع آخر، ولا أن يكتب ALL فوق:

```text
C:\Users\badee\Desktop\ORION_NEXT
```

## MAIN — official primary project mirror

`MAIN` هو المسار الوحيد المسموح له بالكتابة داخل:

```text
C:\Users\badee\Desktop\ORION_NEXT
```

المصدر:

```text
GitHub / origin/main
```

والنتيجة المطلوبة هي **Exact Mirror**:

> كل مسار موجود في `origin/main` يجب أن يكون موجودًا محليًا بالمحتوى نفسه، وكل مسار غير موجود في `origin/main` يجب ألا يبقى محليًا، باستثناء `.git` لأنه بيانات Git الداخلية الخاصة بالمستودع.

### قواعد MAIN

1. يستخدم `git fetch --prune origin main` دون `checkout` أو تغيير للفرع الحالي.
2. يقرأ snapshot الرسمي بواسطة `git archive origin/main`.
3. يبني manifest فعليًا للمجلد المحلي مع استثناء `.git` فقط.
4. يقارن المحتوى باستخدام SHA-256.
5. ينقل الملفات الجديدة.
6. يحدّث أي ملف تغير محتواه داخل `origin/main`.
7. يحذف أي ملف أو مجلد محلي زائد لا وجود له في snapshot الرسمي لـ `origin/main`.
8. يعالج file/directory collisions كجزء من تحقيق التطابق النهائي.
9. لا يستخدم `clean -fdx` ولا `checkout` ولا `reset --hard` لتحقيق المزامنة.
10. لا يكتب داخل `ALL_ROOT` مطلقًا.
11. بعد materialization يتم تنفيذ verification كامل:
    - لا ملفات ناقصة.
    - لا ملفات زائدة.
    - لا ملفات مختلفة المحتوى.
12. لا يظهر `MAIN SUCCESS` إلا بعد نجاح verification.
13. `BRANCHES` في MAIN = `1`، و`FILES / ADDED / UPDATED / REMOVED` تعرض نتائج MAIN نفسها.

### تحديثات الملفات

عند تغيير محتوى ملف في GitHub/main، يعاد حساب SHA-256 للمصدر والملف المحلي.

إذا اختلفت البصمتان، ينقل MAIN المحتوى الجديد إلى الملف المحلي.

إذا تطابقت البصمتان، لا يعاد نسخ الملف.

### الملفات الزائدة محليًا

MAIN الآن يعمل بمنطق mirror حقيقي وليس بمنطق tracked-files فقط.

لذلك إذا كان هناك مثلًا:

```text
PROJECT_ROOT/
    file_from_main.py
    old_file.py
    local_extra.txt
```

بينما `origin/main` يحتوي فقط على:

```text
file_from_main.py
```

فبعد `Sync MAIN` يجب أن تصبح النتيجة:

```text
PROJECT_ROOT/
    .git/
    file_from_main.py
```

ويتم حذف `old_file.py` و`local_extra.txt` لأنهما ليسا جزءًا من snapshot الرسمي.

### verification النهائي

المقارنة النهائية هي:

```text
LOCAL_MANIFEST (excluding .git)
        ==
ORIGIN_MAIN_ARCHIVE_MANIFEST
```

أي اختلاف، مهما كان سببه أو نوعه، يمنع إعلان النجاح.

## MAIN وALL — الفصل النهائي

```text
MAIN:
GitHub/main → PROJECT_ROOT

ALL:
GitHub/all branches → ALL_ROOT/<branch>
```

القواعد:

- MAIN لا يستخدم `ALL_ROOT`.
- ALL لا يستخدم `PROJECT_ROOT` كوجهة.
- MAIN لا يغير أو يعيد تصميم محرك ALL.
- ALL لا يكتب فوق المشروع الرئيسي.
- لا يوجد `git worktree` في أي من المسارين.

## إحصائيات الشاشة

واجهة الأداة تعرض:

- `BRANCHES`
- `FILES`
- `ADDED`
- `UPDATED`
- `REMOVED`

في MAIN:

```text
BRANCHES = 1
FILES    = عدد ملفات origin/main
ADDED    = الملفات التي أضيفت محليًا
UPDATED  = الملفات التي اختلف محتواها وتم تحديثها
REMOVED  = الملفات الزائدة محليًا التي أزيلت لتحقيق التطابق
```

## الأدوات

التصميم النهائي للأداة:

```text
tools/
    orion_restore_gui.pyw       # محرك ALL المجمد
    orion_restore_main_gui.pyw  # واجهة MAIN + ALL
    orion_restore_gui.vbs       # Windows launcher
```

## النتيجة المعتمدة

`MAIN` =

**Fetch origin/main → Archive snapshot → Compare SHA-256 → Add new files → Update changed files → Remove all extra local paths → Verify exact manifest → SUCCESS**

و`ALL` =

**Discover all branches → Batch Fetch → Archive each branch → Compare SHA-256 → Transfer only required files → Remove obsolete files → Resolve Windows path-type collisions → Show per-branch statistics**.

يظل نجاح ALL baseline محميًا، ويظل MAIN هو المسار الوحيد الذي يجوز له تحديث `PROJECT_ROOT`.