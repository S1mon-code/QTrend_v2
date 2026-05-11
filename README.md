# QTrend_v2

Long-only trend-capture engine for HC (热卷) futures. Carver-style continuous forecast → integer-lot sizing (0-5) → 1H Connors pullback modulator → ATR trailing stop. Driven by manually annotated `long bias` windows from Simon.

See:
- `docs/superpowers/specs/2026-05-11-qtrend-v2-design.md` — full design spec
- `docs/superpowers/plans/2026-05-11-qtrend-v2-implementation.md` — this plan
- `docs/research/2026-05-11-indicator-frequency-research.md` — indicator-frequency deep research

## Install (dev)
```
cd ~/Desktop/QTrend_v2
python -m pip install -e ".[dev]"
```

## Run tests
```
pytest -ra
```

## Status
v1 in development. Out of scope for v1: live execution, paper trade, quantitative bias proxy, multi-instrument.
