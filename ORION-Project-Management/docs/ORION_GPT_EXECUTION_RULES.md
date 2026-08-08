# ORION — GPT EXECUTION RULES

الإصدار: 3.0
الحالة: ACTIVE
المشروع: ORION
المستودع الرسمي: badeemorse-gif/ORION_NEXT

==================================================
1. الوظيفة
==================================================

هذه الوثيقة هي بوابة التنفيذ الإلزامية لـ GPT داخل مشروع ORION.

وظيفتها ليست تخزين جميع معلومات المشروع.

وظيفتها تحديد:

- كيف يبدأ GPT أي رسالة مرتبطة بالمشروع.
- كيف يحدد الوثائق المطلوبة.
- كيف يحدد حالة المشروع.
- كيف يتعامل مع التعارض.
- كيف يتعامل مع GitHub.
- كيف يتعامل مع التعديلات.
- كيف يتعامل مع المزامنة.
- كيف يحافظ على استمرارية المشروع بين المحادثات.

هذه الوثيقة هي المرجع التشغيلي الأعلى.

==================================================
2. قاعدة الأمر 1
==================================================

إذا كان أول أمر في رسالة المستخدم هو:

1

فالمعنى الإلزامي هو:

نفذ الخطوة التالية من حالة مشروع ORION الحالية.

لا يبدأ GPT مهمة جديدة من التخمين.

يجب عليه:

1. قراءة هذه الوثيقة.
2. قراءة ORION_CONTROL_INDEX.md.
3. قراءة ORION_PROJECT_STATE.md.
4. تحديد المرحلة الحالية.
5. تحديد آخر خطوة معتمدة.
6. تحديد الخطوة التالية.
7. مراجعة الوثائق المرتبطة بالخطوة فقط.
8. تنفيذ الخطوة التالية فقط.

==================================================
3. قاعدة ما قبل كل رد
==================================================

قبل كل رد مرتبط بمشروع ORION يجب:

1. الوصول إلى هذه الوثيقة.
2. قراءتها.
3. قراءة ORION_CONTROL_INDEX.md.
4. قراءة ORION_PROJECT_STATE.md عند الحاجة إلى حالة المشروع.

هذه الخطوة إلزامية.

لا تعتمد على ذاكرة المحادثة بدل الوثائق.

==================================================
4. نظام المراجعة الذكي
==================================================

لا تتم قراءة جميع وثائق المشروع بالكامل في كل رسالة.

بدل ذلك يستخدم GPT ثلاث مستويات للمراجعة:

--------------------------------------------------
المستوى 1 — المراجعة السريعة
--------------------------------------------------

تستخدم في الطلبات العادية.

يتم:

- قراءة قواعد التنفيذ.
- قراءة فهرس التحكم.
- قراءة حالة المشروع.
- تحديد الوثائق المرتبطة مباشرة بالطلب.

--------------------------------------------------
المستوى 2 — المراجعة المستهدفة
--------------------------------------------------

تستخدم عندما يتطلب الطلب قرارًا أو تعديلًا.

يتم:

- قراءة الوثائق المرتبطة مباشرة.
- مراجعة الكود أو الملفات المرتبطة.
- البحث داخل بقية الوثائق عند الحاجة للتأكد من عدم وجود معلومة مؤثرة.

--------------------------------------------------
المستوى 3 — المراجعة الموسعة
--------------------------------------------------

تستخدم فقط عندما:

- يوجد تعارض بين وثيقتين.
- يوجد قرار معماري كبير.
- يوجد تغيير في بنية المشروع.
- توجد معلومة مهمة غير واضحة المصدر.
- يطلب المستخدم مراجعة شاملة.
- تكون حالة المشروع غير قابلة للتحديد من الحالة والفهرس.
- يظهر احتمال وجود تعليمات متعارضة.

عندها تتم مراجعة جميع الوثائق ذات الصلة بالموضوع، وليس بشكل آلي في كل رسالة.

==================================================
5. عدم تجاهل الوثائق
==================================================

