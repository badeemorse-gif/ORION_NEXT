# ORION — FUTURE TRADING INTELLIGENCE CONTRACTS

الإصدار: 1.2
الحالة: DESIGN BASELINE — NOT WIRED

## 1. الغرض

هذه الوثيقة تثبت حدود العقود المستقبلية اللازمة لبناء:

1. Scalping Opportunity Engine
2. Independent Explosive Watchlist
3. فصل ORION Intelligence عن Trading Bot لاحقًا

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

## 3. Opportunity Evaluation boundary

العقد المستقبلي هو `models.opportunity_evaluation.OpportunityEvaluation`.

يمثل نتيجة تقييم مرشح Opportunity من محرك مستقبلي، وليس استراتيجية ترتيب أو قرار تنفيذ.

القاعدة الحرجة:

> لا يمكن لمحرك مستقبلي أن يعلن Opportunity كـ`ACCEPTED` إذا كانت `Opportunity.is_eligible` = false.

أما المرشح المرفوض فيجب أن يحمل سببًا واحدًا على الأقل حتى تبقى نتيجة الاستبعاد قابلة للتفسير.

هذا العقد لا يفرض ranking formula أو threshold رقميًا؛ تلك القرارات مؤجلة إلى Intelligence Engine بعد توفر الأدلة والـbacktesting المناسبة.

## 4. Explosive Watchlist

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

## 5. Trading Bot boundary

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

### Opportunity Evaluation

- eligible opportunity → accepted
- ineligible opportunity → cannot be accepted
- rejected evaluation → requires reason
- rejection reason is preserved
- naive evaluation timestamp → rejected

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
