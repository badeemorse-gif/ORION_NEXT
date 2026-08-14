# ORION — FUTURE TRADING INTELLIGENCE CONTRACTS

الإصدار: 1.3
الحالة: DESIGN BASELINE — NOT WIRED

هذه الوثيقة تثبت حدود العقود المستقبلية اللازمة لبناء Scalping Opportunity Engine وIndependent Explosive Watchlist وTradingReadiness. العقود لا تدخل في المسار الحالي Analysis → Profile → Score → Decision → Execution.

القواعد المقررة تشمل أن Opportunity confidence يأتي فقط من `ProfileResult.TimeframeProfile.confidence` للـtimeframe المطلوب، وأن `AnalysisResult.strength` لا يُعاد تفسيره كـOpportunity confidence، ولا توجد aggregation formula أو ranking thresholds أو synthetic forecast قبل توفر أدلة Core المناسبة.

Status: DESIGN BASELINE — NOT WIRED
