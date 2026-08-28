# ORION — Scalping Opportunity Optimization Specification

الإصدار: 1.1
الحالة: ACCEPTED — DEVELOPMENT GATE AFTER CURRENT PAPER TEST
المشروع: ORION_NEXT

==================================================
1. PURPOSE
==================================================

هذه الوثيقة تثبت المعيار التشغيلي المعتمد لتطوير Scalping Opportunity Engine بعد اكتمال تجربة الـ$50 / 4H الحالية وتحليل نتائجها.

الهدف ليس بناء نظام بقواعد جامدة تؤدي إلى ندرة الصفقات، وليس مطاردة العملات الأكثر ارتفاعًا بصورة عمياء.

الهدف هو:

**Maximum Sustainable Portfolio Growth + Controlled Risk**

أي تنمية المحفظة بأعلى قدرة عملية قابلة للاستمرار، مع التحكم في المخاطرة، وعدم الهروب غير المبرر من الفرص الجيدة.

==================================================
2. CORE PRINCIPLE
==================================================

ORION ليس نظامًا من نوع:

PASS / FAIL
→ BUY / NO TRADE

بل يجب أن يعمل كمنظومة تقييم متدرجة:

Market Universe
↓
Opportunity Detection
↓
Opportunity Classification
↓
Entry Setup Detection
↓
Risk / Reward Evaluation
↓
Capital Allocation
↓
Execution
↓
Position Management
↓
Exit

القواعد الصلبة تستخدم فقط عند وجود سبب أمني أو تشغيلي أو تعاقدي واضح.
أما جودة الفرصة فتُعامل كمسألة وزن واحتمال وأفضلية، لا كسلسلة Gates جامدة بلا مبرر.

**قاعدة تشغيلية حاكمة:** لا يجوز أن تتسبب دورة تحليل بطيئة أو انتظار غير ضروري لإشارة إطار زمني أبطأ في فقدان فرصة قصيرة الأجل كانت مؤهلة وفق الأدلة المتاحة في الوقت الفعلي.

==================================================
3. MULTI-TIMEFRAME OPPORTUNITY MODEL
==================================================

يعتمد ORION مستقبلًا على أدوار واضحة للأطر الزمنية، وليس على إطار واحد يقرر كل شيء.

### 1D — MARKET REGIME / SAFETY CONTEXT

الـ1D يصف البيئة العامة والمخاطر والـregime.
لا يجوز أن يكون Trend يومي مكتمل شرطًا مطلقًا لمنع كل فرصة Scalping قصيرة الأجل.

### 4H — PRIMARY DIRECTION

الـ4H هو الاتجاه الرئيسي المرجعي للفرصة.
يستخدم كـDirectional Evidence وWeight في التقييم، وليس كـPASS/FAIL gate مطلق.

### 1H — ACTIVE TREND / MOMENTUM

الـ1H يحدد الاتجاه التشغيلي النشط وقوة الحركة والاستمرارية الحالية.

### 15M — ENTRY TIMING

الـ15M يستخدم لتحديد جودة التوقيت، الاستمرار، التصحيح، والعودة إلى الاتجاه.

يمكن إضافة إطار أقصر لاحقًا فقط إذا أثبتت البيانات أنه يضيف معلومة مستقلة وذات قيمة.

==================================================
4. SHORT-TERM OPPORTUNITY / ACCELERATION
==================================================

يجب أن يميز ORION بين:

- حركة بطيئة مستقرة.
- Momentum حديث.
- Acceleration حقيقي.
- حركة ممتدة أصبحت خطرة.

يجب أن تتضمن الدراسة المستقبلية عناصر مثل:

- short-term ROC.
- multi-window momentum.
- acceleration.
- range expansion.
- volume expansion.
- persistence.
- pullback quality.

النمط التشغيلي المستهدف يشمل حركات من نوع:

+6%
-3%
+7%
-2%
...

عندما تكون الحركة استمرارًا صحيًا وليست Pump عشوائيًا.

**Sudden-Move Response Requirement:** عند رصد تغير سعري سريع أو توسع غير اعتيادي في النطاق خلال نافذة قصيرة، يجب أن ينتقل النظام إلى إعادة تقييم سريعة للفرصة بدل انتظار اكتمال دورة تقييم بطيئة. لا يعني ذلك الدخول الآلي؛ يعني تقليص زمن اكتشاف/تحقق/قرار الفرصة إلى الحد الذي تثبته الاختبارات دون الإخلال بقيود المخاطر.

