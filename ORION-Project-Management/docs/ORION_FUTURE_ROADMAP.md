# ORION — FUTURE ROADMAP

الإصدار: 1.3
الحالة: ACTIVE — FUTURE PLANNING ONLY
المشروع: ORION

==================================================
1. وظيفة الوثيقة
==================================================

هذه الوثيقة تحفظ الأهداف والمراحل الكبرى بعيدة المدى حتى لا تضيع أثناء التطوير الحالي.

لا تحدد المرحلة الحالية ولا الخطوة التالية.
المصدر الوحيد لذلك هو ORION_PROJECT_STATE.md وORION_ROADMAP.md.

==================================================
2. الهدف التشغيلي الرئيسي
==================================================

**Scalping Opportunity Engine** هو الهدف التشغيلي الرئيسي لـ ORION.

الهدف هو ترشيح أفضل الفرص القريبة للسكالبينج بصورة منهجية وقابلة للتفسير والاختبار والتتبع.

==================================================
3. المراحل الكبرى المستقبلية
==================================================

### A — Core Intelligence Completion

استكمال قلب ORION التحليلي وتثبيت سلوكه قبل بناء المستهلكين الأعلى.

### B — Scalping Opportunity Engine

تحويل Core Intelligence إلى Ranked Opportunities قابلة للتفسير، مع Confidence وRisk Context وRejection Reasons.

### C — Desktop Application / GUI

تحويل ORION إلى برنامج مكتبي احترافي للاستخدام اليومي.

GUI واجهة عرض وتحكم فقط، وليست مكان Business Logic.

### D — Pre-Explosion / Explosive Coin Radar

قائمة مستقلة تتحدث باستمرار لرصد العملات التي تظهر مقدمات سوقية قد تسبق حركة انفجارية.

لا تستبدل هذه الميزة قائمة فرص السكالبينج ولا تدعي التنبؤ المؤكد.

### E — Trading Bot / Paper Execution

بناء طبقة التداول الآلي بعد استقرار Core وScalping Engine.

تبدأ بـ Paper Trading:

Signal
↓
Decision
↓
ExecutionPlan
↓
Risk Checks
↓
Paper Execution
↓
Position Management
↓
Exit
↓
Audit / Report

### F — Backtesting / Replay / Validation

اختبار المنهج تاريخيًا وإعادة تشغيل السيناريوهات وقياس الأداء والمخاطر والتنفيذ.

### G — Live Trading Readiness

Security + Risk Limits + Emergency Stop + Audit + Monitoring + Paper Validation + Operational Verification.

### H — Production ORION

الصورة النهائية المتكاملة:

Desktop Application
↓
Market Scanner
↓
Scalping Opportunity Engine
↓
Independent Explosive Coin Radar
↓
Decision / Risk Management
↓
Paper / Approved Live Execution
↓
Position Management
↓
Reports / Audit / Monitoring

==================================================
4. قواعد حماية المستقبل
==================================================

- لا تنفذ مرحلة مستقبلية مبكرًا لمجرد وجودها هنا.
- لا تعاد كتابة مكونات مثبتة فقط لخدمة ميزة مستقبلية دون ضرورة معمارية موثقة.
- أي متطلب مستقبلي يؤثر فعليًا على Contract حالي يجب أن يظهر أولًا كقرار معماري واضح.
- Explosion Radar يظل مستقلًا عن Scalping Opportunity Engine.
- Trading Bot لا يبدأ Live Trading لمجرد اكتمال الكود.
- GUI لا تصبح مركز النظام.

==================================================
5. TREND / VOLATILITY HARVESTER — FUTURE SATELLITE PROJECT
==================================================

**الحالة:** FUTURE ONLY — NO CURRENT DEVELOPMENT

هذه الخاصية/الاستراتيجية لا تُضاف إلى ORION_NEXT الأساسي أثناء مرحلة إكماله الحالية، ولا تُغير عقوده أو معماريته أو مساره التشغيلي.

بعد اعتماد ORION_NEXT نهائيًا، وتشغيله فعليًا على الكمبيوتر واجتياز التجارب الورقية وقرار الإدارة بأن النظام الأساسي جاهز للعمل الحقيقي، يُفتح مشروع مستقل أو Satellite Strategy باسم مبدئي:

`ORION_TREND_HARVESTER`

### الهدف

نظام متخصص للعملات التي يختارها المشغل يدويًا عندما تدخل **Explosive Trend / High-Volatility Trend Regime**، بدل تشغيل الكون الكامل للنظام الأساسي عليها.

المقصود ليس بناء Grid Bot تقليدي بحدود سعرية ثابتة، بل استغلال التذبذب الداخلي داخل اتجاه قوي مع حماية رأس المال.

### التشغيل

المشغل يحدد رمزًا واحدًا أو عدة رموز مستهدفة.

النظام يركز فقط على الرموز المختارة، ولا يشارك في Dynamic Universe ranking الخاص بـORION الأساسي.

الهدف المعماري هو السماح بسرعة استجابة أعلى من النظام الأساسي، باستخدام طبقة مراقبة قصيرة الأجل وقرارات على مستوى الشموع عندما يكون ذلك مناسبًا.

