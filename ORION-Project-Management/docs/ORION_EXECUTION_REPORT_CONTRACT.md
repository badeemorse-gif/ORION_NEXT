# ORION — Execution → Report Contract

الإصدار: 1.1
الحالة: ACTIVE
المالك: Reporting / Auditability

## الغرض

هذه الوثيقة تثبت العقد الرسمي والوحيد للعلاقة بين `ExecutionResult` و`ReportResult`.

يوجد فصل إلزامي بين ثلاث دلالات مستقلة:

```text
STRUCTURAL COMPLETENESS
≠
EXECUTION SUCCESS
≠
PIPELINE SUCCESS
```

Report يستهلك evidence صادرًا من الطبقات السابقة ولا ينشئ intelligence جديدة، ولا يغيّر Decision semantics.

## الدلالات الرسمية

### Structural Completeness — `ReportResult.is_complete`

`is_complete` يجيب سؤالًا واحدًا فقط:

> هل توجد كل النتائج canonical upstream المطلوبة لبنية التقرير؟

لا يجيب هذا property عن نجاح التنفيذ أو نجاح الـpipeline.

### Report Audit Status — `ReportAuditStatus`

`COMPLETE` تعني أن عقد الـevidence مكتمل ولا توجد failure evidence، مع وجود `execution_status`.

`INCOMPLETE` تعني أن البنية المطلوبة لم تكتمل ولا توجد failure evidence مثبتة.

`FAILED` تعني وجود failure evidence في التنفيذ أو مرحلة upstream.

### Execution Success Evidence — `ReportAudit.execution_succeeded`

هذه الخاصية تعني شيئًا واحدًا فقط:

`execution_status == ExecutionStatus.EXECUTED`

وهي **execution evidence** وليست pipeline success.

`ExecutionStatus.SKIPPED` قد ينتج تقريرًا `COMPLETE` لكنه لا يثبت execution success.

### Pipeline Success

نجاح الـpipeline مملوك لـ`PipelineItemResult.success`، وليس لـ`ReportResult` أو `ReportAudit`.

لا توجد خاصية في Report باسم `is_successful` لأن الاسم يوحي بدلالة تشغيلية غير مملوكة للتقرير.

## الحالات الرسمية

### COMPLETE

توجد كل النتائج upstream المطلوبة في `ReportResult`، ولا توجد failure evidence، وحالة التنفيذ ليست `FAILED`.

`ExecutionStatus.EXECUTED` و`ExecutionStatus.SKIPPED` يمكن أن ينتجا تقريرًا `COMPLETE`.

لذلك:

```text
Report COMPLETE
does NOT imply
Execution SUCCESS
```

وبالأخص:

```text
COMPLETE + SKIPPED
→ structurally complete
→ execution_succeeded = False
```

### INCOMPLETE

لم تكتمل مجموعة النتائج المطلوبة للتقرير، ولا توجد failure evidence مثبتة.

`INCOMPLETE` لا يساوي نجاح pipeline ولا نجاح execution.

### FAILED

توجد failure evidence في execution أو في مرحلة upstream:

`ExecutionStatus.FAILED`
أو `failure_stage`
أو `failure_message`

ولا يجوز أن يبقى التقرير في `COMPLETE` عند وجود هذه الأدلة.

## حقول الأدلة الرسمية

`execution_status`

ينقل `ExecutionResult.status` كما هو. Report لا يعيد تصنيفه.

`failure_stage`

المرحلة التي أبلغ عنها pipeline كمصدر للفشل، مثل `ORCHESTRATION` أو `EXECUTION`.

`failure_message`

الرسالة التشغيلية الفعلية للفشل، دون توليد سبب جديد من Report.

`stage_trace`

التسلسل التشغيلي الذي عبرته النتيجة قبل إنشاء التقرير. المسار التنفيذي المباشر هو:

`ORCHESTRATION → EXECUTION → REPORT`

وعند فشل orchestration قبل execution:

`ORCHESTRATION → REPORT`

## Execution FAILED

العقد الملزم هو:

`ExecutionResult.status = FAILED`
↓
`Failure Evidence Report` مسموح ومطلوب حفظه عندما يمكن بناؤه
↓
`Report.audit.status = FAILED`
↓
`Pipeline.success = False`

يظل `ExecutionResult` داخل التقرير حتى يستطيع المشغل مراجعة `execution_status`, `execution_message`, `order_id`, وfailure evidence.

## API / Renderer / Exporter

- `ReportEngine.build_report()` يشتق `ReportAuditStatus` من الأدلة الموجودة فقط.
- `ReportEngine.export_dict()` و`export_json()` يحافظان على `audit` و`execution_status` وfailure fields دون إنشاء `success` أو `pipeline_success` بديل.
- JSON وHTML renderers يستهلكان `ReportResult` فقط ويعرضان audit evidence.
- `ReportExporter` قد يكتب Failure Evidence Report، لكن نجاح عملية الكتابة لا يساوي نجاح التقرير ولا نجاح الـpipeline.
- `ApiService.export_report()` يستخدم `ApiResponse.success` فقط لنجاح عملية export I/O. ويضع `export_success=True` و`pipeline_success=None` في payload حتى لا تختلط دلالة التصدير بدلالة الـpipeline.

مثال إلزامي:

```text
FAILED Report
+ successful file write
→ export_success = True
→ pipeline_success = None
→ audit_status = FAILED
```

## الممنوع

لا يجوز لأي Report component:

- استخدام `ReportAuditStatus.COMPLETE` كمرادف لنجاح execution.
- استخدام `ReportResult.is_complete` كمرادف لنجاح pipeline.
- تحويل `FAILED` إلى `SUCCESS`.
- إسقاط `ExecutionResult` الفاشل من التقرير.
- إنشاء `is_successful` أو أي alias عام يخلط structural completeness مع operational success.
- استنتاج intelligence جديدة.
- إعادة حساب Decision أو تغيير semantics الخاصة به.
- اعتبار نجاح export I/O مساويًا لنجاح pipeline.

END