عدم قراءة وثيقة في رسالة معينة لا يعني تجاهلها.

جميع الوثائق الرسمية تعتبر مصادر محتملة للمعلومة.

إذا كانت هناك حاجة للتأكد من وجود معلومة داخل وثيقة غير محددة في الفهرس:

يجب البحث فيها.

إذا ظهرت معلومة صحيحة في وثيقة غير الوثيقة المناسبة:

1. يتم اعتمادها أثناء القرار.
2. يتم تحديد مكانها الصحيح.
3. يتم نقلها أو توثيقها في المكان الصحيح عند تحديث الوثائق.

==================================================
6. ترتيب سلطة الوثائق
==================================================

كل وثيقة تملك سلطة على مجال محدد فقط.

1. ORION_GPT_EXECUTION_RULES.md
   قواعد تشغيل GPT.

2. ORION_CONTROL_INDEX.md
   خريطة الوثائق وأدوارها ونطاق استخدامها.

3. ORION_PROJECT_STATE.md
   الحالة الحالية والمرحلة والخطوة التالية.

4. ORION_WORK_PROTOCOL.md
   طريقة العمل داخل المشروع.

5. ORION_PROJECT_CHARTER.md
   تعريف المشروع ونطاقه وأهدافه.

6. ORION_ARCHITECTURE.md
   المعمارية والبنية والمسؤوليات التقنية.

7. ORION_ROADMAP.md
   المراحل وترتيب التطوير وشروط الانتقال.

8. ORION_DECISIONS.md
   القرارات المعتمدة.

9. ORION_CHANGELOG.md
   التاريخ التنفيذي للتغييرات.

10. ORION_KNOWN_PROBLEMS.md
    المشاكل المؤكدة وحالتها.

لا يجوز لوثيقة أن تنشئ قاعدة تشغيلية تناقض وثيقة أعلى منها.

إذا تكرر نفس المبدأ في أكثر من وثيقة، تكون الوثيقة الأعلى في هذا الترتيب هي المرجع.

==================================================
7. قاعدة عدم تكرار القواعد
==================================================

لا يتم إنشاء نفس القاعدة في عدة وثائق كقاعدة مستقلة.

يمكن أن تذكر الوثائق الأخرى القاعدة لأغراض الوصف أو التوثيق.

لكن القاعدة التنفيذية الأصلية يجب أن تكون في مكان واحد.

عند اكتشاف قاعدة مكررة:

- لا يتم إنشاء نسخة ثالثة منها.
- يتم تحديد مصدرها الأساسي.
- يتم إزالة أو تحويل النسخ الأخرى إلى مرجع وصفي عند تحديث الوثائق.

==================================================
8. حالة المشروع
==================================================

ORION_PROJECT_STATE.md هي المرجع المختصر للحالة الحالية.

يجب أن تحتوي على:

- المرحلة الحالية.
- آخر خطوة مكتملة.
- الخطوة الحالية.
- الخطوة التالية.
- حالة المراجعة.
- آخر مجموعة تعديلات معتمدة.
- آخر مزامنة.
- أي توقف أو قرار مؤقت.

لا يتم تخزين التاريخ الكامل للمشروع فيها.

التاريخ الكامل يوجد في CHANGELOG وDECISIONS.

==================================================
9. الوصول إلى GitHub
==================================================

المستودع الرسمي:

badeemorse-gif/ORION_NEXT

الفرع الرئيسي:

main

إذا كان الوصول إلى GitHub متاحًا:

يجب استخدامه للتحقق من:

- الملفات.
- الوثائق.
- بنية المستودع.
- آخر Commit.
- حالة الفرع.
- الملفات المعدلة.
- أي معلومة لازمة للتحقق.

لا يجوز افتراض عدم الوصول.

إذا تعذر الوصول فعليًا:

يجب توضيح ذلك وطلب الوصول اللازم.

==================================================
10. بنية المشروع المحلية
==================================================

الجذر الرسمي:

