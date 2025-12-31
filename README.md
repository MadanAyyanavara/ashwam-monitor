# ashwam-monitor

Production monitoring and evaluation framework for Ashwam journaling parser - detects model/prompt drift and unsafe behavior without ground truth labels.

## Overview

This project implements a **production-grade monitoring system** for the Ashwam health journaling parser. The system is designed to detect model drift, prompt changes, and unsafe extraction behavior in a non-deterministic LLM-based system without relying on ground truth labels.

### Key Design Principles
- **Safety First**: Restraint and precision matter more than recall
- **No Ground Truth**: Operates without canonical labels for symptoms, food, emotions, or mind states  
- **Production Ready**: Detects drift, hallucinations, contradictions, and schema violations
- **Explainability**: Reports actionable insights for human review

## Features

### 1. Invariant Checks (Hard Rules)
Ensures critical structural and semantic integrity:
- **Schema Validity**: Confirms outputs conform to expected JSON structure
- **Evidence Span Validity**: Verifies extracted spans appear verbatim in source text (hallucination detection)
- **Contradiction Detection**: Identifies same evidence spans with conflicting polarity
- **Polarity Consistency**: Tracks conflicts in extracted sentiment/presence indicators

### 2. Proxy Drift Metrics (No Labels)
Detects model/prompt changes via statistical signals:
- **Extraction Volume**: Average items extracted per journal (detect over/under-extraction)
- **Uncertainty Rate**: Proportion of unknown/uncertain polarity or intensity buckets
- **Arousal Drift**: High-arousal emotion detection rate changes
- **Domain Mix Drift**: Distribution shifts across symptom/food/emotion/mind domains
- **Intensity Drift**: Changes in high-intensity item rates

### 3. Canary Audit Strategy
Small labeled dataset monitors production health:
- **Fixed Canary Set**: Evidence-grounded gold labels for 5 key journals
- **Minimal Metrics**: Pass/fail threshold-based alerting
- **Automated Checks**: Runs on Day 1+ outputs, triggers human review if alert
- **Threshold**: 80% pass rate required to clear canary audit

### 4. Human-in-the-Loop Design
Clear separation of machine and human decisions:
- **What Machines Do**: Compute invariants, drift metrics, canary scores
- **What Humans Do**: Review drift alerts, investigate schema violations, approve rollbacks
- **Frequency**: Canary runs on every production batch, weekly drift reviews

## Installation

```bash
# Clone repository
git clone https://github.com/MadanAyyanavara/ashwam-monitor.git
cd ashwam-monitor

# Install package in development mode
pip install -e .
```

## Usage

### CLI Entrypoint

```bash
python -m ashwammonitor run --data ./data --out ./out
```

**Arguments**:
- `--data`: Directory containing journals.jsonl, parser_outputs_day0.jsonl, parser_outputs_day1.jsonl, gold.jsonl
- `--out`: Output directory for reports

### Output Reports

The system generates three JSON reports:

#### 1. `out_invariant_report.json`
Summary of hard rule violations:
```json
{
  "summary": { ... },
  "day0_baseline": {
    "schema_valid_rate": 1.0,
    "evidence_valid_rate": 0.95,
    "hallucination_rate": 0.05,
    "contradiction_count": 0
  },
  "day1_drift_breakage": {
    "schema_valid_rate": 1.0,
    "evidence_valid_rate": 0.85,
    "hallucination_rate": 0.15,
    "contradiction_count": 2
  },
  "invariant_explanations": { ... }
}
```

#### 2. `out_drift_report.json`
Proxy metrics comparing Day 0 vs Day 1:
```json
{
  "day0": { "avg_extraction": 2.1, "high_arousal_rate": 0.3, ... },
  "day1": { "avg_extraction": 2.5, "high_arousal_rate": 0.5, ... },
  "drift_signals": {
    "extraction_volume_change": 0.19,
    "arousal_drift": 0.2,
    "domain_mix_change": { ... }
  }
}
```

#### 3. `out_canary_report.json`
Canary audit results:
```json
{
  "canary_passed": 4,
  "canary_failed": 1,
  "canary_pass_rate": 0.8,
  "status": "PASS",
  "alerts": [ ... ]
}
```

## Data Format

### Input Files

**journals.jsonl** - Source journal entries:
```json
{"journalid": "C001", "text": "Woke up with mild headache...", "langhint": "en"}
```