==================================================
5. OPPORTUNITY CLASSIFICATION
==================================================

يجب ألا تكون كل الفرص مصنفة تحت Trend واحد فقط.

الأنماط الأساسية المستهدفة:

### A — TREND CONTINUATION

4H direction + 1H continuation + short-term confirmation.

### B — BREAKOUT / ACCELERATION

4H neutral أو bullish قد تكون مقبولة إذا كان 1H/15M يظهران breakout وacceleration وحجمًا داعمًا ومخاطرة مضبوطة.

### C — PULLBACK CONTINUATION

اتجاه واضح، ثم تصحيح منضبط، ثم استعادة للاتجاه مع entry quality مناسبة.

يجب أن تظل classification قابلة للتفسير، وأن لا تتحول إلى محركات Opportunity منفصلة تعيد تعريف D1 contract.

==================================================
6. CANDIDATE POOL VS ACTIVE TRADING SET
==================================================

لا يجب أن يكون Top-N الصغير هو كل ما يعرفه النظام عن السوق.

المبدأ المستهدف:

Broad Candidate Pool
↓
Active Trading Set
↓
Immediate Entry Candidates

يجب أن تسمح المعمارية بمراقبة عدد أوسع من المرشحين، مع Active Top-N أصغر للتنفيذ والمتابعة، حتى لا تضيع العملة عند تغير ترتيبها مؤقتًا.

القيم العددية النهائية لا تُثبت إلا بعد الاختبار.

**ممنوع تشغيليًا** إسقاط مرشح قوي فقط لأن ترتيبه المؤقت انخفض دورة واحدة أثناء استمرار الـmomentum أو الـacceleration.

==================================================
7. RANKING PHILOSOPHY
==================================================

ترتيب الفرص يجب أن يجمع بين:

- Quality.
- Direction.
- Current Momentum.
- Acceleration.
- Liquidity.
- Volatility / Risk.
- Structure.
- Entry Quality.

لا يجوز أن يكون 4H أو 1D سببًا منفردًا لإلغاء فرصة قصيرة الأجل سليمة.

كما لا يجوز أن يكون ارتفاع 24h وحده سببًا كافيًا للدخول.

==================================================
8. INDICATOR EVIDENCE LAYER
==================================================

Supertrend أو مؤشرات مشابهة مسموح بدراستها كـadditional evidence فقط.

يجب عدم تحويل:

Supertrend = GREEN
→ BUY

أو:

Supertrend = RED
→ REJECT

قبل إثبات القيمة التجريبية.

أي مؤشر جديد يجب أن يثبت أنه يضيف معلومة مستقلة، وألا يعيد حساب الاتجاه نفسه عدة مرات عبر EMA / MACD / ADX / Supertrend وغيرها.

==================================================
9. DECISION GRADIENT
==================================================

يجب أن يتحول القرار من Gate واحد إلى مستويات قابلة للتفسير، مثل:

A+
→ Entry Now

A
→ Entry Allowed

B
→ Watch / Pullback

C
→ No Trade

D
→ Reject

الأسماء النهائية قابلة للتعديل، لكن المبدأ ثابت:

**Opportunity ≠ Immediate Entry**

الفرصة قد تكون ممتازة بينما التوقيت غير مناسب.

**Anti-Wait Rule:** لا يجوز أن يبقى مرشح مؤهل في WAIT إلى أجل غير محدد بينما تستمر أدلة الـmomentum/acceleration. يجب أن تكون لكل حالة Watch/Wait نافذة إعادة تقييم محددة أو محفزة بحدث واضح، ويجب تسجيل سبب استمرار الانتظار.

==================================================
10. CAPITAL ALLOCATION ROLE
==================================================

لا تعني زيادة الفرص زيادة المخاطرة بالتساوي.

Capital Management يجب أن يقرر التخصيص وفق:

- opportunity quality.
- risk.
- available capital.
- concurrent positions.
- minimum symbol notional.

قد تحصل فرصة قوية على تخصيص أكبر، بينما تحصل فرصة أضعف على تخصيص أصغر أو لا تحصل على تخصيص.

Minimum Notional ليس sizing policy؛ هو execution constraint.

==================================================
11. NO FIXED DAILY TRADE TARGET
==================================================

