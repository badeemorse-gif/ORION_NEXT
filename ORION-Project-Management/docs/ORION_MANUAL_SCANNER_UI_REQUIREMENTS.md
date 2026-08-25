# ORION — Manual Scanner UI Requirements

## 1. Purpose

هذا المستند يثبت كمتطلب منتج رسمي تفاصيل واجهة **Manual Scanner** داخل ORION Desktop Application، حتى لا تضيع هذه المتطلبات أثناء اكتمال طبقات المشروع والتكامل النهائي.

الواجهة مخصصة للمراقبة واتخاذ القرار اليدوي، وليست محرك تداول مستقلًا ولا سلطة تنفيذ بديلة عن ORION Core.

---

## 2. Relationship to the Existing Product Vision

هذا المستند يكمل قسم **Market Scanner** و **Opportunity Analysis** في:

`ORION-Project-Management/docs/ORION_FUTURE_PRODUCT_VISION_DESKTOP_APPLICATION.md`

ويحوّل فكرة الـScanner العامة إلى متطلبات تشغيلية قابلة للتنفيذ والاختبار.

الـManual Scanner يجب أن يستخدم نفس canonical intelligence / decision path المعتمد في ORION، ولا يجوز إنشاء محرك تحليل أو Decision Engine منفصل للواجهة.

---

## 3. Manual Scanner Main Screen

تتضمن الواجهة شاشة مخصصة باسم:

**Manual Scanner**

وتعرض قائمة الفرص الحالية بصورة مرتبة ومحدثة.

لكل أصل يظهر على الأقل:

- Symbol
- Market / Universe
- Opportunity Score
- Opportunity Class
- Direction
- Entry State
- Entry Readiness
- Entry Price
- Stop Loss
- Target 1
- Target 2 عند توفره
- Risk / Reward
- Risk Flags / Warnings
- Last Update
- سبب ظهور الفرصة
- سبب القبول أو الرفض
- سبب الانتظار عند عدم الجاهزية

---

## 4. Opportunity State Model

يجب أن توضح الواجهة حالة كل أصل بصورة مباشرة، مثل:

```text
WATCH
→ DEVELOPING
→ ENTRY READY
→ ACTIVE SETUP
→ INVALIDATED
```

ولا يجوز أن توحي الواجهة بأن `WATCH` أو `DEVELOPING` تعني وجود أمر تداول.

`ENTRY READY` يعني فقط أن canonical decision layer تعتبر شروط الدخول مستوفاة في آخر تقييم؛ ولا يساوي ذلك تنفيذًا تلقائيًا.

---

## 5. Manual Symbol Detail View

عند اختيار عملة من القائمة يستطيع المستخدم فتح صفحة/لوحة تفصيلية تعرض:

### Market Context

- السعر الحالي
- آخر تحديث
- حالة السوق العامة
- الأطر الزمنية المستخدمة
- freshness / health indicators عند توفرها

### Opportunity

- Opportunity Score
- Opportunity Class
- Recall provenance / recall lanes عند توفرها
- أسباب الظهور في الـScanner
- عوامل القوة
- عوامل الضعف

### Entry Setup

- Direction
- Entry Price
- Stop Loss
- Target 1
- Target 2 عند توفره
- Risk / Reward
- Entry Readiness
- Entry State
- صلاحية الإشارة / freshness

### Decision Explanation

يجب أن يستطيع المستخدم معرفة:

- Why now?
- Why not now?
- What supports the setup?
- What blocks the setup?
- What invalidates the setup?

كل ذلك من الـcanonical DecisionTrace / domain outputs، وليس من منطق GUI جديد.

---

## 6. Refresh / Update Behavior

الـScanner يجب أن يدعم تحديثًا دوريًا قابلًا للضبط.

### Default

```text
refresh_interval = 5 minutes
```

### Configurable

يجب أن يكون التحديث قابلًا للضبط، مع دعم استخدام 5 أو 10 دقائق على الأقل وفق إعداد المستخدم.

هذا يتوافق مع إعدادات Scanner الحالية التي تحتوي على `refresh_interval_seconds` وقيمة افتراضية 300 ثانية.

### Manual Refresh

يجب توفير زر:

**Refresh Now**

مع إظهار:

- آخر تحديث مكتمل
- وقت التحديث التالي المتوقع
- حالة عملية التحديث (`RUNNING / SUCCESS / FAILED`)

---

## 7. Live Price vs Decision Refresh

الواجهة يجب أن تميز بين:

### Live Market Data

يمكن عرض السعر الحالي/آخر سعر متاح بصورة أكثر تكرارًا أو لحظية عند توفر البنية اللازمة.

### Decision Refresh

يجب أن تعتمد Entry / Stop / Target / Opportunity state على آخر canonical decision refresh، وليس على إعادة حساب منفصلة داخل GUI.

لذلك قد يتغير السعر على الشاشة بين Refresh وآخر، بينما تبقى آخر Decision موثقة إلى أن تتم دورة تحديث جديدة.

---

## 8. Manual Trading Use Case

الـManual Scanner مخصص للمستخدم الذي يريد العمل يدويًا.