**parser_outputs_day{0,1}.jsonl** - Parser extraction results:
```json
{"journalid": "C001", "items": [
  {"domain": "symptom", "evidencespan": "mild headache", "polarity": "present", "confidence": 0.7}
]}
```

**gold.jsonl** - Evidence-grounded canary labels (no canonical labels, just evidence grounding):
```json
{"journalid": "C001", "items": [
  {"domain": "symptom", "evidencespan": "mild headache", "polarity": "present"}
]}
```

## Architecture

```
ashwammonitor/
├── __init__.py           # Package exports
├── __main__.py          # CLI entry point  
├── monitor.py           # Core monitoring logic
└── tests/
    ├── test_invariants.py
    ├── test_drift.py
    └── test_canary.py

data/
├── journals.jsonl                # 20 source journals
├── parser_outputs_day0.jsonl     # Baseline extractions
├── parser_outputs_day1.jsonl     # Drift+breakage scenario
└── gold.jsonl                    # 5 canary labels
```

## Invariant Explanations

### Schema Validity
- **Definition**: Rate of outputs conforming to JSON schema
- **Risk Mitigated**: Structural errors, incomplete data
- **Action on Failure**: Investigate parser version, schema changes, recent deployments

### Evidence Span Validity
- **Definition**: % of extracted spans appearing verbatim in journal text
- **Risk Mitigated**: Hallucinations, fabricated evidence
- **Action on Failure**: Review prompt changes, retrain model, consider rollback

### Hallucination Rate
- **Definition**: % of extracted items unsupported by source text
- **Risk Mitigated**: Unsafe claims, trust degradation
- **Action on Failure**: Immediate human review, potential rollback

### Contradiction Rate
- **Definition**: Same evidence span extracted with conflicting polarity
- **Risk Mitigated**: Logical inconsistency, user confusion
- **Action on Failure**: Human investigation, model retraining

## Production Deployment

1. **Pre-Deployment**: Run canary on small labeled set
2. **Initial Run**: Compute Day 0 invariants and drift metrics as baseline
3. **Ongoing**: Monitor each new batch (Day 1, 2, etc.) against Day 0
4. **Alerts**: If canary fails or drift metrics exceed thresholds, escalate to humans
5. **Review**: Weekly drift reviews by domain experts
6. **Rollback**: If hallucination rate > 20%, consider immediate rollback


## Explainability (Role-based)

This section describes how parsing decisions are explained to different stakeholders:

### For Product Managers
**Audience**: System health, trends, risk signals
- **What to Show**: Invariant pass rates, drift metrics over time, alert frequency
- **How to Present**:  
  - "Schema validity: 95% (Day 0) → 90% (Day 1) - slight degradation, investigate"  
  - "Hallucination rate: 5% → 15% - 3x increase, recommend human review"  
  - "Canary status: ALERT - extraction patterns shifting, trending review needed"
- **Focus**: High-level system health signals, no technical details

### For Clinicians/Domain Experts
**Audience**: Evidence grounding, uncertainty, limitations
- **What to Show**: Extraction accuracy, evidence span grounding, confidence scores
- **How to Present**:  
  - "Symptom 'headache' extracted from 'mild headache' - evidence grounded ✓"  
  - "Emotion 'calm' found with 65% confidence - moderate uncertainty"  
  - "Evidence span 'intrusive thoughts' appears in journal, but polarity contradicted in another entry - needs review"
- **Focus**: Evidence quality, not assertions, limitations transparently

### For End Users
**Audience**: High-level, non-alarming, trust-preserving
- **What to Show**: Only clear, well-grounded insights
- **How to Present**:  
  - "We found 'headache' in your journal from 12/15 morning"  
  - "This is mentioned in your original entry, so we're confident in flagging it"  
  - "When we're less certain, we don't include it - your privacy and accuracy matter most"
- **Focus**: Transparency about what we found and confidence, avoid jargon

## Future Enhancements

- [ ] Add statistical significance tests for drift detection
- [ ] Implement confidence interval estimation for metrics
- [ ] Add time-series anomaly detection (CUSUM, Isolation Forest)
- [ ] Develop user-facing dashboards for monitoring trends
- [ ] Add cost-sensitive error metrics for false positives vs negatives

## Contributing

To add new invariants or metrics:
1. Add method to `AshwamMonitor` class in `monitor.py`
2. Call from `run()` method
3. Add explanation in `_format_invariant_report()` or output
4. Write tests in `tests/`

## License

MIT
