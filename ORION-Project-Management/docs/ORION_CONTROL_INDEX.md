# ORION — CONTROL INDEX

الإصدار: 1.5
الحالة: ACTIVE
المشروع: ORION

## الوثائق الرسمية ومالك كل معلومة

- GPT EXECUTION RULES → `ORION_GPT_EXECUTION_RULES.md`
  قواعد تشغيل GPT، نموذج التطوير بالحزم، وسياسة التطوير/المزامنة.
- CONTROL INDEX → `ORION_CONTROL_INDEX.md`
  خريطة الوثائق وملكية المعلومات.
- PROJECT CHARTER → `ORION_PROJECT_CHARTER.md`
  تعريف المشروع ونطاقه وأهدافه العامة.
- WORK PROTOCOL → `ORION_WORK_PROTOCOL.md`
  طريقة التنفيذ والمراجعة والاختبار والتسليم والتكامل المؤجل.
- ARCHITECTURE → `ORION_ARCHITECTURE.md`
  المعمارية الحالية وحدود الطبقات والعقود.
- PROJECT STATE → `ORION_PROJECT_STATE.md`
  الحالة الحالية فقط.
- ROADMAP → `ORION_ROADMAP.md`
  ترتيب المراحل وشروط الانتقال.
- FUTURE ROADMAP → `ORION_FUTURE_ROADMAP.md`
  الأهداف المستقبلية فقط.
- FUTURE PRODUCT VISION → `ORION_FUTURE_PRODUCT_VISION_DESKTOP_APPLICATION.md`
  تصور المنتج النهائي.
- ARCHITECTURE FINDINGS → `ORION_ARCHITECTURE_FINDINGS.md`
  سجل Findings وحالاتها.
- DECISIONS → `ORION_DECISIONS.md`
  القرارات المؤثرة.
- CHANGELOG → `ORION_CHANGELOG.md`
  التاريخ التنفيذي المهم.
- KNOWN PROBLEMS → `ORION_KNOWN_PROBLEMS.md`
  المشاكل المؤكدة فقط.
- RESTORE/ALL SYNC CONTRACT → `ORION_RESTORE_ALL_BRANCH_SYNC.md`
  عقد MAIN/ALL والعزل والمرايا.

## قاعدة المصدر الواحد

كل معلومة لها مالك رئيسي واحد. لا تنشأ وثيقة بديلة تؤدي نفس الوظيفة دون قرار موثق.

## متى نقرأ الوثائق

- رسالة ORION عادية → GPT EXECUTION RULES + CONTROL INDEX.
- أمر 1 → EXECUTION RULES + CONTROL INDEX + PROJECT STATE + ROADMAP ثم الوثائق المطلوبة فقط.
- مراجعة تطوير → EXECUTION RULES + CONTROL INDEX + الحالة عند الحاجة + ARCHITECTURE/FINDINGS والكود المتأثر.
- Workflow/Sync → EXECUTION RULES + CONTROL INDEX + WORK PROTOCOL + RESTORE/ALL SYNC CONTRACT عند تأثر MAIN/ALL.
- مراجعة شاملة/تعارض → مراجعة موسعة للوثائق والكود والاختبارات المتأثرة.

## سياسة التطوير والمزامنة الحالية

GITHUB هو مصدر الحقيقة أثناء التطوير.

المطورون داخل ChatGPT يعملون على فروع GitHub ويكملون حزمًا كاملة داخل نطاقاتهم.

لا تتم مزامنة GITHUB → LOCAL بعد كل تعديل صغير.

`C:\Users\badee\Desktop\ORION_NEXT` هي بيئة Development / Integration محلية، وليست Sandbox لمزامنة كل فرع.

عند اكتمال حالة التكامل فقط يتم إنشاء نسخة محلية نظيفة ومحددة بالـbranch/commit ثم تنفيذ Full Verification / E2E / parity.

لا يجوز لمطور ChatGPT الادعاء بأنه شغّل اختبارًا محليًا دون تنفيذ فعلي.

## المرحلة الحالية

`ORION_PROJECT_STATE.md` هو المصدر الوحيد للمرحلة الحالية.

## المستودع

`badeemorse-gif/ORION_NEXT`

الفرع المرجعي العام: `main`

الجذر المحلي: `C:\Users\badee\Desktop\ORION_NEXT`

END
