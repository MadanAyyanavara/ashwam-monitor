import json
import os
from pathlib import Path
from collections import defaultdict, Counter
from typing import Dict, List, Any, Set, Tuple
import statistics

class AshwamMonitor:
    """Production monitoring and evaluation framework for Ashwam journaling parser."""
    
    def __init__(self):
        self.required_fields = {'journalid', 'items'}
        self.item_fields = {'domain', 'text', 'evidencespan', 'polarity', 'confidence'}
        self.domains = {'symptom', 'food', 'emotion', 'mind'}
        self.polarity_values = {'present', 'absent', 'unknown'}
        
    def run(self, data_dir: str, out_dir: str):
        """Main execution function."""
        data_path = Path(data_dir)
        out_path = Path(out_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        
        # Load input files
        journals = self._load_jsonl(data_path / 'journals.jsonl')
        day0_outputs = self._load_jsonl(data_path / 'parser_outputs_day0.jsonl')
        day1_outputs = self._load_jsonl(data_path / 'parser_outputs_day1.jsonl')
        canary_gold = self._load_jsonl(data_path / 'gold.jsonl')
        
        # Compute invariants
        inv_day0 = self._compute_invariants(day0_outputs, journals)
        inv_day1 = self._compute_invariants(day1_outputs, journals)
        
        # Compute drift metrics
        drift_metrics = self._compute_drift_metrics(day0_outputs, day1_outputs, journals)
        
        # Run canary audit
        canary_results = self._run_canary(day1_outputs, canary_gold, journals)
        
        # Save reports
        self._save_report(out_path / 'out_invariant_report.json', self._format_invariant_report(inv_day0, inv_day1))
        self._save_report(out_path / 'out_drift_report.json', drift_metrics)
        self._save_report(out_path / 'out_canary_report.json', canary_results)
        
        print(f"Monitoring complete. Reports saved to {out_dir}")
    
    def _load_jsonl(self, filepath: Path) -> List[Dict]:
        """Load JSONL file."""
        if not filepath.exists():
            return []
        data = []
        with open(filepath, 'r') as f:
            for line in f:
                if line.strip():
                    data.append(json.loads(line))
        return data
    
    def _compute_invariants(self, outputs: List[Dict], journals: List[Dict]) -> Dict[str, Any]:
        """Compute hard invariant checks."""
        total = len(outputs)
        schema_valid = 0
        evidence_valid = 0
        hallucinations = 0
        contradictions = defaultdict(list)
        
        journal_texts = {j['journalid']: j['text'] for j in journals}
        
        for record in outputs:
            journal_id = record.get('journalid')
            journal_text = journal_texts.get(journal_id, '')
            items = record.get('items', [])
            
            # Check schema validity
            if self._validate_schema(record):
                schema_valid += 1
            
            # Process items
            evidence_spans_seen = defaultdict(list)
            for item in items:
                # Check evidence span validity
                evidence_span = item.get('evidencespan', '')
                polarity = item.get('polarity', '')
                domain = item.get('domain', '')
                
                if evidence_span and self._is_span_in_text(evidence_span, journal_text):
                    evidence_valid += 1
                elif evidence_span:  # Hallucinated
                    hallucinations += 1
                
                # Track contradictions
                evidence_spans_seen[evidence_span].append(polarity)
            
            # Check contradictions
            for span, polarities in evidence_spans_seen.items():
                if len(set(polarities)) > 1:
                    contradictions[journal_id].append(span)
        
        return {
            'total_records': total,
            'schema_valid_count': schema_valid,
            'schema_valid_rate': schema_valid / total if total > 0 else 0,
            'evidence_valid_count': evidence_valid,
            'evidence_valid_rate': evidence_valid / max(1, sum(len(r.get('items', [])) for r in outputs)) if outputs else 0,
            'hallucination_count': hallucinations,
            'hallucination_rate': hallucinations / max(1, sum(len(r.get('items', [])) for r in outputs)) if outputs else 0,
            'contradiction_count': sum(len(v) for v in contradictions.values()),
            'contradictions_by_journal': dict(contradictions)
        }
    
    def _validate_schema(self, record: Dict) -> bool:
        """Validate output schema."""
        if not isinstance(record, dict):
            return False
        if 'journalid' not in record:
            return False
        items = record.get('items', [])
        if not isinstance(items, list):
            return False
        for item in items:
            required = {'domain', 'text', 'evidencespan', 'polarity', 'confidence'}
            if not all(k in item for k in required):
                return False
        return True
    
    def _is_span_in_text(self, span: str, text: str) -> bool:
        """Check if evidence span appears verbatim in text."""
        if not span or not text:
            return False
        return span.lower() in text.lower()
    
    def _compute_drift_metrics(self, day0: List[Dict], day1: List[Dict], journals: List[Dict]) -> Dict[str, Any]:
        """Compute proxy drift metrics."""
        def extract_stats(outputs: List[Dict]) -> Dict:
            total_items = sum(len(r.get('items', [])) for r in outputs)
            avg_extraction = total_items / len(outputs) if outputs else 0
            
            uncertainty_count = 0
            intensity_high = 0
            arousal_high = 0
            domain_counts = Counter()
            
            for record in outputs:
                for item in record.get('items', []):
                    if item.get('polarity') == 'unknown' or item.get('intensitybucket') == 'unknown':
                        uncertainty_count += 1
                    if item.get('intensitybucket') == 'high':
                        intensity_high += 1
                    if item.get('arousalbucket') == 'high':
                        arousal_high += 1
                    domain_counts[item.get('domain')] += 1
            
            return {
                'total_items': total_items,
                'avg_extraction': avg_extraction,
                'uncertainty_rate': uncertainty_count / max(1, total_items),
                'high_intensity_rate': intensity_high / max(1, total_items),
                'high_arousal_rate': arousal_high / max(1, total_items),
                'domain_distribution': dict(domain_counts)
            }
        
        day0_stats = extract_stats(day0)
        day1_stats = extract_stats(day1)
        
        return {
            'day0': day0_stats,
            'day1': day1_stats,
            'drift_signals': {
                'extraction_volume_change': (day1_stats['avg_extraction'] - day0_stats['avg_extraction']) / max(0.001, day0_stats['avg_extraction']),
                'uncertainty_rate_change': day1_stats['uncertainty_rate'] - day0_stats['uncertainty_rate'],
                'arousal_drift': day1_stats['high_arousal_rate'] - day0_stats['high_arousal_rate'],
                'domain_mix_change': self._compute_domain_drift(day0_stats['domain_distribution'], day1_stats['domain_distribution'])
            }
        }
    
    def _compute_domain_drift(self, day0_dist: Dict, day1_dist: Dict) -> Dict:
        """Compute domain mix drift."""
        changes = {}
        all_domains = set(day0_dist.keys()) | set(day1_dist.keys())
        total0 = sum(day0_dist.values())
        total1 = sum(day1_dist.values())
        
        for domain in all_domains:
            count0 = day0_dist.get(domain, 0)
            count1 = day1_dist.get(domain, 0)
            pct0 = count0 / total0 if total0 > 0 else 0
            pct1 = count1 / total1 if total1 > 0 else 0
            changes[domain] = {'day0_pct': pct0, 'day1_pct': pct1, 'change': pct1 - pct0}
        
        return changes
    
    def _run_canary(self, outputs: List[Dict], canary_gold: List[Dict], journals: List[Dict]) -> Dict:
        """Run canary audit on labeled subset."""
        # Map gold by journal ID
        canary_map = {c['journalid']: c for c in canary_gold}
        
        passed = 0
        failed = 0
        alerts = []
        
        for record in outputs:
            journal_id = record['journalid']
            if journal_id not in canary_map:
                continue
            
            # Simple check: verify items exist if expected
            items = record.get('items', [])
            gold = canary_map[journal_id].get('items', [])
            
            if bool(items) == bool(gold):
                passed += 1
            else:
                failed += 1
                alerts.append({
                    'journal_id': journal_id,
                    'reason': f'Extraction mismatch: {len(items)} items found, {len(gold)} expected'
                })
        
        return {
            'canary_passed': passed,
            'canary_failed': failed,
            'canary_pass_rate': passed / (passed + failed) if (passed + failed) > 0 else 1.0,
            'alerts': alerts,
            'threshold': 0.8,
            'status': 'PASS' if (passed / (passed + failed) >= 0.8 if (passed + failed) > 0 else True) else 'ALERT'
        }
    
    def _save_report(self, filepath: Path, data: Dict):
        """Save report to JSON file."""
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2, default=str)
    
    def _format_invariant_report(self, inv_day0: Dict, inv_day1: Dict) -> Dict:
        """Format invariant report with explanations."""
        return {
            'summary': {
                'exercise': 'Production Monitoring Without Ground Truth',
                'focus': 'Safety and restraint over recall',
                'constraints': 'No canonical labels for symptom, food, emotion, or mind'
            },
            'day0_baseline': inv_day0,
            'day1_drift_breakage': inv_day1,
            'invariant_explanations': {
                'schema_validity': {
                    'definition': 'Rate of outputs conforming to expected JSON schema',
                    'risk_mitigated': 'Structural errors, incomplete data',
                    'action_on_failure': 'Investigate parser version, schema changes'
                },
                'evidence_span_validity': {
                    'definition': 'Rate of extracted items whose evidencespan appears verbatim in journal text',
                    'risk_mitigated': 'Hallucinations, fabricated evidence',
                    'action_on_failure': 'Review and retrain model, investigate prompt changes'
                },
                'hallucination_rate': {
                    'definition': 'Rate of extracted items not supported by source text',
                    'risk_mitigated': 'Unsafe claims, trust degradation',
                    'action_on_failure': 'Immediate human review, potential rollback'
                },
                'contradiction_rate': {
                    'definition': 'Same evidence span extracted with conflicting polarity',
                    'risk_mitigated': 'Logical inconsistency, user confusion',
                    'action_on_failure': 'Human review, model retraining'
                }
            }
        }
