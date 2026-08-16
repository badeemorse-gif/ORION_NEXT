# ORION — FUTURE TRADING INTELLIGENCE CONTRACTS

الإصدار: 1.2
الحالة: DESIGN BASELINE — NOT WIRED

## 1. الغرض

هذه الوثيقة تثبت حدود العقود المستقبلية اللازمة لبناء:

1. Scalping Opportunity Engine
2. Independent Explosive Watchlist
3. فصل ORION Intelligence عن Trading Bot لاحقًا
4. Experimental Trading Bot مع تتبع دورة حياة الصفقة واستعادة الحالة بعد إعادة التشغيل

العقود هنا لا تغيّر المسار الحالي ولا تدخل في Analysis → Profile → Score → Decision → Execution.

## 2. Scalping Opportunity

العقد المستقبلي هو `models.opportunity.Opportunity`.

يمثل فرصة قريبة قابلة للتفسير، وليس أمر تداول.

يحتوي عند الحاجة على:

- symbol / timeframe / direction
- entry candidate
- confidence / setup quality
- risk state + invalidation
- expected move
- supporting evidence
- market context
- freshness
- status / expiry

الحد الأدنى للجاهزية المستقبلية هو اكتمال البيانات الأساسية، freshness معروفة، risk state معروف، ووجود evidence. ولا توجد thresholds رقمية للسكالبينج داخل العقد؛ thresholds والتصنيف يجب أن تأتي من Intelligence Engine عندما تتوفر أدلة Core المناسبة.

`is_eligible` بوابة عقدية محافظة فقط: ACTIVE + FRESH + ACCEPTABLE risk + complete intelligence. وهي ليست قرار شراء/بيع ولا ExecutionPlan.

## 3. Explosive Watchlist

العقد المستقبلي هو `models.explosive_watchlist.ExplosiveWatchCandidate`.

وهو مستقل تمامًا عن Scalping Opportunity.

يمثل **probabilistic estimate** لاحتمال حركة قوية مستقبلية، وليس وعدًا أو prediction مؤكدة.

يحتوي عند الحاجة على:

- symbol / timeframe window
- move probability
- readiness score
- confidence
- freshness
- supporting signals
- invalidation conditions
- estimated time window
- status / expiry

`is_monitorable` بوابة عقدية محافظة فقط: MONITOR + FRESH + complete evidence package. وهي لا تعني أن الحركة ستحدث، ولا تنتج أمر تداول.

لا يجوز أن تؤثر نتيجة Explosive Watchlist في ترتيب أو صلاحية Scalping Opportunities، ولا تدخل Score أو Decision الحالي.

## 4. Trading Bot boundary

العقد المستقبلي لبوابة البوت هو `models.trading_readiness.TradingReadiness`.

الطبقة المستقبلية يجب أن تبقى منفصلة عن ORION Intelligence:

ORION Intelligence
↓
Opportunity
↓
TradingReadiness
↓
Bot Decision
↓
Order Execution

`TradingReadiness` بوابة معلوماتية **fail-closed**. لا تحتوي أوامر Binance ولا مفاتيح API ولا live-trading wiring.

لا تكون البوابة `eligible` إلا إذا تحققت جميع الشروط الإلزامية:

- intelligence complete
- confidence acceptable
- opportunity fresh
- risk acceptable
- market conditions valid

أي شرط غير متحقق يمنع الأهلية. وجود `Opportunity` وحده لا يمنح صلاحية تنفيذ.

## 5. Experimental Trading Bot — Trade Lifecycle & 1-Second Tracking

هذه طبقة مستقبلية مستقلة مخصصة **للبوت التجريبي فقط**، وتُبنى downstream من `TradingReadiness` ولا تُضاف إلى Core Intelligence أو ProfileIntelligence أو Opportunity كـintelligence timeframe.

المسار التصميمي:

ORION Intelligence
↓
Opportunity
↓
TradingReadiness
↓
Experimental Trading Bot
↓
Trade Lifecycle Journal
↓
1-second Market Tracking
↓
Exit Event
↓
Trade Outcome / Duration / P&L

### 5.1 الدقة الزمنية

**1-second resolution هي الحد الأدنى المعتمد لتتبع دورة حياة الصفقة في البوت التجريبي.**

الهدف هو أن يستطيع البوت، بعد عودة التشغيل، تحديد أحداث الصفقة حتى مستوى الثانية، مثل:

- `entry_time`
- `exit_time`
- مدة الصفقة بالثانية
- حالة الصفقة
- سبب الخروج
- نتيجة الصفقة / P&L

لا يُسمح باستخدام فريم أكبر من 1 ثانية كمصدر الدقة الأساسي لتحديد دورة حياة الصفقة عندما تكون دقة الثانية مطلوبة؛ الفريمات الأكبر تفقد تفاصيل زمنية داخل الشمعة.

هذه القاعدة لا تعني أننا نحتاج إلى تحليل ترتيب أحداث داخل نفس الثانية. مستوى الدقة المطلوب هو **الثانية نفسها**، وهي الحد الأدنى المقبول للمشروع التجريبي.

