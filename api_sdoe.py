"""
SDOE API Endpoints
==================

FastAPI router for Strong Dip Opportunity Engine.

Endpoints:
- GET  /api/strategies/strong-dip/today         - Today's opportunities
- GET  /api/strategies/strong-dip/watchlist     - Watchlist candidates
- GET  /api/strategies/strong-dip/rejected      - Rejected candidates
- GET  /api/strategies/strong-dip/:symbol/explain - Detailed explanation
- GET  /api/strategies/strong-dip/status        - Scanner status
- POST /api/strategies/strong-dip/scan          - Trigger manual scan
- GET  /api/strategies/strong-dip/filter        - Filter opportunities
"""
import logging
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from config import settings

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(
    prefix="/api/strategies/strong-dip",
    tags=["SDOE - Strong Dip Opportunities"],
)


# ══════════════════════════════════════════════════════════════════════════════
#  RESPONSE MODELS
# ══════════════════════════════════════════════════════════════════════════════

class SDOEScoreBreakdown(BaseModel):
    decline: int
    quality: int
    stabilization: int
    recovery: int
    market: int
    upside_bonus: int


class SDOETradeParams(BaseModel):
    entry_zone: List[float]
    stop_loss: float
    target_1: float
    target_2: float
    risk_reward_ratio: float


class SDOESignalResponse(BaseModel):
    symbol: str
    exchange: str = "NSE"
    strategy: str = "SDOE"
    total_score: int
    category: str
    score_breakdown: SDOEScoreBreakdown
    trade_params: SDOETradeParams
    holding_horizon: str
    is_approved: bool
    selection_reasons: List[str]
    rejection_reasons: List[dict]
    risk_factors: List[str]
    analyzed_at: str
    
    class Config:
        from_attributes = True


class ScanStatusResponse(BaseModel):
    has_data: bool
    last_scan: Optional[dict] = None
    cache_age_minutes: Optional[float] = None
    is_cache_fresh: bool
    counts: dict


class TodayOpportunitiesResponse(BaseModel):
    strong_buy: List[dict]
    watchlist: List[dict]
    monitor: List[dict]
    scan_status: dict


# ══════════════════════════════════════════════════════════════════════════════
#  DEPENDENCY INJECTION
# ══════════════════════════════════════════════════════════════════════════════

def get_sdoe_scanner():
    """Get SDOE scanner instance"""
    try:
        from services.sdoe_scanner import get_sdoe_scanner
        return get_sdoe_scanner()
    except Exception as e:
        logger.error(f"Failed to get SDOE scanner: {e}")
        raise HTTPException(status_code=500, detail="SDOE scanner unavailable")


# ══════════════════════════════════════════════════════════════════════════════
#  ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/status")
async def get_sdoe_status():
    """
    Get SDOE scanner status and statistics.
    
    Returns current scan status, cache freshness, and opportunity counts.
    """
    scanner = get_sdoe_scanner()
    return scanner.get_scan_status()


@router.get("/today", response_model=TodayOpportunitiesResponse)
async def get_today_opportunities():
    """
    Get today's SDOE opportunities.
    
    Returns strong buy, watchlist, and monitor candidates from the latest scan.
    Results are cached and refreshed periodically.
    """
    scanner = get_sdoe_scanner()
    
    opportunities = scanner.get_today_opportunities()
    status = scanner.get_scan_status()
    
    return TodayOpportunitiesResponse(
        strong_buy=opportunities.get("strong_buy", []),
        watchlist=opportunities.get("watchlist", []),
        monitor=opportunities.get("monitor", []),
        scan_status=status,
    )


@router.get("/strong-buy")
async def get_strong_buy_candidates():
    """
    Get strong buy candidates (score >= 80).
    
    These are the highest-conviction SDOE opportunities with:
    - Attractive decline (5-20%)
    - Strong underlying quality
    - Clear stabilization evidence
    - Early recovery signals
    """
    scanner = get_sdoe_scanner()
    return {
        "count": len(scanner.get_strong_buy()),
        "candidates": scanner.get_strong_buy(),
    }