C:\Users\badee\Desktop\ORION_NEXT

المكونات الرئيسية:

C:\Users\badee\Desktop\ORION_NEXT\binansScanner

C:\Users\badee\Desktop\ORION_NEXT\ORION-Project-Management

C:\Users\badee\Desktop\ORION_NEXT\tools

==================================================
11. وظيفة الجذور
==================================================

binansScanner

هو الجذر البرمجي.

يحتوي على ملفات ومجلدات البرنامج والاختبارات.

ORION-Project-Management

هو جذر إدارة المشروع والتوثيق.

docs

هو المجلد الرسمي للوثائق.

tools

هو مجلد الأدوات التشغيلية.

أداة المزامنة:

tools\orion_sync.bat

==================================================
12. Git
==================================================

المشروع يستخدم مستودع Git رئيسيًا واحدًا.

المسار:

C:\Users\badee\Desktop\ORION_NEXT\.git

لا تعتبر:

binansScanner

أو:

ORION-Project-Management

أو:

tools

مستودعات مستقلة.

==================================================
13. مسار المزامنة
==================================================

المسار الرسمي الوحيد:

LOCAL
↓
GIT
↓
GITHUB

ولا يعتمد المشروع:

GITHUB
↓
LOCAL

كمسار مزامنة تشغيلي.

==================================================
14. المزامنة
==================================================

المزامنة تتم باستخدام:

tools\orion_sync.bat

المزامنة تكون مرة واحدة لكل مجموعة مكتملة من التعديلات.

التسلسل:

1. تعديل الملفات محليًا.
2. حفظ الملفات.
3. اختبار التعديلات.
4. مراجعة المجموعة.
5. اعتماد المجموعة.
6. تشغيل ORION Sync مرة واحدة.
7. Commit.
8. Push.
9. التحقق من GitHub.

لا تتم المزامنة بعد كل تعديل صغير.

==================================================
15. التعديل
==================================================

GPT لا يعتمد على تعديل الملفات مباشرة داخل GitHub كطريقة العمل الطبيعية.

عند تعديل ملف:

GPT يقدم النسخة الكاملة الجديدة.

ثم:

GPT
↓
الملف الكامل
↓
المستخدم يطبقه محليًا
↓
اختبار
↓
مراجعة
↓
اعتماد
↓
ORION Sync
↓
GitHub

==================================================
16. مراجعة الملفات
==================================================

قبل تعديل ملف يجب عند الحاجة مراجعة:

- الملف نفسه.
- الملفات المرتبطة.
- الاعتماديات.
- الاختبارات.
- الطبقة المعمارية.
- الوثائق ذات الصلة.

لا يتم توسيع المراجعة بلا سبب.

==================================================
17. القرارات المعمارية
==================================================

أي تغيير يؤثر على:

- البنية.
- الطبقات.
- المسؤوليات.
- الاعتماديات.
- Pipeline.
- Bootstrap.
- Engines.
- Providers.
- Storage.
- API.
- GUI.
- Scheduler.

يعتبر قرارًا معماريًا.

يجب تسجيله في:

ORION_DECISIONS.md

==================================================
18. سجل التغييرات
==================================================

التغيير المعتمد يسجل في:

ORION_CHANGELOG.md

ولا يستخدم CHANGELOG كبديل عن الحالة الحالية.

==================================================
19. المشاكل
==================================================

المشكلة المؤكدة تسجل في:

ORION_KNOWN_PROBLEMS.md

ولا تعتبر منتهية إلا بدليل على حلها.

==================================================
20. خارطة الطريق
==================================================

ORION_ROADMAP.md تحدد:

- المراحل.
- ترتيبها.
- شروط اكتمالها.
- شروط الانتقال.

لكن الحالة اللحظية للمشروع تحفظ في:

ORION_PROJECT_STATE.md

==================================================
21. الاستمرارية بين المحادثات
==================================================

المحادثة الجديدة لا تعتمد على تاريخ المحادثة السابقة.

الاستمرارية تعتمد على:

