# ORION — FUTURE TRADING INTELLIGENCE CONTRACTS

الإصدار: 1.0
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

لا يجوز أن تؤثر نتيجة Explosive Watchlist في ترتيب أو صلاحية Scalping Opportunities، ولا تدخل Score أو Decision الحالي.

## 4. Trading Bot boundary

الطبقة المستقبلية يجب أن تبقى منفصلة عن ORION Intelligence:

ORION Intelligence
↓
Opportunity
↓
Future Risk / Validation Gate
↓
Bot Decision
↓
Order Execution

العقود الحالية لا تحتوي أوامر Binance ولا مفاتيح API ولا live-trading wiring.

قبل السماح لبوت مستقبلي بالتنفيذ يجب أن تكون intelligence مكتملة وغير منتهية، والمخاطر مقبولة، والسياق صالحًا. أي فشل في هذه الشروط يجب أن يمنع التنفيذ بدل تحويل نقص المعلومات إلى قرار تداول.

## 5. Dependencies المؤجلة

لا يُفترض الآن شكل thresholds أو ranking formula أو signal weights أو estimated time model؛ هذه تحتاج أدلة Core Intelligence وبيانات تاريخية/backtesting مناسبة.

لا يتم ربط هذه العقود بالـpipeline الحالي حتى تُغلق Phase 2 وتثبت المدخلات التي يحتاجها Opportunity Engine فعليًا.

## 6. الاختبارات

العقود تختبر:

- valid opportunity
- incomplete intelligence
- stale / expired opportunity
- invalid confidence / non-finite values
- valid explosive candidate
- incomplete explosive candidate
- stale explosive candidate
- invalid probabilistic values

الاختبارات تثبت سلامة العقد فقط ولا تدعي صحة استراتيجية تداول لم تُبنَ بعد.

## 7. قاعدة الاستقلال

أي تطوير لاحق لهذه الطبقات يجب أن يستهلك العقود الحالية دون إعادة تصميم العقود المستقرة في Core إلا بقرار معماري مستقل.