@router.get("/watchlist")
async def get_watchlist_candidates():
    """
    Get watchlist candidates (score 65-79).
    
    These stocks show potential but need more confirmation:
    - May be in early stages of stabilization
    - Could move to strong buy on further recovery
    """
    scanner = get_sdoe_scanner()
    return {
        "count": len(scanner.get_watchlist()),
        "candidates": scanner.get_watchlist(),
    }


@router.get("/rejected")
async def get_rejected_candidates(
    limit: int = Query(50, ge=1, le=200, description="Max records to return"),
):
    """
    Get rejected candidates with reasons.
    
    See why stocks were not selected - useful for understanding
    the strategy criteria and monitoring potential future candidates.
    """
    scanner = get_sdoe_scanner()
    rejected = scanner.get_rejected()
    
    return {
        "count": len(rejected),
        "showing": min(limit, len(rejected)),
        "candidates": rejected[:limit],
    }


@router.get("/{symbol}/explain")
async def explain_symbol(symbol: str):
    """
    Get detailed explanation for a symbol.
    
    Returns comprehensive analysis of why a symbol was selected or rejected,
    including score breakdown, key factors, and risk assessment.
    
    Args:
        symbol: Stock symbol (e.g., "RELIANCE")
    """
    scanner = get_sdoe_scanner()
    
    try:
        explanation = await scanner.explain_symbol(symbol.upper())
        return explanation
    except Exception as e:
        logger.error(f"Failed to explain {symbol}: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.get("/filter")
async def filter_opportunities(
    min_score: int = Query(None, ge=0, le=100, description="Minimum score"),
    max_score: int = Query(None, ge=0, le=100, description="Maximum score"),
    sector: str = Query(None, description="Filter by sector (e.g., 'Banking', 'IT')"),
    holding_horizon: str = Query(None, description="Holding period: '5-20 days', '20-45 days', '45-90 days'"),
    min_decline_pct: float = Query(None, ge=0, le=100, description="Min decline % from 60d high"),
    max_decline_pct: float = Query(None, ge=0, le=100, description="Max decline % from 60d high"),
):
    """
    Filter SDOE opportunities with custom criteria.
    
    Combine multiple filters to find specific opportunities.
    """
    scanner = get_sdoe_scanner()
    
    filtered = scanner.filter_opportunities(
        min_score=min_score,
        max_score=max_score,
        sector=sector,
        holding_horizon=holding_horizon,
        min_decline_pct=min_decline_pct,
        max_decline_pct=max_decline_pct,
    )
    
    return {
        "count": len(filtered),
        "filters_applied": {
            "min_score": min_score,
            "max_score": max_score,
            "sector": sector,
            "holding_horizon": holding_horizon,
            "min_decline_pct": min_decline_pct,
            "max_decline_pct": max_decline_pct,
        },
        "candidates": filtered,
    }


@router.post("/scan")
async def trigger_scan(
    force_refresh: bool = Query(False, description="Force refresh even if cache is fresh"),
):
    """
    Trigger a manual SDOE scan.
    
    This will scan the stock universe for opportunities.
    Results are cached for future API calls.
    
    NOTE: This can take 1-5 minutes depending on universe size.
    In production, scanning is typically scheduled (e.g., daily at market open).
    """
    scanner = get_sdoe_scanner()
    
    try:
        result = await scanner.scan_universe(force_refresh=force_refresh)
        return {
            "success": True,
            "message": "Scan completed successfully",
            "result": result.to_dict(),
        }
    except Exception as e:
        logger.error(f"SDOE scan failed: {e}")
        raise HTTPException(status_code=500, detail=f"Scan failed: {str(e)}")


@router.get("/config")
async def get_sdoe_config():
    """
    Get current SDOE configuration thresholds.
    
    Returns the scoring weights and filter thresholds currently in use.
    """
    from strategies.strong_dip import SDOE_CONFIG
    
    return {
        "config": SDOE_CONFIG,
        "classification_thresholds": {
            "strong_buy": SDOE_CONFIG.get("score_strong_buy", 80),
            "watchlist": SDOE_CONFIG.get("score_watchlist", 65),
            "monitor": SDOE_CONFIG.get("score_monitor", 50),
        },
        "scoring_weights": {
            "decline": {"weight": SDOE_CONFIG.get("weight_decline", 20), "max_score": 20},
            "quality": {"weight": SDOE_CONFIG.get("weight_quality", 25), "max_score": 25},
            "stabilization": {"weight": SDOE_CONFIG.get("weight_stabilization", 20), "max_score": 20},
            "recovery": {"weight": SDOE_CONFIG.get("weight_recovery", 15), "max_score": 15},
            "market_sector": {"weight": SDOE_CONFIG.get("weight_market_sector", 10), "max_score": 10},
            "upside_bonus": {"weight": SDOE_CONFIG.get("weight_upside_bonus", 10), "max_score": 10},
        },
    }


# ══════════════════════════════════════════════════════════════════════════════
#  SECTOR SUMMARY
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/by-sector")
async def get_opportunities_by_sector():
    """
    Get opportunities grouped by sector.
    
    Useful for sector-based analysis and diversification.
    """
    scanner = get_sdoe_scanner()
    
    opportunities = scanner.get_today_opportunities()
    
    # Group by sector
    by_sector = {}
    
    for category in ["strong_buy", "watchlist", "monitor"]:
        for signal in opportunities.get(category, []):
            quality = signal.get("quality_metrics", {})
            sector = quality.get("sector", "Other")
            
            if sector not in by_sector:
                by_sector[sector] = {
                    "sector": sector,
                    "strong_buy": [],
                    "watchlist": [],
                    "monitor": [],
                    "total_count": 0,
                }
            
            by_sector[sector][category].append({
                "symbol": signal.get("symbol"),
                "score": signal.get("total_score"),
                "decline_pct": signal.get("decline_metrics", {}).get("decline_from_60d_pct", 0),
            })
            by_sector[sector]["total_count"] += 1
    
    # Sort sectors by opportunity count
    sectors = sorted(by_sector.values(), key=lambda x: x["total_count"], reverse=True)
    
    return {
        "sector_count": len(sectors),
        "sectors": sectors,
    }


# ══════════════════════════════════════════════════════════════════════════════
#  BACKTEST / RESEARCH SUPPORT
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/backtest")
async def run_backtest(
    symbols: List[str] = Query(default=[], description="Symbols to backtest"),
    lookback_days: int = Query(60, ge=30, le=365, description="Days of history"),
    min_score: int = Query(65, ge=0, le=100, description="Min score threshold"),
):
    """
    Run SDOE backtest on historical data.
    
    Analyzes how SDOE signals would have performed historically.
    
    NOTE: This is a placeholder - full backtest implementation requires
    historical data storage and more complex analysis.
    """
    
    # This is a placeholder for the full backtest implementation
    # In a production system, this would:
    # 1. Load historical OHLCV data for each symbol
    # 2. Simulate SDOE signals at each date
    # 3. Track simulated trades and outcomes
    # 4. Calculate performance metrics
    
    return {
        "status": "pending",
        "message": "Backtest functionality is under development",
        "parameters": {
            "symbols": symbols,
            "lookback_days": lookback_days,
            "min_score": min_score,
        },
        "note": "Full backtest implementation requires historical data infrastructure"
    }


# ══════════════════════════════════════════════════════════════════════════════
#  REGISTRATION HELPER
# ══════════════════════════════════════════════════════════════════════════════

def register_sdoe_routes(app, auth_dependency=None):
    """
    Register SDOE routes with the FastAPI app.
    
    Args:
        app: FastAPI application instance
        auth_dependency: Optional authentication dependency
    """
    # Add auth dependency to all routes if provided
    if auth_dependency:
        for route in router.routes:
            if hasattr(route, 'dependencies'):
                route.dependencies.append(Depends(auth_dependency))
    
    app.include_router(router)
    logger.info("✅ SDOE API routes registered")