ORION_GPT_EXECUTION_RULES.md
↓
ORION_CONTROL_INDEX.md
↓
ORION_PROJECT_STATE.md
↓
الوثائق المرتبطة
↓
المستودع الفعلي

لذلك يجب أن تكون هذه الملفات محدثة دائمًا.

==================================================
22. قاعدة القرار
==================================================

لا يتم اتخاذ قرار بناءً على الذاكرة وحدها.

القرار يعتمد على:

- الحالة الفعلية للمشروع.
- الوثائق.
- الكود عند الحاجة.
- GitHub عند توفر الوصول.
- القرارات المعتمدة.

==================================================
23. قاعدة التعارض
==================================================

إذا ظهر تعارض:

1. لا يتم اختيار أحد الطرفين بالتخمين.
2. يتم تحديد الوثائق المتعارضة.
3. تتم مراجعة السياق.
4. يتم تحديد المصدر الصحيح.
5. يتم تسجيل القرار عند الحاجة.
6. يتم تحديث الوثائق المتأثرة.

==================================================
24. قاعدة الاقتصاد في المراجعة
==================================================

الهدف هو:

أعلى دقة ممكنة
مع
أقل قراءة ضرورية.

لا تتم إعادة قراءة معلومة تم التحقق منها دون سبب.

ولا يتم توسيع نطاق المراجعة إلا إذا تطلب القرار ذلك.

==================================================
25. قاعدة التنفيذ
==================================================

عند وجود أمر واضح:

ينفذ GPT المطلوب مباشرة.

عند وجود أمر 1:

ينفذ GPT الخطوة التالية فقط.

لا يتم تنفيذ خطوات إضافية لمجرد أنها ممكنة.

==================================================
26. قاعدة سلامة المشروع
==================================================

لا يتم:

- حذف وثائق دون قرار.
- تغيير المعمارية دون مراجعة.
- تغيير مسار المزامنة دون قرار.
- إنشاء قواعد متكررة.
- إنشاء أدوات مزامنة بديلة.
- الاعتماد على ذاكرة المحادثة بدل حالة المشروع.

==================================================
27. المرجع النهائي
==================================================

عند الشك:

ابدأ من:

ORION_GPT_EXECUTION_RULES.md

ثم:

ORION_CONTROL_INDEX.md

ثم:

ORION_PROJECT_STATE.md

ثم انتقل فقط إلى الوثائق المطلوبة.

# ORION — GPT Execution Rules

**File:** `ORION_GPT_EXECUTION_RULES.md`
**Project:** ORION_NEXT
**Repository:** `badeemorse-gif/ORION_NEXT`
**Branch:** `main`

---

# 1. Purpose

This document defines the mandatory operating rules for every AI-assisted ORION development session.

The purpose is to ensure that every conversation:

* starts from the official project state;
* follows the approved architecture;
* continues from the actual implementation point;
* does not recreate already completed analysis;
* does not invent project state;
* does not bypass dependencies;
* does not make uncontrolled architectural changes;
* records implementation progress;
* remains synchronized with the official project documentation.

---

# 2. Mandatory Document Order

For every ORION-related request, the assistant must use the following order.

## Step 1

Read:

```text
ORION-Project-Management/docs/ORION_GPT_EXECUTION_RULES.md
```

## Step 2

Read:

```text
ORION-Project-Management/docs/ORION_CONTROL_INDEX.md
```

## Step 3

Use:

```text
ORION-Project-Management/docs/ORION_PROJECT_STATE.md
```

when project state or current phase is required.

## Step 4

Read the documents identified as relevant by the Control Index.

## Step 5

For implementation work, always read:

```text
ORION-Project-Management/docs/ORION_TARGET_ARCHITECTURE_IMPLEMENTATION_BASELINE.md
```

This document is the central implementation baseline.

---

# 3. Implementation Baseline Rule

The document:

```text
ORION_TARGET_ARCHITECTURE_IMPLEMENTATION_BASELINE.md
```

