# ORION — Scalping Opportunity Optimization Specification

الإصدار: 1.0
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

الهدف هو الإجابة عن السؤال:

**لماذا لم يدخل ORION هذه العملة؟**

دون تخمين.

==================================================
15. CURRENT OBSERVATION / DESIGN FINDING
==================================================

التجربة الحالية أظهرت أن D1 يستطيع اكتشاف فرص مرتفعة الترتيب، بينما قد تمنع طبقات Decision/Context الدخول لاحقًا.

لا يعتبر هذا فشلًا بحد ذاته قبل تحليل السبب.
لكنه Finding يجب اختباره منهجيًا.

كما أن الاعتماد على 31 شمعة يومية لاستخراج trend/momentum الرئيسي وحده قد يكون بطيئًا بالنسبة لفرص Scalping قصيرة الأجل.

هذه الوثيقة تعتمد Multi-Timeframe model بدل استخدام الـ1D كـTrend Gate.

==================================================
16. A/B TESTING BEFORE ADOPTION
==================================================

أي تطوير جديد مثل:

- Supertrend.
- Short-term acceleration.
- Multi-timeframe scoring.
- Opportunity classification.
- Candidate pool expansion.

يجب أولًا اختباره مقابل Baseline معروف.

المقارنة يجب أن تستخدم نفس:

- market data.
- time windows.
- capital assumptions.
- execution rules.

ولا يعتمد أي تعديل لمجرد أنه زاد عدد الصفقات.

==================================================
17. DEVELOPMENT ORDER
==================================================

بعد انتهاء تجربة الـ$50 / 4H الحالية وتحليل نتائجها:

1. تحليل Market Movers والفرص الضائعة.
2. قياس Opportunity Capture Rate.
3. تحديد نقطة فقدان الفرصة داخل Universe → Eligibility → Rank → Profile → Decision → Entry.
4. بناء Multi-Timeframe evidence model.
5. إضافة Short-Term Momentum / Acceleration.
6. دراسة Opportunity Classification.
7. دراسة Supertrend كـevidence مستقل.
8. ضبط Candidate Pool / Active Trading Set.
9. A/B Test مقابل Baseline.
10. Full Verification.
11. Paper Forward Test جديد.
12. اعتماد النتيجة قبل أي Live Trading.

==================================================
18. GOVERNANCE
==================================================

لا يبدأ تنفيذ هذه النقاط أثناء تجربة الـ$50 / 4H الحالية.

التجربة الحالية يجب أن تكتمل دون تعديل الكود حتى تبقى Baseline صالحة للتحليل.

بعد وصول Final Results:

**GPT يراجع النتائج أولًا، ثم يصدر تكليف التطوير.**

لا يتم استنتاج نجاح أو فشل التعديلات قبل الاختبار.

==================================================
END
==================================================
