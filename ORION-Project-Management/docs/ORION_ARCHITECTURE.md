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

لا تحدد المرحلة الحالية؛ لذلك يرجع إلى ORION_PROJECT_STATE.md.

==================================================
2. المبدأ المعماري
==================================================

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

- Engines لا تعتمد مباشرة على Binance.
- Domain لا يعتمد على GUI أو API.
- Business Logic الأساسي لا يوضع في GUI أو Router.
- Orchestrator ينسق ولا يصبح مستودعًا لقواعد الأعمال.
- MarketDataset لا يحمل نتائج المراحل الأخرى بصورة دائمة.
- Legacy لا يعود للمسار القانوني دون قرار معماري.

==================================================
4. Market Data Boundary
==================================================

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

==================================================
5. Result Contracts
==================================================

AnalysisResult
ProfileResult
ScoreResult
DecisionResult
ExecutionPlan
ExecutionResult
ReportResult

كل مرحلة تنتج نتيجة مستقلة.

==================================================
6. Intelligence Layer
==================================================

Indicators يحسب المؤشرات.
Analysis ينتج AnalysisResult.
Profile ينتج ProfileResult.
Score ينتج ScoreResult.
Decision ينتج DecisionResult.

Report لا يدخل في توليد intelligence.

==================================================
7. Execution Boundary
==================================================

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

==================================================
8. Report Boundary — Canonical
==================================================

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

القواعد الملزمة:

- Report يستهلك evidence فقط.
- Report لا يعيد تنفيذ Analysis/Score/Decision/Execution.
- Report لا يغير Decision semantics.
- `ReportResult` هو العقد القانوني.
- Renderers تستهلك `ReportResult` فقط.
- Exporter يكتب artifact ولا يقرر نجاح pipeline.
- نجاح كتابة ملف report ليس نجاحًا للتشغيل.

العقد التفصيلي الوحيد هو:
`ORION_EXECUTION_REPORT_CONTRACT.md`

==================================================
9. Execution → Report Failure Semantics
==================================================

ExecutionStatus.FAILED
↓
Failure Evidence Report مسموح
↓
Report.audit.status = FAILED
↓
Pipeline.success = False

يجب أن يحتفظ التقرير بـExecutionResult وبالأدلة التالية عند توافرها:

- execution_status
- execution_message
- order_id
- failure_stage
- failure_message
- stage_trace

لا يجوز لأي renderer/exporter/API تحويل `FAILED` إلى success semantics.

`COMPLETE` و`INCOMPLETE` و`FAILED` هي الحالات الرسمية لـ`Report.audit.status`.

==================================================
10. Orchestrator وPipeline
==================================================

Orchestrator ينسق الخطوات ويحتفظ بالـresults الرسمية.
Pipeline يمثل Application Flow.

Pipeline مسؤول عن إبقاء `Pipeline.success=False` عند failure، مع السماح بتوليد Failure Evidence Report عندما توجد النتيجة اللازمة لبنائه.

==================================================
11. Application / Bootstrap
==================================================

Bootstrap
↓
Dependency Container
↓
Application

Application ينسق حالات الاستخدام ولا يعتمد على UI implementation details.

==================================================
12. API / GUI / Scheduler
==================================================

API boundary لا تحتوي Business Logic الأساسي.
GUI downstream من Core Intelligence.
Scheduler مسؤول عن WHEN وليس عن كيفية عمل Analysis.

عند `export_report` تعكس API حالة التقرير:
`COMPLETE → success=True`
`INCOMPLETE → success=False`
`FAILED → success=False`

==================================================
13. Repository / Storage
==================================================

Application
↓
MarketRepository
↓
Storage

==================================================
14. Legacy Policy
==================================================

يصبح المكون Legacy عندما يوجد بديل canonical وتم ترحيل المستهلكين ونجحت الاختبارات والتكامل ولا توجد dependency تشغيلية عليه.

==================================================
15. Verification Boundary
==================================================

يجب أن تثبت المعمارية عبر:
- Contract Tests.
- Integration Tests.
- E2E Tests عند وجود أثر تكاملي.
- Full Verification عند بوابة المرحلة.

==================================================
16. قاعدة التطوير الحالية
==================================================

Phase 1 مكتملة.
Phase 2 تعمل فوق العقود والحدود المثبتة.

==================================================
END
==================================================