is the authoritative execution roadmap after completion of Architecture Inventory.

Every implementation conversation must use it to determine:

```text
Current Phase
Current Status
Last Completed Step
Current Work
Next Step
```

The assistant must not infer project progress from memory.

The assistant must not assume a phase is complete unless its completion is recorded in the baseline.

---

# 4. Continuity Rule

A new ORION conversation is a continuation of the project, not a new project.

Therefore:

```text
New Conversation
      ↓
Read Rules
      ↓
Read Control Index
      ↓
Read Project State when required
      ↓
Read Implementation Baseline
      ↓
Determine Current Execution Point
      ↓
Continue
```

The assistant must resume from the latest recorded implementation state.

It must not restart architectural analysis unless the documentation indicates that the architecture is unresolved or a real conflict has been discovered.

---

# 5. Command `1`

When the first command in a user message is:

```text
1
```

the assistant must execute the next appropriate step from the current ORION implementation state.

The assistant must:

1. read the mandatory execution documents;
2. determine the current implementation phase;
3. identify the last completed milestone;
4. identify the next pending milestone;
5. inspect the relevant repository files;
6. perform only the next authorized implementation step;
7. verify the result;
8. report the outcome;
9. update the implementation state when appropriate.

The assistant must not interpret `1` as permission to skip architectural dependencies.

---

# 6. Target Architecture Rule

The approved target architecture is defined by:

```text
ORION_TARGET_ARCHITECTURE_IMPLEMENTATION_BASELINE.md
```

The assistant must treat that architecture as the implementation target.

A local code pattern that contradicts the baseline is not automatically authoritative.

The assistant must prefer the approved contract over an existing legacy implementation.

---

# 7. Dependency-First Rule

Implementation must proceed in dependency order.

The canonical order is:

```text
Contracts
    ↓
Domain Models
    ↓
Market Foundation
    ↓
Validation
    ↓
Indicators
    ↓
Analysis
    ↓
Profile
    ↓
Score
    ↓
Decision
    ↓
Execution
    ↓
Report
    ↓
Core
    ↓
Application
    ↓
Interfaces
    ↓
Integration
```

A later layer must not be used to hide an unresolved foundational contract.

---

# 8. No Patch Cascade Rule

The assistant must not solve architecture problems through an uncontrolled sequence of local patches.

If fixing one component creates a contract mismatch in another component, the assistant must stop and identify the underlying contract problem.

Preferred sequence:

```text
Identify Contract
      ↓
Correct Contract
      ↓
Migrate Consumers
      ↓
Test
      ↓
Continue
```

not:

```text
Patch A
Patch B
Patch C
Patch D
Patch E
```

without resolving the common cause.

---

# 9. Canonical Contract Rule

Every major domain concept must have one canonical contract.

This includes:

```text
MarketDataset
TimeframeData
AnalysisResult
ProfileResult
ScoreResult
DecisionResult
ExecutionPlan
ExecutionResult
ReportResult
```

Duplicate definitions must not be introduced.

If duplicates already exist, they must be classified as:

```text
Canonical
Migration Target
Legacy
```

and consolidated through controlled migration.

---

# 10. Engine Rule

The assistant must not assume that every engine has the same input/output shape.

The system contains different contracts:

```text
MarketDataset
      ↓
AnalysisResult
      ↓
ScoreResult
      ↓
DecisionResult
      ↓
ExecutionResult
      ↓
ReportResult
```

Therefore a universal:

```text
.execute()
```

abstraction must not be imposed merely for convenience if it destroys the real domain contracts.

---

# 11. Layer Boundary Rule

Each layer must remain within its responsibility.

## Provider

Market data acquisition.

## Mapper

External-to-internal transformation.

## Repository

Persistence abstraction.

## Validation

Validity and preconditions.

## Indicators

Indicator calculation.

## Analysis

Market interpretation.

## Profile

Market profile characterization.

## Score

Scoring.

## Decision

Decision logic.

## Execution

Execution planning and execution.

## Report

Presentation/export of results.

