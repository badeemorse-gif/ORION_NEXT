# ORION — Execution → Report Contract

الإصدار: 1.0
الحالة: ACTIVE
المالك: Reporting / Auditability

## الغرض

هذه الوثيقة تثبت العقد الرسمي والوحيد للعلاقة بين `ExecutionResult` و`ReportResult`.

Report يستهلك evidence صادرًا من الطبقات السابقة ولا ينشئ intelligence جديدة، ولا يغيّر Decision semantics.

## الحالات الرسمية

`Report.audit.status` له ثلاث حالات فقط:

### COMPLETE

توجد كل النتائج upstream المطلوبة في `ReportResult`، ولا توجد failure evidence، وحالة التنفيذ ليست `FAILED`.

`ExecutionStatus.EXECUTED` و`ExecutionStatus.SKIPPED` يمكن أن ينتجا تقريرًا `COMPLETE`.

`COMPLETE` هو اكتمال عقد التقرير، وليس ترخيصًا لإعادة تفسير قرار التداول.

### INCOMPLETE

لم تكتمل مجموعة النتائج المطلوبة للتقرير، ولا توجد failure evidence مثبتة.

مثال: `execution_status = None` مع غياب `ExecutionResult`.

`INCOMPLETE` لا يساوي نجاح pipeline.

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
- `ReportEngine.export_dict()` و`export_json()` يحافظان على `audit` و`execution_status` وfailure fields دون إنشاء `success` بديل.
- JSON وHTML renderers يستهلكان `ReportResult` فقط ويعرضان audit evidence.
- `ReportExporter` قد يكتب Failure Evidence Report، لكن نجاح عملية الكتابة لا يساوي نجاح التقرير.
- `ApiService.export_report()` يعيد `success=False` عندما يكون `Report.audit.status = FAILED` أو `INCOMPLETE` حتى لو نجحت كتابة الملف.

## الممنوع

لا يجوز لأي Report component:

- تحويل `FAILED` إلى `SUCCESS`.
- إسقاط `ExecutionResult` الفاشل من التقرير.
- استنتاج intelligence جديدة.
- إعادة حساب Decision أو تغيير semantics الخاصة به.
- اعتبار نجاح export I/O مساويًا لنجاح pipeline.

END