### Regime Activation

لا يعمل النظام بكامل نشاطه لمجرد وجود رمز مختار.

يفعّل **Harvesting Mode** فقط عند وجود أدلة متضافرة مثل:

- Trend Regime صالح.
- Momentum / Acceleration.
- Volume Expansion.
- Range / ATR Expansion.
- Breakout أو Reclaim أو Pullback Continuation.
- Market Structure متوافقة.

المؤشرات المفردة، بما فيها Supertrend، تبقى Evidence وليست سلطة BUY/SELL منفردة.

### Core Position + Trading Inventory

التصميم المستهدف يفصل التعرض إلى مكوّنين:

```text
Core Position
+
Trading Inventory
```

الـCore يهدف إلى البقاء مع الاتجاه وعدم الخروج الكامل بسبب Pullback عابر.

الـTrading Inventory مخصص للتدوير الديناميكي داخل التذبذب:

```text
Impulse
↓
Scale / Harvest
↓
Pullback
↓
Rebuild Inventory
↓
Re-expansion
↓
Scale / Harvest
```

يجب ألا يتحول Pullback واحد إلى Liquidation كامل للـCore Position.

### سرعة الإشارة

لأن المشغل يختار الرموز مسبقًا، يمكن للنظام المستقبلي تخصيص موارد المراقبة لها فقط واستخدام timeframes قصيرة مثل:

```text
1m / 3m / 5m / 15m
```

مع إمكان الاستفادة من WebSocket مباشر وطبقات Micro-Structure / Acceleration / Volume Burst / Pullback Reclaim.

السرعة هنا **نتيجة لتضييق نطاق الرصد والتخصص**، وليست مجرد خفض thresholds عشوائيًا.

### Persistent State / Restart Continuity

يجب ألا يتعامل Trend Harvester بعد إعادة التشغيل مع الرمز كما لو أنه يراه للمرة الأولى.

التصميم المستهدف يحافظ على **Persistent Strategy State** منفصلًا عن بيانات الشموع الخام، بحيث يمكن بعد Restart استعادة:

```text
Last Processed Event / Candle
Historical Context Required by the Strategy
Active Regime State
Core Position State
Trading Inventory State
Pending Strategy Intent
Protected Profit / Trailing State
```

عند التشغيل الطبيعي:

```text
Load durable strategy state
↓
Load only the recent market history required to re-establish context
↓
Reconcile with live market stream
↓
Resume from the last durable event boundary
```

ولا يُفترض إعادة تحليل كامل السوق التاريخي من الصفر في كل Restart.

في المقابل، إذا لم يوجد state محفوظ سابقًا، يبدأ النظام بمرحلة **initial context warm-up** قبل السماح بالـHarvesting الكامل.

يجب أن تكون إعادة التشغيل:

```text
Idempotent
Replay-safe
No duplicate entry
No duplicate harvest
No duplicate release
```

ويجب أن يبقى Position / Core / Inventory state قابلًا للاستعادة حتى لو حدث توقف بين قرارات أو أوامر مرحلية.

### حدود المسؤولية

المشروع المستقبلي يجب أن يبقى منفصلًا عن:

- ORION Core Opportunity Engine.
- D1 Opportunity semantics.
- D6 Capital / Accounting semantics.
- D4/D5 lifecycle.
- Trading Control authority.

وأي إعادة استخدام لمكونات ORION تكون عبر Contracts واضحة، لا عبر نسخ منطق داخلي.

### تشغيل المنتج

الهدف المستقبلي هو أن يختار المشغل بين:

```text
ORION Core
```

أو:

```text
ORION Trend Harvester
```

للفترة/الأصول المستهدفة وفق سياسة تشغيل واضحة.

لا يُفترض تشغيل الاستراتيجيتين على نفس رأس المال لنفس الرمز في نفس اللحظة إلا بعد تعريف Portfolio Arbitration Contract مستقل.

### القياس قبل الاعتماد

لا يعتمد النظام المستقبلي لمجرد أنه يستطيع التقاط حركات كثيرة.

يجب قياس:

- Capture of intra-trend swings.
- Realized P&L.
- Net P&L after fees/slippage.
- Maximum Drawdown.
- Core retention rate.
- Inventory turnover.
- False exits.
- Missed continuation.
- Recovery stability.
- Opportunity-to-entry latency.

### قاعدة حاكمة

```text
ORION_NEXT الأساسي لا يتغير بسبب Trend Harvester.
Trend Harvester هو Satellite Strategy مستقلة.
```

لا يبدأ أي تطوير لهذه المرحلة قبل اكتمال واعتماد ORION_NEXT الأساسي كما هو محدد في بوابات المشروع.

==================================================
6. علاقة هذه الوثيقة بالتنفيذ
==================================================

ORION_ROADMAP.md
→ ما يتم تنفيذه الآن وبأي ترتيب.

ORION_PROJECT_STATE.md
→ أين نحن الآن.

ORION_FUTURE_ROADMAP.md
→ إلى أين نريد أن نصل.

وجود هذه الوثيقة لا يفرض على المطور أي تغيير في المرحلة الحالية.

==================================================
END
==================================================
