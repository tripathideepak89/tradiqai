"""
Dividend Radar Engine - Scoring Logic

Implements the scoring model for dividend candidates.

Specification (DRE – Dividend Radar Engine):
- Dividend Yield Score (0–25)
    > 5%  -> 25
    > 3%  -> 20
    > 2%  -> 10
    else  -> 0
- Consistency Score (0–20)
    dividend_paid_last_4_years -> 20
    3 years                    -> 15
    else                       -> 5
- Growth Score (0–15)
    dividend_growth_3yr > 10% -> 15
    else                      -> 5
- Financial Strength Score (0–20)
    ROE > 18%          -> +10
    debt_to_equity < 1 -> +10
- Technical Strength Score (0–20)
    price > 50DMA -> +10
    price > 200DMA -> +10

Additional filters:
- Dividend trap filter: if yield > 8% and price is in a downtrend, we
  aggressively penalize the score so such names are de‑prioritised.
"""
from typing import Dict, Any


class DividendScorer:
    @staticmethod
    def _get(candidate: Dict[str, Any], key: str, default: float = 0.0) -> float:
        value = candidate.get(key, default)
        try:
            return float(value) if value is not None else default
        except (TypeError, ValueError):
            return default

    @classmethod
    def score(cls, candidate: Dict[str, Any]) -> int:
        """
        Calculate the total dividend score for a candidate stock.

        Expected keys (all optional, sensible defaults used when missing):
        - yield_percent
        - years_dividend_history (int)
        - dividend_growth_3yr
        - roe
        - debt_to_equity
        - price
        - dma_20
        - dma_50
        - dma_200
        """
        # 1) Dividend Yield Score (0–25)
        dividend_yield = cls._get(candidate, "yield_percent")
        if dividend_yield > 5:
            yield_score = 25
        elif dividend_yield > 3:
            yield_score = 20
        elif dividend_yield > 2:
            yield_score = 10
        else:
            yield_score = 0

        # 2) Consistency Score (0–20)
        years_history = candidate.get("years_dividend_history")
        try:
            years_history = int(years_history) if years_history is not None else 0
        except (TypeError, ValueError):
            years_history = 0

        if years_history >= 4:
            consistency_score = 20
        elif years_history >= 3:
            consistency_score = 15
        elif years_history > 0:
            consistency_score = 5
        else:
            consistency_score = 0

        # 3) Growth Score (0–15)
        growth_3yr = cls._get(candidate, "dividend_growth_3yr")
        if growth_3yr > 10:
            growth_score = 15
        elif growth_3yr > 0:
            growth_score = 5
        else:
            growth_score = 0

        # 4) Financial Strength Score (0–20)
        roe = cls._get(candidate, "roe")
        debt_to_equity = cls._get(candidate, "debt_to_equity", default=0.0)
        financial_score = 0
        if roe > 18:
            financial_score += 10
        if 0 <= debt_to_equity < 1:
            financial_score += 10

        # 5) Technical Strength Score (0–20)
        price = cls._get(candidate, "price")
        dma_50 = cls._get(candidate, "dma_50")
        dma_200 = cls._get(candidate, "dma_200")

        technical_score = 0
        if price and dma_50 and price > dma_50:
            technical_score += 10
        if price and dma_200 and price > dma_200:
            technical_score += 10

        total_score = yield_score + consistency_score + growth_score + financial_score + technical_score

        # Dividend trap filter:
        # If yield is very high AND simple downtrend (price < 50DMA and 50DMA < 200DMA),
        # heavily penalise.
        is_downtrend = False
        if price and dma_50 and dma_200:
            is_downtrend = price < dma_50 and dma_50 < dma_200

        if dividend_yield > 8 and is_downtrend:
            # Cap such cases hard
            total_score = min(total_score, 35)

        # Ensure score is within 0–100 range
        total_score = max(0, min(int(round(total_score)), 100))
        return total_score


def classify_dividend_score(score: int) -> str:
    if score >= 80:
        return "Strong Buy Candidate"
    elif score >= 60:
        return "Watchlist"
    elif score >= 40:
        return "Moderate"
    else:
        return "Ignore"