مثال الاستخدام:

```text
User sees strong opportunity
        ↓
opens symbol detail
        ↓
reviews Entry / Stop / Target / R:R
        ↓
reviews Why / Risks / Invalidation
        ↓
places manual trade externally if desired
```

الواجهة لا ترسل أمرًا للبورصة بمجرد عرض `ENTRY READY`.

أي Manual Execution feature مستقبلية يجب أن تكون منفصلة وصريحة ومحمية بطبقاتها الخاصة.

---

## 9. Scanner Filters and Sorting

يجب أن يستطيع المستخدم:

- ترتيب الفرص حسب Opportunity Score
- ترتيب حسب Entry Readiness
- تصفية حسب Direction
- تصفية حسب Opportunity Class
- تصفية حسب Entry State
- إظهار فرص `ENTRY READY` فقط
- إظهار Watch / Developing فقط
- إظهار التحذيرات عالية الخطورة
- البحث عن Symbol محدد

ويجب أن تكون هذه عمليات عرض فقط؛ لا يجوز أن تعيد GUI تعريف الـcanonical ranking أو Decision.

---

## 10. Strong-Mover Visibility

يجب أن تبقى العملات ذات التحرك القوي مرئية في الـScanner حتى لو لم تصبح `ENTRY READY`.

ينبغي أن يستطيع المستخدم رؤية حالات مثل:

```text
Strong Opportunity
+ Direction insufficient
= Visible / WAIT
```

بدل اختفاء الفرصة بالكامل.

الهدف هو تقليل false negatives في العرض اليدوي مع الحفاظ على Hard Safety Guards في القرار.

---

## 11. New / High-Volatility Listings

لا يتم استبعاد العملة الجديدة تلقائيًا من الـManual Scanner لمجرد حداثة الإدراج.

يجب أن تظهر عند اجتياز الـeligibility الأساسية، مع عرض المخاطر المرتبطة بها بصورة واضحة، مثل:

- New Listing
- High Volatility
- Wide Spread
- Liquidity Warning
- Execution Risk
- Data Quality Warning

المستخدم يرى الفرصة والمخاطر معًا بدل إخفائها دون تفسير.

---

## 12. Entry / Exit Display Contract

عندما تكون القيم متاحة وصالحة، يجب أن تعرض الواجهة بوضوح:

```text
ENTRY
STOP LOSS
TARGET 1
TARGET 2
R/R
INVALIDATION
```

عند عدم وجود Entry صالح، لا يجوز للواجهة تصنيع سعر أو Stop أو Target افتراضي لغرض العرض.

بدل ذلك تعرض:

```text
Entry: N/A
Reason: DIRECTIONAL_INSUFFICIENT
```

أو السبب canonical المناسب.

---

## 13. Auditability

لكل حالة Manual Scanner يجب أن يكون بالإمكان تتبع:

- timestamp
- source market snapshot
- canonical opportunity result
- canonical DecisionTrace
- Entry / Stop / Target data source
- warnings / rejection reasons
- last refresh identity

الواجهة لا تعيد حساب القرار لتكوين Audit Trail جديد.

---

## 14. Architecture Boundary

المسار المستهدف:

```text
Market Data
    ↓
ORION Discovery / Fast Recall
    ↓
Opportunity Analysis
    ↓
Canonical Decision
    ↓
Manual Scanner View
```

والـGUI تبقى:

**Presentation + User Control only**

ولا تصبح:

- Analysis Engine
- Scoring Engine
- Decision Engine
- Risk Engine
- Execution Engine

---

## 15. Acceptance Criteria

يعتبر Manual Scanner requirement مكتملًا عندما يستطيع المستخدم:

1. رؤية الفرص الحالية بوضوح.
2. معرفة سبب ظهور كل فرصة.
3. فتح عملة ومشاهدة Entry / Stop / Target / R:R عندما تكون صالحة.
4. معرفة لماذا الفرصة `ENTRY READY` أو `WAIT` أو `INVALIDATED`.
5. رؤية العملات القوية حتى عندما تكون غير قابلة للدخول بعد.
6. رؤية مخاطر العملات الجديدة/عالية التقلب بدل اختفائها بلا تفسير.
7. تحديث البيانات يدويًا أو دوريًا، مع افتراضي 5 دقائق وإمكانية 10 دقائق.
8. التأكد أن ما تعرضه الواجهة هو نفس canonical intelligence/decision output المستخدم في بقية النظام.

---

## 16. Non-Goals

هذا المستند لا يفرض:

- Auto execution من خلال Manual Scanner
- تغيير D1/D6/D7 semantics
- تخفيف Hard Safety Guards
- إنشاء Decision Engine جديد
- تشغيل Live Trading
- فرض عدد صفقات يومي

---

## 17. Product Requirement Status

```text
MANUAL SCANNER UI = REQUIRED FINAL PRODUCT CAPABILITY
```

ويجب عدم اعتبار المنتج النهائي مكتملًا من منظور تجربة المستخدم قبل تنفيذ هذا القسم أو اعتماد قرار صريح بإلغاء المتطلب.
