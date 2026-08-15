# ORION — CONTROL INDEX

الإصدار: 1.6  
الحالة: ACTIVE  
المشروع: ORION

## الوثائق الرسمية ومالك كل معلومة

- GPT EXECUTION RULES → `ORION_GPT_EXECUTION_RULES.md`
- CONTROL INDEX → `ORION_CONTROL_INDEX.md`
- PROJECT CHARTER → `ORION_PROJECT_CHARTER.md`
- WORK PROTOCOL → `ORION_WORK_PROTOCOL.md`
- ARCHITECTURE → `ORION_ARCHITECTURE.md`
- EXECUTION → REPORT CONTRACT → `ORION_EXECUTION_REPORT_CONTRACT.md`
  العقد الوحيد لعلاقة ExecutionResult بـReportResult، وحالات COMPLETE/INCOMPLETE/FAILED وأدلة الفشل.
- PROJECT STATE → `ORION_PROJECT_STATE.md`
- ROADMAP → `ORION_ROADMAP.md`
- FUTURE ROADMAP → `ORION_FUTURE_ROADMAP.md`
- FUTURE PRODUCT VISION → `ORION_FUTURE_PRODUCT_VISION_DESKTOP_APPLICATION.md`
- ARCHITECTURE FINDINGS → `ORION_ARCHITECTURE_FINDINGS.md`
- DECISIONS → `ORION_DECISIONS.md`
- CHANGELOG → `ORION_CHANGELOG.md`
- KNOWN PROBLEMS → `ORION_KNOWN_PROBLEMS.md`
- RESTORE/ALL SYNC CONTRACT → `ORION_RESTORE_ALL_BRANCH_SYNC.md`

## قاعدة المصدر الواحد

كل معلومة لها مالك رئيسي واحد. العقد التفصيلي للعلاقة Execution → Report مملوك حصريًا لـ`ORION_EXECUTION_REPORT_CONTRACT.md`.

## متى نقرأ الوثائق

- مراجعة Reporting/Auditability → EXECUTION/REPORT CONTRACT + ARCHITECTURE + PROJECT STATE + الكود والاختبارات المتأثرة.
- مراجعة شاملة/تعارض → مراجعة موسعة للوثائق والكود والاختبارات المتأثرة.

## سياسة التطوير والمزامنة الحالية

GITHUB هو مصدر الحقيقة أثناء التطوير.
المطورون داخل ChatGPT يعملون على فروع GitHub ويكملون حزمًا كاملة داخل نطاقاتهم.
لا تتم مزامنة GITHUB → LOCAL بعد كل تعديل صغير.

لا يجوز لمطور ChatGPT الادعاء بأنه شغّل اختبارًا محليًا دون تنفيذ فعلي.

## المرحلة الحالية

`ORION_PROJECT_STATE.md` هو المصدر الوحيد للمرحلة الحالية.

## المستودع

`badeemorse-gif/ORION_NEXT`

الفرع المرجعي العام: `main`

END
