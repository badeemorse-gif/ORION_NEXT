# ORION Restore — MAIN + ALL Synchronization Contract

الإصدار: 2.4
الحالة: MAIN + FAST ISOLATED ALL + INDEPENDENT MAIN PARITY VERIFIER + MAIN DEVELOPMENT ISOLATION

## الهدف

أداة ORION Restore تحتوي على مسارين مستقلين:

- `MAIN` = exact mirror لمحتوى `origin/main` داخل مجلد MAIN مستقل.
- `ALL` = exact mirrors لجميع الفروع داخل `ORION_NEXT_ALL_BRANCHES`.

لا يجوز لأي مسار أن يكتب فوق Working Tree الخاص بالتطوير.

## MAIN — exact isolated mirror

المصدر:

```text
GitHub / origin/main
```

مصدر Git هو مستودع المشروع الرئيسي:

```text
PROJECT_ROOT
```

لكن `PROJECT_ROOT` **مصدر قراءة فقط بالنسبة إلى MAIN materialization**.

وجهة MAIN الرسمية هي:

```text
C:\Users\badee\Desktop\ORION_NEXT_MAIN
```

أو ما يعادلها ديناميكيًا:

```text
Path(PROJECT_ROOT).parent / "ORION_NEXT_MAIN"
```

### القاعدة الحاكمة

> MAIN يجب أن يكون نسخة مطابقة 100% لـ `origin/main`، لكن عملية MAIN ممنوعة من تعديل أو حذف أو استبدال أي ملف داخل `PROJECT_ROOT`.

وبالتالي لا توجد مفاضلة بين الدقة والأمان:

```text
origin/main
     ↓
Git archive snapshot
     ↓
ORION_NEXT_MAIN
     ↓
Exact parity verification
```

بينما:

```text
PROJECT_ROOT
     ↑
Git source / development checkout
     │
     └── لا يتم تنظيفه أو materialize داخله بواسطة MAIN
```

## MAIN — قواعد التنفيذ

1. `git fetch --prune origin main` من `PROJECT_ROOT` دون checkout أو تغيير الفرع الحالي.
2. `git archive origin/main` لبناء snapshot رسمي.
3. حساب manifest للمجلد `ORION_NEXT_MAIN`.
4. مقارنة المسارات والمحتوى باستخدام SHA-256.
5. إضافة Missing.
6. تحديث Different.
7. حذف Extra داخل `ORION_NEXT_MAIN` فقط.
8. معالجة file/directory/symlink collisions داخل وجهة MAIN فقط.
9. التحقق النهائي قبل إعلان النجاح.
10. أي محاولة لتوجيه MAIN إلى `PROJECT_ROOT` تُرفض صراحة.

لا يظهر `MAIN SUCCESS` إلا عند:

```text
MAIN_LOCAL_MANIFEST
        ==
ORIGIN_MAIN_ARCHIVE_MANIFEST
```

## Independent parity verification

الأداة:

```text
tools/orion_main_sync_verify.py
```

Read-only، وتتحقق من:

```text
Fresh fetch
    ↓
origin/main commit
    ↓
git archive
    ↓
Expected manifest
    ↓
ORION_NEXT_MAIN manifest
    ↓
Missing / Extra / Different
    ↓
EXACT MATCH / FAILED
```

ولا تدخل `PROJECT_ROOT` ضمن الـwritable MAIN mirror.

## MAIN — حماية التطوير

هذه الحماية Contract وليست سلوكًا اختياريًا.

إذا كان المطور يعمل على:

```text
modified files
untracked files
test files
local experiments
```

فـMAIN Sync لا يلمسها إطلاقًا لأنها موجودة خارج `ORION_NEXT_MAIN`.

هذا يحل تعارض المزامنة مع الاختبارات دون إضعاف مفهوم Exact Mirror.

## ALL — التصميم المعتمد

`ALL` يبقى مسارًا مستقلًا ولا يتغير بسبب إصلاح MAIN.

يتم:

1. `git fetch --prune origin +refs/heads/*:refs/remotes/origin/*` مرة واحدة.
2. `git archive origin/<branch>` لكل فرع.
3. materialization داخل:

```text
ORION_NEXT_ALL_BRANCHES/<safe-branch-name>
```

4. لا يتم تبديل `PROJECT_ROOT`.
5. لا يتم استخدام `reset --hard` أو `clean -fdx` أو `git worktree` داخل المشروع الرئيسي.
6. كل مجلد فرع هو exact mirror لمحتوى ذلك الفرع.

## الفصل النهائي

```text
MAIN:
origin/main → ORION_NEXT_MAIN

ALL:
origin/<all branches> → ORION_NEXT_ALL_BRANCHES/<branch>

DEVELOPMENT:
PROJECT_ROOT
```

والقواعد:

- MAIN لا يكتب `PROJECT_ROOT`.
- ALL لا يكتب `PROJECT_ROOT` كوجهة.
- MAIN لا يكتب `ALL_ROOT`.
- ALL لا يكتب `MAIN_ROOT`.
- إصلاح MAIN لا يغير محرك ALL.
- التطوير والاختبارات تبقى داخل `PROJECT_ROOT` دون تدخل من أدوات materialization.

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
FILES    = ملفات origin/main
ADDED    = الملفات المضافة إلى MAIN mirror
UPDATED  = الملفات التي تغير محتواها
REMOVED  = الملفات الزائدة المحذوفة من MAIN mirror
```

## أدوات MAIN + ALL

```text
tools/
    orion_restore_gui.pyw       # محرك ALL المجمد
    orion_restore_main_gui.pyw  # واجهة MAIN + ALL
    orion_main_sync_verify.py   # مستقل: exact MAIN parity verification
    orion_restore_gui.vbs       # Windows launcher
```

## النتيجة المعتمدة

`MAIN` =

**Fetch origin/main → Archive snapshot → Materialize فقط داخل ORION_NEXT_MAIN → Remove Extra → Update Different → Add Missing → Verify exact parity → SUCCESS**

`ALL` =

**Discover branches → Batch Fetch → Archive each branch → Materialize داخل ALL_ROOT/<branch> → Compare SHA-256 → Reconcile Missing/Extra/Different → Verify → Statistics**.

**ممنوع العودة إلى التصميم القديم الذي كان يجعل MAIN يكتب مباشرة داخل `PROJECT_ROOT`.**
