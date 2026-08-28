# ORION — المعمارية الرسمية

الإصدار: 2.2
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
- حدود Opportunity Response وPosition Management عند دخول النظام مراحل التداول.

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

عند دخول Trading Bot، يجب ألا تُستخدم حالة المركز أو توقيت الاستجابة كمتغيرات مخفية داخل Result Contract قائم. أي state جديد مطلوب لـPosition Management أو Opportunity Response يجب أن يملك contract مستقلًا ومراجعًا معماريًا.

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

### Opportunity Response

عند وجود فرصة قصيرة الأجل أو Sudden-Move / Acceleration event، يجب أن يستطيع المسار التشغيلي طلب إعادة تقييم أسرع من الدورة العادية دون كسر حدود الطبقات.

المبدأ المعماري:

Market Event
↓
Opportunity Re-evaluation Trigger
↓
Analysis / Opportunity Context
↓
Score / Decision
↓
ExecutionPlan

ولا يجوز أن تُدفن قاعدة الاستجابة السريعة داخل GUI أو Scheduler أو ExecutionAdapter.

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

عند دخول Trading Bot، يجب أن يكون هناك فصل صريح بين:

1. Entry Decision
2. Order Execution
3. Active Position Management
4. Exit Decision

ولا يجوز افتراض أن `SELL` الناتج من Decision الأساسي يغطي وحده كل حالات إدارة الصفقة المفتوحة.

==================================================
9. Opportunity Response Boundary
==================================================

Opportunity Response ليست مجرد Metric تقريرية؛ هي متطلب تشغيلي يمتد عبر عدة طبقات.

يجب أن يدعم التصميم مستقبلًا تسجيل سلسلة زمنية قابلة للتدقيق:

opportunity_detected_at
↓
revalidation_started_at
↓
decision_at
↓
execution_requested_at
↓
execution_confirmed_at

الحدود:

- Provider/MarketData يملك freshness/timestamp الخاص بالبيانات.
- Opportunity/Analysis يحدد أن حدثًا سريعًا يستحق إعادة التقييم.
- Decision يقرر دون انتظار غير مبرر.
- ExecutionPlan ينقل القرار دون إضافة delay غير مبرر.
- Execution يسجل زمن الطلب والتنفيذ الفعلي.
- Reporting/Audit يعرض جميع نقاط الزمن.

يجب ألا تستخدم قيمة زمنية ثابتة قبل إثباتها تجريبيًا؛ القيم النهائية تأتي من Performance/Replay Tests.

==================================================
10. Position Management Boundary
==================================================

بعد تنفيذ دخول ناجح، لا ينتهي المسار عند ExecutionResult.

المسار المستهدف:

ExecutionResult
↓
Active Position State
↓
Position Management
↓
Profit Protection / Trailing / Scale-Out / Exit Evaluation
↓
Exit Execution
↓
Final Position Result / Audit

Position Management مسؤول عن الاستمرار داخل الحركة عندما تكون الأدلة داعمة، وعن حماية الربح عند تراجع الزخم، وعن الخروج عند invalidation أو خطر تشغيلي.

لا يجوز اختزال هذه الوظيفة في `fixed take-profit` واحد دون إثبات تجريبي أنه لا يسبب Premature Exit مرتفعًا في الحركات القوية.

==================================================
11. Report Boundary — Canonical
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

عند توفر Trading Bot telemetry، يجب أن يتسع ReportResult أو عقد تقريري مستقل مراجع ليحمل Opportunity Response وPosition Management metrics دون تهريب state تشغيلي إلى Analysis/Decision contracts.

==================================================
12. Orchestrator وPipeline
==================================================

### Orchestrator

مسؤول عن التنسيق عالي المستوى بين النتائج والخطوات.

لا يملك قواعد الأعمال الخاصة بـAnalysis أو Score أو Decision أو Report.

### Pipeline

يمثل Application Flow ويجمع المكونات القانونية في Use Case متكامل.

لا يعيد تنفيذ منطق Engines.

في Trading Bot، لا يجوز أن يتحول Orchestrator إلى منطق لإدارة الصفقة؛ Position Management يجب أن يكون مكونًا قانونيًا مستقلًا.

==================================================
13. Application / Bootstrap
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
14. API / GUI / Scheduler
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

Scheduler لا يملك وحده Opportunity Response policy؛ الحدث السريع يجب أن يصل إلى مكونه القانوني دون أن يتحول Scheduler إلى محرك استراتيجية.

==================================================
15. Repository / Storage
==================================================

Application
↓
MarketRepository
↓
Storage

SQLite أو أي تنفيذ تخزين آخر يبقى خلف Repository/Storage boundary.

لا تتسرب تفاصيل التخزين إلى Business Logic.

==================================================
16. Legacy Policy
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
17. حالة الازدواجيات المعروفة
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
18. Verification Boundary
==================================================

المعمارية لا تعتبر صحيحة لمجرد وجود Classes.

يجب أن تثبتها:

- Contract Tests.
- Integration Tests.
- E2E Tests عند وجود أثر تكاملي.
- Full Verification عند بوابة المرحلة.

وبالنسبة لمرحلة Trading Bot، يجب أن تتضمن Verification أيضًا:

- Opportunity Response Latency.
- False Negative / Missed Opportunity analysis.
- Premature Exit analysis.
- Position Management state transitions.
- Auditability of event/decision/execution timestamps.

المرجع الحالي للحالة والـVerification:
ORION_PROJECT_STATE.md

==================================================
19. قاعدة التطوير الحالية
==================================================

Phase 1 مكتملة.

Phase 2 تعمل فوق هذه المعمارية.

لا يعاد فتح عقد أو boundary مثبتة إلا بسبب معماري أو متطلب جديد مثبت بالأدلة.

متطلب Opportunity Response وPosition Management هنا يعد متطلبًا معماريًا مستقبليًا محميًا، ولا يجوز إسقاطه عند الانتقال إلى Scalping/Trading Bot لمجرد أن المسار الأساسي يعمل.

==================================================
END
==================================================
