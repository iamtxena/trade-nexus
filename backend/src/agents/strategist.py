"""Strategist Brain - core trading intelligence agent.

Researches markets, generates strategy ideas, scores backtest results,
and decides portfolio allocation across asset classes.
"""

import json
from typing import Any, Literal, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_xai import ChatXAI

from src.config import get_settings

MARKET_RESEARCH_SYSTEM_PROMPT = """\
You are an elite quantitative market analyst and portfolio strategist with deep \
expertise across crypto, equities, and forex markets.

Your task is to analyze current market conditions and generate actionable trading \
strategy ideas. For each asset class requested, provide:

1. **Market Regime**: Is the market trending (bull/bear), range-bound, or \
transitioning? What is the current volatility regime (low/normal/high/extreme)?

2. **Key Trends & Drivers**: What macro factors, technical patterns, or sentiment \
shifts are driving price action? Identify the dominant narrative.

3. **Opportunities**: Specific trade setups or strategy types that would perform \
well in this regime. Be concrete — name specific indicators, timeframes, and \
asset pairs.

4. **Risk Factors**: What could invalidate the thesis? Key levels to watch, \
upcoming events, correlation risks.

For strategy ideas, think like a systematic trader. Suggest strategies that can be \
coded as Backtrader strategies with clear entry/exit rules:
- Trend-following (moving average crossovers, breakouts, momentum)
- Mean-reversion (RSI extremes, Bollinger Band bounces, pairs trading)
- Volatility strategies (straddles, vol-of-vol, regime switching)
- Statistical arbitrage (correlation breakdown, cointegration)

Output your analysis as JSON with this structure:
{
  "market_analysis": "Your comprehensive market analysis text",
  "strategy_ideas": [
    {
      "name": "Strategy name",
      "asset_class": "crypto|stocks|forex",
      "type": "trend|mean_reversion|volatility|arbitrage",
      "description": "Brief description of the strategy logic",
      "rationale": "Why this strategy suits current conditions"
    }
  ]
}

Generate 3-5 diverse strategy ideas that span different asset classes and strategy \
types to ensure portfolio diversification."""

STRATEGY_GENERATION_SYSTEM_PROMPT = """\
You are an expert algorithmic trading strategy developer specializing in Backtrader \
strategies. Your job is to take a strategy idea and produce a detailed natural \
language specification that can be directly translated into a Backtrader strategy.

For each strategy, provide a DETAILED specification including:

1. **Indicators**: Exact indicators with parameters (e.g., SMA(20), RSI(14), \
Bollinger Bands(20, 2.0))
2. **Entry Rules**: Precise conditions for entering long/short positions. Use \
boolean logic (e.g., "Enter LONG when SMA_fast crosses above SMA_slow AND \
RSI > 50 AND volume > 1.5x average")
3. **Exit Rules**: Conditions for closing positions (take profit, stop loss, \
trailing stop, indicator-based exits)
4. **Position Sizing**: How to size the position (fixed fraction, volatility-based, \
Kelly criterion)
5. **Risk Management**: Stop-loss percentage, maximum position size, maximum \
drawdown before halting
6. **Timeframe**: Candle timeframe (1h, 4h, 1d) and lookback period
7. **Asset**: Specific trading pair or symbol

Be extremely specific. The description must be unambiguous enough that a code \
generator can produce a working Backtrader strategy from it alone.

Output as JSON array:
[
  {
    "name": "Strategy Name",
    "asset_class": "crypto|stocks|forex",
    "description": "Full detailed strategy specification as described above"
  }
]"""

ALLOCATION_SYSTEM_PROMPT = """\
You are a senior portfolio manager making allocation decisions for a systematic \
trading portfolio. You must decide how to distribute capital across a set of \
ranked trading strategies.

Your allocation must respect these hard constraints:
- Maximum {max_position_pct}% of total capital per individual strategy position
- Maximum {max_drawdown_pct}% portfolio-level drawdown tolerance
- Total capital: ${capital:,.0f}

Allocation principles:
1. **Diversification**: Spread across asset classes. Never allocate >40% to a \
single asset class.
2. **Risk Budgeting**: Higher-scoring strategies get more capital, but adjust for \
correlated drawdown risk. Two highly correlated strategies should share a risk budget.
3. **Score Thresholds**: Only allocate to strategies with a composite score above \
0.3. Below that, the risk-reward is unfavorable.
4. **Cash Reserve**: Always keep at least 10% in cash as a risk buffer.
5. **Position Sizing**: Within each strategy's allocation, individual positions \
should not exceed {max_position_pct}% of total portfolio.

Output your decision as JSON:
{{
  "allocations": [
    {{
      "strategy_name": "Name",
      "strategy_id": "id or null",
      "asset_class": "crypto|stocks|forex",
      "capital_pct": 15.0,
      "capital_amount": 15000.0,
      "rationale": "Why this allocation"
    }}
  ],
  "cash_reserve_pct": 10.0,
  "cash_reserve_amount": 10000.0,
  "risk_assessment": "Overall portfolio risk assessment",
  "expected_portfolio_sharpe": 1.5,
  "notes": "Any additional notes on the allocation decision"
}}"""