## Application

Use-case coordination.

## API

HTTP/interface boundary.

## GUI

Presentation boundary.

## Scheduler

Timing and scheduling.

---

# 12. No Cross-Layer Leakage

The following are prohibited:

```text
API
→ Binance directly
```

```text
GUI
→ Decision rules directly
```

```text
Decision
→ Binance directly
```

```text
Execution
→ Orchestrator internals
```

```text
Report
→ Recalculate analysis
```

```text
Scheduler
→ Own complete analysis pipeline
```

---

# 13. MarketDataset Rule

`MarketDataset` is market data.

It must not become a generic mutable bag containing every pipeline result.

Do not add:

```text
score
decision
report
execution
```

to `MarketDataset` merely because doing so is convenient.

Results must use their own contracts.

---

# 14. State Ownership Rule

Every piece of state must have one clear owner.

Before introducing state, the assistant must answer:

```text
Who owns it?
Who mutates it?
Who reads it?
When is it valid?
When is it cleared?
```

Implicit shared state is prohibited unless explicitly justified.

---

# 15. Duplicate Implementation Rule

When two files appear to implement the same responsibility:

1. inspect both;
2. identify all consumers;
3. identify which contract matches the target architecture;
4. select the canonical implementation;
5. migrate consumers;
6. test;
7. retire the duplicate.

Do not delete a duplicate merely because its filename appears old.

---

# 16. Legacy Rule

Existing code is not automatically correct.

Existing code is also not automatically disposable.

Every existing component must be classified as:

```text
KEEP
REBUILD
MERGE
MIGRATE
LEGACY
REMOVE
```

The classification must be based on:

* target architecture;
* current consumers;
* contract compatibility;
* tests;
* actual responsibility.

---

# 17. Repository Inspection Rule

When GitHub access is available, the assistant must use it to verify repository state and relevant files.

The assistant must not assume that a file exists, has a particular implementation, or has a particular version without verification.

The local project remains the authoritative implementation path.

---

# 18. Local → Git → GitHub Rule

The official project synchronization path is:

```text
Local
  ↓
Git
  ↓
GitHub
```

Do not use:

```text
GitHub
  ↓
Local
```

as a project synchronization mechanism.

GitHub may be inspected for verification, but it is not the source used to overwrite local project state.

---

# 19. File Modification Rule

The assistant must not directly modify repository files when following the ORION project workflow.

When a file must change, the assistant must provide the complete intended file content for local application.

The user applies the change locally.

After a complete approved group of changes:

```text
Local
  ↓
Git
  ↓
GitHub
```

is performed once.

---

# 20. Synchronization Rule

Do not synchronize after every small edit.

A synchronization point should occur after a coherent implementation group has been:

```text
implemented
+
tested
+
reviewed
+
approved
```

This prevents Git history from becoming a sequence of unstable intermediate states.

---

# 21. Testing Rule

A code change is not considered complete because the file was successfully edited.

Completion requires appropriate verification.

Depending on the change, this may include:

```text
Unit Test
Contract Test
Integration Test
Pipeline Test
Application Test
Regression Test
E2E Test
```

The appropriate level must be selected based on the affected boundary.

---

# 22. Completion Rule

A phase may be marked:

```text
COMPLETED
```

only when:

```text
Implementation
+
Tests
+
Verification
+
Review
```

are complete.

The implementation baseline must then be updated.

---

# 23. Baseline Update Rule

After each meaningful implementation milestone, update:

```text
ORION_TARGET_ARCHITECTURE_IMPLEMENTATION_BASELINE.md
```

at minimum:

```text
Phase Status
Last Completed Step
Current Work
Next Step
```

If a decision changes architecture, also update the appropriate decision record.

---

# 24. Reopening Rule

A completed phase may be reopened only when a real issue justifies it.

Examples:

```text
Contract conflict
Regression
Invalid assumption
Architectural contradiction
Downstream incompatibility
Critical test failure
```

When reopening:

```text
Reason
Affected Phase
Affected Contract
Required Correction
```

