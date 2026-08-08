# ==========================================
# Badee Binance Scanner - Decision Engine V1.1
# Core Decision Making & Trade Controller
# ==========================================


def evaluate_decision(score_result, profile):
    """
    عقل المشروع (Decision Engine V1.1)
    يصدر قراراً استراتيجياً متوافقاً مع بروتوكول العقود الموحد (Contract Mapped).
    """
    score = score_result.get("score", 0)
    confidence = score_result.get("confidence", "50%")
    modules = score_result.get("modules", [])

    health_score = profile.get("health_score", 50)
    trade_mode = profile.get("trade_mode", "NEW_LISTING")

    # تجميع الأسباب، التحذيرات، والموانع المنظمة (Blocks)
    all_reasons = []
    all_warnings = []
    blocks = []

    for mod in modules:
        mod_name = mod.get("name", "Unknown")
        if mod.get("reason"):
            all_reasons.append({
                "type": "positive" if mod.get("passed", True) else "warning",
                "message": f"[{mod_name}] {mod['reason']}"
            })
        
        mod_warnings = mod.get("warnings", [])
        if mod_warnings:
            for w in mod_warnings:
                all_warnings.append({
                    "type": "warning",
                    "message": f"[{mod_name}] {w}"
                })

        # التحقق من الوحدات التي فشلت وتكوين كائن الحظر المنظم
        if not mod.get("passed", True):
            blocks.append({
                "engine": mod_name,
                "reason": mod.get("reason", "فشل في اجتياز شروط الوحدة")
            })

    # ==========================================
    # Decision Logic & Rules Controller
    # ==========================================
    
    # 1. حالة الرفض التام (REJECT)
    if health_score < 60 or (trade_mode == "NEW_LISTING" and score < 40):
        return _build_decision_response(
            decision="REJECT",
            decision_score=score,
            decision_priority=int(score),
            decision_version="1.1",
            risk_level="HIGH",
            entry_quality="F",
            reasons=all_reasons,
            warnings=all_warnings,
            blocks=blocks,
            recommendation="REJECT_TRADE"
        )

    # 2. فحص المخاطر
    has_high_risk = any("مخاطرة" in str(w) or "تشبع" in str(w) or "متضخم" in str(w) for w in all_warnings)

    # 3. اتخاذ القرار بناءً على النقاط والتحذيرات
    if score >= 85 and not has_high_risk and len(blocks) == 0:
        decision = "BUY"
        recommendation = "ENTRY_NOW"
        risk_level = "LOW"
        entry_quality = "A+" if score >= 92 else "A"

    elif score >= 75 and has_high_risk:
        decision = "WAIT"
        recommendation = "WAIT_PULLBACK"
        risk_level = "MEDIUM"
        entry_quality = "B+"

    elif score >= 65 and len(blocks) > 0:
        decision = "WAIT"
        recommendation = "WAIT_CONFIRMATION"
        risk_level = "MEDIUM"
        entry_quality = "B"

    elif score >= 55:
        decision = "WATCH"
        recommendation = "WATCHLIST"
        risk_level = "MEDIUM-HIGH"
        entry_quality = "C"

    else:
        decision = "SKIP"
        recommendation = "SKIP"
        risk_level = "HIGH"
        entry_quality = "D"

    # حساب أولوية القرار (Decision Priority) دمجاً بين النقاط وقوة التوصية
    priority_boost = 10 if recommendation == "ENTRY_NOW" else (5 if recommendation == "WAIT_PULLBACK" else 0)
    decision_priority = min(100, int(score + priority_boost))

    return _build_decision_response(
        decision=decision,
        decision_score=score,
        decision_priority=decision_priority,
        decision_version="1.1",
        risk_level=risk_level,
        entry_quality=entry_quality,
        reasons=all_reasons,
        warnings=all_warnings,
        blocks=blocks,
        recommendation=recommendation
    )


def _build_decision_response(
    decision,
    decision_score,
    decision_priority,
    decision_version,
    risk_level,
    entry_quality,
    reasons,
    warnings,
    blocks,
    recommendation
):
    """بناء القالب القياسي الموحد لنتيجة القرار النهائي (Contract Schema)"""
    return {
        "decision": decision,
        "decision_score": decision_score,
        "decision_priority": decision_priority,
        "decision_version": decision_version,
        "risk_level": risk_level,
        "entry_quality": entry_quality,
        "reasons": reasons,
        "warnings": warnings,
        "blocks": blocks,
        "recommendation": recommendation
    }