class StrategyCandidate(TypedDict):
    """A candidate strategy with optional backtest results."""

    description: str
    strategy_id: str | None
    report_id: str | None
    metrics: dict[str, Any] | None
    score: float


class StrategistState(TypedDict):
    """State for the strategist agent pipeline."""

    phase: Literal["research", "generate", "backtest", "score", "allocate", "complete"]
    market_analysis: str | None
    asset_classes: list[str]
    strategy_candidates: list[StrategyCandidate]
    ranked_strategies: list[StrategyCandidate]
    portfolio_allocation: dict[str, Any] | None
    capital: float
    risk_constraints: dict[str, float]
    error: str | None


class StrategistAgent:
    """The trading brain that researches, generates, tests, and selects strategies."""

    def __init__(self) -> None:
        settings = get_settings()
        self.llm = ChatXAI(
            model="grok-2-latest",
            api_key=settings.xai_api_key,
        )
        self.settings = settings

    async def research_markets(self, state: StrategistState) -> StrategistState:
        """Analyze current market conditions across all asset classes.

        Uses LLM to assess market regime, trends, volatility, and generate
        a list of strategy ideas suited to current conditions.
        """
        asset_classes = state["asset_classes"]

        messages = [
            SystemMessage(content=MARKET_RESEARCH_SYSTEM_PROMPT),
            HumanMessage(
                content=(
                    f"Analyze current market conditions for these asset classes: "
                    f"{', '.join(asset_classes)}.\n\n"
                    f"Capital available: ${state['capital']:,.0f}\n"
                    f"Risk constraints: max {state['risk_constraints']['max_position_pct']}% "
                    f"per position, max {state['risk_constraints']['max_drawdown_pct']}% "
                    f"portfolio drawdown.\n\n"
                    f"Generate diverse strategy ideas that work well in current conditions."
                )
            ),
        ]

        response = await self.llm.ainvoke(messages)
        content = str(response.content)

        # Parse the JSON response
        try:
            parsed = json.loads(content)
            state["market_analysis"] = parsed.get("market_analysis", content)
            ideas = parsed.get("strategy_ideas", [])

            # Convert ideas to initial strategy candidates
            candidates: list[StrategyCandidate] = []
            for idea in ideas:
                candidates.append(
                    {
                        "description": (
                            f"{idea.get('name', 'Unknown')}: "
                            f"{idea.get('description', '')} "
                            f"[{idea.get('asset_class', 'unknown')}/"
                            f"{idea.get('type', 'unknown')}] "
                            f"Rationale: {idea.get('rationale', '')}"
                        ),
                        "strategy_id": None,
                        "report_id": None,
                        "metrics": None,
                        "score": 0.0,
                    }
                )
            state["strategy_candidates"] = candidates
        except json.JSONDecodeError:
            # Fallback: use raw response as analysis
            state["market_analysis"] = content
            state["error"] = "Failed to parse market research JSON response"

        return state

    async def generate_strategies(self, state: StrategistState) -> StrategistState:
        """Generate detailed strategy descriptions for each idea.

        Produces Backtrader-compatible strategy specifications that can
        be passed to Lona for code generation.
        """
        candidates = state["strategy_candidates"]
        if not candidates:
            state["error"] = "No strategy candidates to generate from"
            return state

        # Collect the brief descriptions for the LLM
        idea_summaries = "\n".join(
            f"{i + 1}. {c['description']}" for i, c in enumerate(candidates)
        )

        messages = [
            SystemMessage(content=STRATEGY_GENERATION_SYSTEM_PROMPT),
            HumanMessage(
                content=(
                    f"Generate detailed Backtrader strategy specifications for "
                    f"these strategy ideas:\n\n{idea_summaries}\n\n"
                    f"Capital: ${state['capital']:,.0f}\n"
                    f"Max position size: {state['risk_constraints']['max_position_pct']}%\n"
                    f"Max drawdown: {state['risk_constraints']['max_drawdown_pct']}%"
                )
            ),
        ]

        response = await self.llm.ainvoke(messages)
        content = str(response.content)

        try:
            strategies = json.loads(content)
            if isinstance(strategies, list):
                # Update candidates with detailed descriptions
                updated: list[StrategyCandidate] = []
                for i, strat in enumerate(strategies):
                    updated.append(
                        {
                            "description": (
                                f"{strat.get('name', f'Strategy_{i}')}: "
                                f"{strat.get('description', '')}"
                            ),
                            "strategy_id": None,
                            "report_id": None,
                            "metrics": None,
                            "score": 0.0,
                        }
                    )
                state["strategy_candidates"] = updated
        except json.JSONDecodeError:
            state["error"] = "Failed to parse strategy generation JSON response"

        return state

    async def score_strategies(self, state: StrategistState) -> StrategistState:
        """Score and rank strategies based on backtest metrics.

        Scoring formula (composite score 0-1):
        - Sharpe ratio:   40% weight (normalized: sharpe / 3.0, clamped)
        - Max drawdown:   25% weight (inverted: lower is better)
        - Win rate:        20% weight (as decimal 0-1)
        - Total return:   15% weight (normalized: return / 100, clamped)
        """
        candidates = state["strategy_candidates"]
        scored: list[StrategyCandidate] = []

        for candidate in candidates:
            metrics = candidate.get("metrics")
            if not metrics:
                # No backtest results yet — keep with zero score
                scored.append(candidate)
                continue

            sharpe = float(metrics.get("sharpe_ratio", 0.0))
            max_dd = float(metrics.get("max_drawdown", 0.0))
            win_rate = float(metrics.get("win_rate", 0.0))
            total_return = float(metrics.get("total_return", 0.0))

            # Normalize components to 0-1 range
            sharpe_score = min(max(sharpe / 3.0, 0.0), 1.0)
            drawdown_score = min(max(1.0 - (abs(max_dd) / 50.0), 0.0), 1.0)
            win_score = min(max(win_rate / 100.0 if win_rate > 1 else win_rate, 0.0), 1.0)
            return_score = min(max(total_return / 100.0, 0.0), 1.0)

            composite = (
                0.40 * sharpe_score
                + 0.25 * drawdown_score
                + 0.20 * win_score
                + 0.15 * return_score
            )

            candidate["score"] = round(composite, 4)
            scored.append(candidate)

        # Sort by score descending
        ranked = sorted(scored, key=lambda c: c["score"], reverse=True)
        state["ranked_strategies"] = ranked

        return state

    async def decide_allocation(self, state: StrategistState) -> StrategistState:
        """Decide portfolio allocation based on ranked strategies and risk constraints.

        Uses LLM to reason about diversification, risk budget, and position sizing
        to produce a final capital allocation across top strategies.
        """
        ranked = state["ranked_strategies"]
        if not ranked:
            state["error"] = "No ranked strategies to allocate to"
            return state

        # Build strategy summary for LLM
        strategy_summary = "\n".join(
            f"{i + 1}. Score: {s['score']:.4f} | {s['description'][:200]}"
            + (f" | Metrics: {json.dumps(s['metrics'])}" if s.get("metrics") else "")
            for i, s in enumerate(ranked)
        )

        prompt = ALLOCATION_SYSTEM_PROMPT.format(
            max_position_pct=state["risk_constraints"]["max_position_pct"],
            max_drawdown_pct=state["risk_constraints"]["max_drawdown_pct"],
            capital=state["capital"],
        )

        messages = [
            SystemMessage(content=prompt),
            HumanMessage(
                content=(
                    f"Allocate ${state['capital']:,.0f} across these ranked strategies:\n\n"
                    f"{strategy_summary}\n\n"
                    f"Market analysis context:\n{state.get('market_analysis', 'N/A')[:500]}"
                )
            ),
        ]

        response = await self.llm.ainvoke(messages)
        content = str(response.content)

        try:
            allocation = json.loads(content)
            state["portfolio_allocation"] = allocation
        except json.JSONDecodeError:
            # Fallback: store raw text
            state["portfolio_allocation"] = {"raw_response": content}
            state["error"] = "Failed to parse allocation JSON response"

        return state

    async def run(
        self,
        asset_classes: list[str] | None = None,
        capital: float | None = None,
    ) -> dict[str, Any]:
        """Run the full strategist pipeline.

        Phases: research → generate → score → allocate → complete.
        The backtest phase is handled externally via Lona client integration.
        """
        settings = self.settings
        state: StrategistState = {
            "phase": "research",
            "market_analysis": None,
            "asset_classes": asset_classes or ["crypto", "stocks", "forex"],
            "strategy_candidates": [],
            "ranked_strategies": [],
            "portfolio_allocation": None,
            "capital": capital or settings.initial_capital,
            "risk_constraints": {
                "max_position_pct": settings.max_position_pct,
                "max_drawdown_pct": settings.max_drawdown_pct,
            },
            "error": None,
        }

        state = await self.research_markets(state)
        state["phase"] = "generate"

        state = await self.generate_strategies(state)
        # Note: backtest step is called externally via CLI/API
        # since it requires Lona client integration
        state["phase"] = "score"

        state = await self.score_strategies(state)
        state["phase"] = "allocate"

        state = await self.decide_allocation(state)
        state["phase"] = "complete"

        return {
            "market_analysis": state["market_analysis"],
            "strategies": state["ranked_strategies"],
            "allocation": state["portfolio_allocation"],
            "capital": state["capital"],
            "error": state["error"],
        }