must be recorded.

---

# 25. Architecture Decision Rule

Any significant architectural change must be recorded in the official architecture decision documentation.

Do not silently change the target architecture inside code.

The documentation must remain synchronized with the implementation.

---

# 26. Documentation Rule

Documentation is part of implementation.

When behavior, architecture, contracts, or execution state changes materially, the relevant documentation must be updated.

Documentation must not describe an architecture that the code no longer follows.

---

# 27. Error Handling Rule

When an error reveals a deeper contract problem, fix the contract rather than masking the error.

Do not introduce:

```text
try/except
```

or fallback behavior merely to conceal an architectural mismatch.

Errors that reveal real design problems must be surfaced and resolved.

---

# 28. No Speculative Feature Rule

Do not introduce functionality that is not required by:

* the approved architecture;
* the implementation baseline;
* an explicit project requirement;
* a documented architecture decision.

The current objective is architectural coherence and executable stability before fine-grained feature expansion.

---

# 29. No Premature Interface Rule

Do not prioritize:

```text
GUI
API polish
Scheduler features
```

over unresolved Core contracts.

Interfaces are downstream consumers.

Core stability takes precedence.

---

# 30. No Premature Optimization Rule

Do not optimize implementation details before:

```text
Contracts
Architecture
Correctness
Tests
```

are stable.

Correctness and architectural consistency come first.

---

# 31. Conversation Continuity Rule

Every new ORION conversation must behave as if it is opening an ongoing engineering session.

The assistant must establish:

```text
Where are we?
What is already approved?
What is complete?
What is currently being implemented?
What is the next exact action?
```

from the official documents.

The assistant must not rely on conversational memory as the authoritative project state.

---

# 32. Conflict Resolution

If the following sources conflict:

```text
Existing Code
Documentation
Implementation Baseline
Architecture Decision
Project State
```

the assistant must not silently choose one.

The conflict must be identified.

The relevant official documents must be checked.

If the conflict requires an architectural decision, execution pauses until the decision is recorded.

---

# 33. Execution Output Rule

When executing a project step, the assistant should clearly report:

```text
Current Phase
Current Objective
Files Affected
Changes Required
Tests
Verification
Result
Next Step
```

This keeps the conversation auditable.

---

# 34. No False Completion Rule

The assistant must never claim:

```text
Implemented
Completed
Verified
Passed
Synchronized
```

unless that state has actually been established.

In particular:

```text
Proposed
```

must not be presented as:

```text
Implemented
```

and:

```text
Implemented
```

must not be presented as:

```text
Verified
```

---

# 35. Current Baseline

The current implementation baseline is:

```text
ORION_TARGET_ARCHITECTURE_IMPLEMENTATION_BASELINE.md
```

Current recorded state:

```text
Architecture Review
    = COMPLETED

Contracts
    = READY

Next Execution Step
    = Canonical Domain Contracts
```

---

# 36. Mandatory First Action for Implementation

Before changing any implementation file:

```text
Read Rules
    ↓
Read Control Index
    ↓
Read Project State when required
    ↓
Read Implementation Baseline
    ↓
Inspect relevant repository files
    ↓
Confirm current phase
    ↓
Implement only the next approved step
```

---

# 37. Final Principle

The ORION project must evolve as one coherent system.

The objective is not:

```text
make each file work
```

The objective is:

```text
make the entire architecture work together
```

Therefore:

```text
Contract
    ↓
Implementation
    ↓
Integration
    ↓
Verification
    ↓
Documented State
    ↓
Next Step
```

is the permanent execution cycle.

---

# 38. Mandatory Reference

For every implementation session after Architecture Inventory, the assistant must use:

```text
ORION_TARGET_ARCHITECTURE_IMPLEMENTATION_BASELINE.md
```

as the central execution reference.

The assistant must continue from the state recorded there.

No new conversation may implicitly reset the implementation position.

No implementation may bypass the recorded dependency order without a documented architectural reason.

==================================================
END
==================================================