### 5.2 Trade Lifecycle Journal

يجب أن يمتلك البوت سجلًا دائمًا للصفقات، ولا يعتمد على بقاء العملية أو الجهاز مفتوحًا.

عند إنشاء الصفقة يُحفظ على الأقل:

- symbol
- side
- quantity
- entry_price
- entry_time
- initial trade status
- stop/take-profit parameters إن وُجدت ضمن عقد البوت

وعند الإغلاق يُحفظ:

- exit_price
- exit_time
- exit_reason
- execution status
- realized P&L
- duration_seconds

ويجب أن يبقى السجل قابلًا للقراءة بعد إغلاق التطبيق أو الجهاز.

### 5.3 Restart / Recovery

عند إعادة تشغيل الجهاز بينما توجد صفقة لم تُغلق في السجل:

1. يسترجع البوت آخر trade record مفتوح.
2. يقرأ `entry_time` والحالة المحفوظة.
3. يستعيد بيانات السوق ذات الدقة الزمنية المطلوبة من لحظة الدخول حتى نقطة الاسترداد.
4. يعيد تحديد حالة الصفقة حتى مستوى الثانية.
5. يثبت `exit_time` و`exit_reason` و`duration_seconds` وP&L عند توفر الأدلة.

لا يجوز افتراض أن الصفقة أُغلقت أو اختراع نتيجة عند غياب الأدلة.

إذا كانت بيانات الاسترداد غير كافية لإثبات الحالة، فالنتيجة تكون حالة recovery صريحة مثل `UNKNOWN` أو `INCOMPLETE` بحسب العقد النهائي، مع **fail-closed** وعدم اختلاق P&L أو مدة أو سبب خروج.

### 5.4 الفصل عن Intelligence

هذه الطبقة:

- تستهلك نتائج ORION ولا تعيد توليد intelligence.
- لا تغير `DecisionResult`.
- لا تغير `ScoreResult`.
- لا تغير `Opportunity` semantics.
- لا تجعل 1-second timeframe شرطًا داخل `ProfileIntelligence`.
- لا تعيد تعريف `ExecutionPlan`.

`1s` هنا هو **Trade Tracking Resolution** وليس **Intelligence Timeframe**.

### 5.5 حدود التنفيذ

في المرحلة التصميمية الحالية لا يوجد live trading wiring مطلوب داخل هذا العقد.

أي اتصال لاحق بـBinance أو execution adapter يجب أن يكون خلف contract مستقل، مع بقاء Trade Journal والاسترداد قابلين للاختبار دون Live Exchange I/O.

### 5.6 الاختبارات المستقبلية المطلوبة

يجب أن تغطي طبقة البوت عند تنفيذها:

- إنشاء trade record عند الدخول.
- حفظ `entry_time` بدقة الثانية.
- تسجيل الخروج وحفظ `exit_time`.
- حساب `duration_seconds` من timestamps الفعلية.
- حفظ P&L وexit reason.
- إغلاق وإعادة تشغيل البوت مع صفقة مفتوحة.
- استعادة الصفقة من السجل الدائم.
- إعادة بناء الحالة من بيانات 1s.
- missing recovery data → UNKNOWN/INCOMPLETE fail-closed.
- عدم تعديل ORION intelligence semantics أثناء recovery.
- عدم الخلط بين `export_success` أو نجاح persistence وبين نجاح الصفقة أو الـpipeline.

## 6. Dependencies المؤجلة

لا يُفترض الآن شكل thresholds أو ranking formula أو signal weights أو estimated time model؛ هذه تحتاج أدلة Core Intelligence وبيانات تاريخية/backtesting مناسبة.

لا يتم ربط هذه العقود بالـpipeline الحالي حتى تُغلق Phase 2 وتثبت المدخلات التي يحتاجها Opportunity Engine فعليًا.

## 7. الاختبارات

العقود تختبر:

### Opportunity

- valid opportunity
- incomplete intelligence
- stale / expired opportunity
- invalid confidence / non-finite values

### Explosive Watchlist

- valid probabilistic candidate
- incomplete candidate
- stale / expired candidate
- invalid probabilistic values

### TradingReadiness

- all gates valid → eligible
- incomplete intelligence → blocked
- low confidence → blocked
- stale opportunity → blocked
- unacceptable risk → blocked
- invalid market conditions → blocked
- non-boolean gate → rejected
- naive evaluation timestamp → rejected

الاختبارات تثبت سلامة العقد فقط ولا تدعي صحة استراتيجية تداول لم تُبنَ بعد.

## 8. قاعدة الاستقلال

أي تطوير لاحق لهذه الطبقات يجب أن يستهلك العقود الحالية دون إعادة تصميم العقود المستقرة في Core إلا بقرار معماري مستقل.

**قاعدة حاكمة:** أي تطوير للبوت التجريبي أو Trade Tracking أو 1-second recovery يجب أن يتم كطبقة مستقلة، مع المحافظة على عزل ORION Intelligence وعدم إدخال 1s ضمن required intelligence timeframes.