# Portfolio Project Roadmap — Quant/Finance/Climate/Quantum

## Purpose
This repo contains a portfolio of 10 technical projects built to demonstrate depth across 
quantitative finance, real estate/climate risk, energy systems, complex systems, and quantum 
computing — aimed at quant/data-science/research-oriented interviews.

Background: derivatives/options experience from a student hedge fund; interested roles span 
insurance risk (Generali-style), quant research, and quantum computing applications (G2Q-style).

## Working style
- Build in clean, modular, well-commented code — this needs to read well in an interview context.
- Confirm the plan back before writing code on any new project; ask before guessing on 
  non-trivial decisions (data source choices, model architecture, capture windows, etc.)
- Each project is self-contained: own /data, /src, /notebooks, /output, requirements.txt, README.
- Prefer real public data sources over synthetic/toy data wherever feasible.
- Every project's README should include: problem framing, data source, methodology, 
  key findings/results, and what a follow-up/extension would look like.

## Project List (in build order)

### Level 1 — Financial Markets
1. **Order Book Dynamics & Market Microstructure** — Binance/Kraken WS depth data, bid-ask 
   spread dynamics, order flow imbalance (OFI) as short-term predictor, price impact. 
   Stack: Python, websockets, pandas, matplotlib. [STATUS: in progress]
2. **Volatility Surface Modelling** — real options data, IV surface calibration, smile/term 
   structure, local vol or Heston calibration. Stack: Python, scipy, numpy, QuantLib optional.

### Level 2 — Real Estate & Climate
3. **Real Estate Price Predictor with Spatial Features** — GeoPandas spatial features 
   (transport proximity, amenity density, network centrality), SHAP interpretability. 
   Stack: GeoPandas, scikit-learn, SHAP.
4. **Climate Risk Scoring for Real Estate Portfolios** — Copernicus CDS climate data, 
   flood/heat/sea-level risk, composite risk score. Stack: Copernicus CDS API, GeoPandas, 
   scikit-learn.

### Level 3 — Energy & Complex Systems
5. **European Energy Price Forecasting** — ENTSO-E API, day-ahead price forecasting, 
   ARIMA → XGBoost → LSTM. Stack: statsmodels, XGBoost, PyTorch.
6. **Financial Contagion on Networks** — interbank exposure network, shock propagation 
   (SIR-style), random vs scale-free topology comparison. Stack: NetworkX, NumPy, Mesa optional.

### Level 4 — Quantum Computing
7. **Quantum ML — Variational Classifier on Financial Data** — VQC for credit default/earnings 
   surprise classification, honest benchmark vs classical baseline. Stack: PennyLane or Qiskit, 
   scikit-learn.
8. **QAOA for Portfolio Optimisation** — discrete portfolio selection via QAOA vs classical 
   Markowitz vs heuristic. Stack: Qiskit or PennyLane, scipy, numpy.

### Level 5 — Capstones
9. **Agent-Based Housing Market with Financial Feedback** — ABM with mortgage access tied to 
   interest rate conditions, testing for bubble/crash emergence. Stack: Mesa, pandas, matplotlib.
10. **Climate Risk + Quantum Portfolio Optimisation** — real estate portfolio optimisation under 
    climate constraints, classical vs QAOA solver. Stack: everything above + Qiskit/PennyLane + 
    Gurobi or scipy.

## Current focus
Project 1 (Order Book Dynamics) — see /project-1-orderbook/README.md for specifics.
