# Scenario study — same data, different variables, different sites

Run: `python pipeline/s2_scenarios.py && python pipeline/s2_scenario_figures.py` (about 5 minutes).
Add or edit scenarios in the `SCENARIOS` list at the top of `pipeline/s2_scenarios.py`; each one overrides one variable.

| Scenario | Variable changed | Sites | Demand covered | Sites moved vs baseline (> 2 km) | Candidates passing MUST filters |
|---|---|---|---|---|---|
| Baseline | the settings in s2_params.py | 4 | 97% | 0 of 4 | 936 |
| Faster access | patients must reach a site within 45 min (not 1.5 h) | 4 | 82% | 3 of 4 | 936 |
| Rainy season | travel times on rainy-season roads (tracks ×0.5, paths ×0.6) | 4 | 95% | 3 of 4 | 936 |
| Strict isolation | sites ≥ 2 km from villages (not 500 m) | 4 | 95% | 3 of 4 | 247 |
| Hospital-led | SHOULD weight on 'near hospital' raised to 0.6 | 4 | 93% | 2 of 4 | 936 |
| Community-first | weights on community acceptance + waste downhill raised | 4 | 96% | 2 of 4 | 936 |
| Tight budget | only 2 treatment centres | 2 | 88% | 1 of 2 | 936 |
| Early warning | planning on 1 June 2014: demand for Jun–Aug only | 4 | 97% | 2 of 4 | 936 |
| Cross-border | weight on 'border flow' raised to 0.5 | 4 | 93% | 2 of 4 | 936 |

## Robustness (200 runs with random SHOULD weights)
Coverage stays between 93% and 96%. The sites near **Macenta (S1)** and **Guéckédou (S2)** are
chosen in almost every run: demand and the road network decide them. The eastern sites (S3, S4) and the Kissidougou area
depend on the weights: the designer's priorities decide them.

## Files
- `fig_5_scenarios.png`: 3 × 3 small multiples
- `fig_6_robustness.png`: Monte Carlo robustness map
- `scenarios.gif`: animated, one scenario per frame
- `scenarios.json`, `monte_carlo_*.csv/json`: data behind the figures
