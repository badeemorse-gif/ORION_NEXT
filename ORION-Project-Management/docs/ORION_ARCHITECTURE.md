# ORION — المعمارية الرسمية

الإصدار: 2.1
الحالة: ACTIVE
المشروع: ORION
المستودع: badeemorse-gif/ORION_NEXT

==================================================
1. وظيفة الوثيقة
==================================================

هذه الوثيقة هي المرجع الرسمي للمعمارية الحالية المعتمدة.

تحدد:

- الطبقات.
- حدود المسؤوليات.
- اتجاه الاعتماديات.
- العقود الرئيسية.
- تدفق البيانات.
- المسارات التنفيذية القانونية.
- سياسة Legacy والازدواجية.

لا تحدد المرحلة الحالية أو ترتيب المراحل؛ لذلك يرجع إلى:

ORION_PROJECT_STATE.md
ORION_ROADMAP.md

==================================================
2. المبدأ المعماري
==================================================

ORION نظام متعدد الطبقات، وكل طبقة تمتلك مسؤولية محددة.

المسار الأساسي:

External Market Source
↓
Provider
↓
Mapper
↓
MarketDataProvider
↓
MarketDataset
↓
Validation
↓
Indicators
↓
Analysis / Profile
↓
Score
↓
Decision
↓
ExecutionPlan
↓
Execution
↓
ReportResult
↓
Renderers / Exporter

وتتصل واجهات التشغيل عبر:

API / GUI / Scheduler
↓
Application
↓
Pipeline / Orchestrator
↓
Core / Engines

==================================================
3. قواعد الاعتماديات
==================================================

الاعتماديات تتجه نحو العقود المستقرة.

يمنع:

- اعتماد Engines على Binance مباشرة.
- اعتماد Domain على GUI أو API.
- وضع Business Logic داخل GUI أو Router.
- جعل Orchestrator مستودعًا لقواعد الأعمال.
- جعل MarketDataset مخزنًا دائمًا لنتائج المراحل الأخرى.
- إعادة إدخال Legacy path إلى المسار القانوني دون Decision.

==================================================
4. Market Data Boundary
==================================================

المسار القانوني:

External Provider
↓
Client
↓
Mapper
↓
Provider
↓
MarketDataProvider
↓
MarketDataset

تفاصيل Binance تبقى محصورة في Provider Layer.

==================================================
5. MarketDataset وTimeframe Data
==================================================

MarketDataset يمثل بيانات السوق وmetadata الشرعية الخاصة بها فقط.

لا يحمل بصورة دائمة:

- Profile.
- Score.
- Decision.
- Execution.
- Report.

البيانات الزمنية تستخدم contract موحدًا، ويظل `dataframe` هو الاسم القانوني للبيانات الجدولية حيث ينطبق ذلك.

==================================================
6. Result Contracts
==================================================

العقود الرئيسية الحالية:

AnalysisResult
ProfileResult
ScoreResult
DecisionResult
ExecutionPlan
ExecutionResult
ReportResult

كل مرحلة تنتج نتيجة مستقلة.

لا يتم إخفاء نتيجة مرحلة داخل Domain Model غير مخصص لها.

==================================================
7. Intelligence Layer
==================================================

### Indicators

مسؤول عن حساب المؤشرات من MarketDataset وفق contract مركزي.

### Analysis

MarketDataset
↓
AnalysisEngine
↓
AnalysisResult

Analysis لا يملك Execution أو Reporting أو Orchestration.

### Profile

MarketDataset + Indicator Context
↓
ProfileEngine / ProfileBuilder
↓
ProfileResult

ProfileResult يمثل Market Context مستقلًا في Core Intelligence الحالي.

### Score

AnalysisResult
↓
ScoreEngine
↓
ScoreResult

### Decision

AnalysisResult + ScoreResult + ProfileResult عندما يتطلب القرار ذلك
↓
DecisionEngine
↓
DecisionResult

Decision يقرر ما يجب فعله، ولا ينفذ الصفقة بنفسه.

==================================================
8. Execution Boundary
==================================================

المسار الحالي:

DecisionResult
↓
ExecutionPlanBuilder
↓
ExecutionPlan
↓
Execution
↓
ExecutionResult

`ExecutionPlanBuilder` هو المسؤول عن mapping بين القرار وخطة التنفيذ.

Orchestrator ينسق ولا يمتلك mapping logic الخاص بـExecutionPlan.