الهدف التشغيلي ليس إجبار النظام على عدد محدد من الصفقات كل يوم.

20–30 صفقة يوميًا بنسبة فوز 70–80% هي **هدف أداء محتمل** في ظروف سوق مناسبة، وليست قاعدة تنفيذ أو KPI مضمونًا.

يجب ألا يفتح البوت صفقة لمجرد الوصول إلى عدد معين.

في السوق الهادئ قد يقل عدد الصفقات.
وفي السوق النشط قد يرتفع.

==================================================
12. PERFORMANCE METRICS
==================================================

لا يعتمد تقييم النظام على Win Rate وحده.

يجب قياس:

- Trades / day.
- Win Rate.
- Expectancy.
- Profit Factor.
- Average Win.
- Average Loss.
- Maximum Drawdown.
- Capital Utilization.
- Fees impact.
- Average Hold Time.
- Opportunity Capture Rate.
- False Negative Rate.
- Rejection reasons.
- **Detection Latency.**
- **Decision Latency.**
- **Execution Latency.**
- **Opportunity Response Failure Rate.**
- **Premature Exit Rate on successful momentum moves.**

الهدف هو تعظيم النمو المعدل بالمخاطر، وليس تعظيم عدد الصفقات أو Win Rate بمعزل عن بقية المؤشرات.

==================================================
13. OPPORTUNITY CAPTURE RATE
==================================================

يجب إنشاء قياس مستقل لقدرة ORION على عدم تفويت الفرص الجيدة.

بالنسبة لحركات السوق المهمة خلال نافذة الاختبار:

Market Mover
↓
Was it in Universe?
↓
Eligible?
↓
D1 Score?
↓
Rank?
↓
Profile Context?
↓
Decision?
↓
Entry Allowed?
↓
If rejected — why?

هذا القياس أهم من الاكتفاء بعدد الصفقات المنفذة.

**Opportunity Capture لا يُقاس فقط بوجود إشارة؛ بل يُقاس أيضًا بالزمن.** يجب تسجيل أول لحظة أصبحت فيها الفرصة مؤهلة، ثم زمن اكتشافها، وزمن القرار، وزمن التنفيذ، وقياس الجزء القابل للتداول من الحركة الذي تم التقاطه.

==================================================
14. DECISION TRACE
==================================================

يجب أن يسجل النظام في المسار المستقبلي، عند الحاجة للتحليل:

- symbol.
- D1 score.
- D1 rank.
- directional evidence.
- 1D regime.
- 4H direction.
- 1H trend/momentum.
- 15M entry context.
- acceleration evidence.
- profile health.
- profile confidence.
- decision.
- risk level.
- blocks.
- warnings.
- rejection reason.
- **opportunity_detected_at.**
- **decision_at.**
- **execution_at.**
- **latency_ms لكل مرحلة.**
- **opportunity state at each transition.**

الهدف هو الإجابة عن السؤال:

**لماذا لم يدخل ORION هذه العملة؟**

ودون تخمين، مع القدرة على الإجابة أيضًا:

**هل دخل بعد فوات الجزء المهم من الحركة بسبب التأخر؟**

==================================================
15. CURRENT OBSERVATION / DESIGN FINDING
==================================================

التجربة الحالية أظهرت أن D1 يستطيع اكتشاف فرص مرتفعة الترتيب، بينما قد تمنع طبقات Decision/Context الدخول لاحقًا.

لا يعتبر هذا فشلًا بحد ذاته قبل تحليل السبب.
لكنه Finding يجب اختباره منهجيًا.

كما أن الاعتماد على 31 شمعة يومية لاستخراج trend/momentum الرئيسي وحده قد يكون بطيئًا بالنسبة لفرص Scalping قصيرة الأجل.

هذه الوثيقة تعتمد Multi-Timeframe model بدل استخدام الـ1D كـTrend Gate.

**Finding إضافي يجب حسمه قبل الاعتماد:** إذا أظهرت الاختبارات أن فرصة قوية تفقد نسبة جوهرية من حركتها بسبب بطء الكشف أو طول WAIT أو اعتماد تأكيد أبطأ من طبيعة الحركة، فيجب تصنيف ذلك كـOpportunity Response defect وليس كسلوك سوق عادي.

==================================================
16. A/B TESTING BEFORE ADOPTION
==================================================