التكامل مع Broker/Exchange وRisk/Order Management المتقدم يظل ضمن مرحلة Trading Bot المستقبلية ولا يعاد هندسته مبكرًا دون حاجة.

==================================================
9. Report Boundary — Canonical
==================================================

المسار القانوني الحالي:

AnalysisResult
+
ProfileResult
+
ScoreResult
+
DecisionResult
+
ExecutionResult
↓
ReportResult
↓
JsonReportRenderer / HtmlReportRenderer
↓
ReportExporter

القواعد:

- Report لا يعيد تنفيذ Analysis.
- Report لا يغير Result Contracts.
- Report لا يحول Execution failure إلى نجاح.
- ReportResult هو العقد القانوني.
- Renderers تستهلك ReportResult.
- ReportExporter يمر عبر renderer boundary.

لا يوجد مسار Report بديل قانوني في main الحالية.

المراجع التاريخية مثل `engines.report_engine` أو `FullReport` لا تعاد إلى المسار التنفيذي إلا بعد Architecture Review وDecision صريح.

==================================================
10. Orchestrator وPipeline
==================================================

### Orchestrator

مسؤول عن التنسيق عالي المستوى بين النتائج والخطوات.

لا يملك قواعد الأعمال الخاصة بـAnalysis أو Score أو Decision أو Report.

### Pipeline

يمثل Application Flow ويجمع المكونات القانونية في Use Case متكامل.

لا يعيد تنفيذ منطق Engines.

==================================================
11. Application / Bootstrap
==================================================

Bootstrap:

Bootstrap
↓
Dependency Container
↓
Application

مسؤوليته إنشاء وربط المكونات القانونية فقط.

Application:

API / GUI / Scheduler
↓
Application
↓
Pipeline / Orchestrator

Application ينسق حالات الاستخدام ودورة الحياة ولا يعتمد على UI implementation details.

==================================================
12. API / GUI / Scheduler
==================================================

### API

Router
↓
Service
↓
Application

API boundary ولا تحتوي Business Logic الأساسي.

### GUI

GUI
↓
Application

GUI طبقة عرض وتحكم فقط، وتبقى downstream من Core Intelligence.

### Scheduler

Scheduler
↓
Application
↓
Pipeline

Scheduler مسؤول عن WHEN وليس عن كيفية عمل Analysis.

==================================================
13. Repository / Storage
==================================================

Application
↓
MarketRepository
↓
Storage

SQLite أو أي تنفيذ تخزين آخر يبقى خلف Repository/Storage boundary.

لا تتسرب تفاصيل التخزين إلى Business Logic.

==================================================
14. Legacy Policy
==================================================

يصبح المكون Legacy عندما:

1. يوجد بديل canonical.
2. تم ترحيل المستهلكين الفعليين.
3. نجحت الاختبارات.
4. نجح التكامل.
5. لا توجد dependency تشغيلية فعالة عليه.

لا يحذف Legacy بالحدس.

لكن لا يسمح بإعادة استخدامه كمسار قانوني جديد دون قرار معماري.

==================================================
15. حالة الازدواجيات المعروفة
==================================================

تم حسم Report Architecture في Phase 1.

المسار القانوني هو:

models.report.ReportResult
↓
reports renderers
↓
reports.report_exporter.ReportExporter

أي ملفات أو مسارات تاريخية خارج ذلك المسار تعتبر Legacy references ما لم تثبت الحاجة إليها بقرار جديد.

أما `app/` و`application/` أو أي تعدد آخر فيظل مقبولًا فقط عندما تكون المسؤوليات مختلفة فعلًا، وليس لمجرد وجود اسمين متشابهين.

==================================================
16. Verification Boundary
==================================================

المعمارية لا تعتبر صحيحة لمجرد وجود Classes.

يجب أن تثبتها:

- Contract Tests.
- Integration Tests.
- E2E Tests عند وجود أثر تكاملي.
- Full Verification عند بوابة المرحلة.

المرجع الحالي للحالة والـVerification:
ORION_PROJECT_STATE.md

==================================================
17. قاعدة التطوير الحالية
==================================================

Phase 1 مكتملة.

Phase 2 تعمل فوق هذه المعمارية.

لا يعاد فتح عقد أو boundary مثبتة إلا بسبب معماري أو متطلب جديد مثبت بالأدلة.

==================================================
END
==================================================