أي تطوير جديد مثل:

- Supertrend.
- Short-term acceleration.
- Multi-timeframe scoring.
- Opportunity classification.
- Candidate pool expansion.
- **Fast opportunity re-evaluation / latency controls.**

يجب أولًا اختباره مقابل Baseline معروف.

المقارنة يجب أن تستخدم نفس:

- market data.
- time windows.
- capital assumptions.
- execution rules.

ولا يعتمد أي تعديل لمجرد أنه زاد عدد الصفقات.

**يجب أن يتضمن كل A/B test خاص بالـopportunity response مقارنة صريحة في:**

- Capture Rate.
- False Negative Rate.
- Detection / Decision / Execution latency.
- Average captured move.
- Net PnL after fees/slippage.
- Drawdown.
- Premature entries caused by acceleration sensitivity.

==================================================
17. DEVELOPMENT ORDER
==================================================

بعد انتهاء تجربة الـ$50 / 4H الحالية وتحليل نتائجها:

1. تحليل Market Movers والفرص الضائعة.
2. قياس Opportunity Capture Rate.
3. تحديد نقطة فقدان الفرصة داخل Universe → Eligibility → Rank → Profile → Decision → Entry.
4. قياس Detection / Decision / Execution latency لكل مرحلة.
5. بناء Multi-Timeframe evidence model.
6. إضافة Short-Term Momentum / Acceleration.
7. دراسة Opportunity Classification.
8. دراسة Fast Re-evaluation / Event-driven opportunity response.
9. تصميم Position Management يحافظ على الأرباح أثناء استمرار الـmomentum ويمنع الخروج المبكر غير المبرر.
10. دراسة Supertrend كـevidence مستقل.
11. إجراء A/B tests.
12. اعتماد القواعد النهائية فقط بعد إثباتها على نفس بيانات وخط أساس معروف.

==================================================
18. MANDATORY OPPORTUNITY RESPONSE ACCEPTANCE GATE
==================================================

لا تعتبر حزمة Opportunity Engine مكتملة أو قابلة للاعتماد النهائي ما لم تثبت الاختبارات، على بيانات تاريخية و/أو Forward/Paper معاد إنتاجها، الشروط التالية:

### A — Detection

يستطيع النظام اكتشاف الحركات المهمة داخل نافذة زمنية قصيرة بما يتوافق مع cadence التشغيل الفعلي.

### B — Response

بعد ظهور evidence كافٍ، لا يبقى النظام في انتظار غير محدود أو confirmation أبطأ من طبيعة الفرصة دون سبب موثق.

### C — Latency

كل مرحلة من Detection → Decision → Execution قابلة للقياس، وتوجد حدود قبول رقمية تُحدد بعد baseline measurement ولا تُترك ضمنية.

### D — Capture

يُقاس الجزء من الحركة القابلة للتداول الذي تم التقاطه فعليًا، وليس فقط ما إذا كانت الصفقة رابحة.

### E — Anti-Missed-Opportunity

تُسجل الفرص الكبيرة التي كانت قابلة للتداول ولم تُنفذ، مع السبب الدقيق، ويجب ألا تكون الأسباب المتكررة ناتجة عن WAIT غير محدود، Top-N churn، أو confirmation latency غير مبرر.

### F — Risk Preservation

أي تسريع في الاستجابة لا يجوز أن يحول النظام إلى مطاردة عمياء للحركات الممتدة. يجب أن تبقى liquidity, volatility, slippage, risk/reward وposition limits جزءًا من القرار.

### G — Exit Preservation

بعد الدخول في حركة قوية، يجب اختبار قدرة Position Management على عدم قتل الصفقة مبكرًا دون evidence كافٍ لانعكاس أو فقدان للزخم، مع حماية الأرباح المكتسبة.

**Failure of any item above = CHANGES REQUIRED.**

==================================================
19. ACCEPTANCE LANGUAGE
==================================================

يُمنع في وثائق الاعتماد استخدام عبارة عامة مثل "البوت سريع" أو "البوت لا يفوّت الفرص" دون قياس.

العبارة المقبولة يجب أن تكون قابلة للإثبات من trace وmetrics:

**ORION detected the opportunity, responded within the accepted latency envelope, entered only when risk constraints allowed, and captured a measurable portion of the tradable move.**

==================================================
END OF SPECIFICATION
==================================================
