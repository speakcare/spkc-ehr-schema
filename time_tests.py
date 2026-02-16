#!/usr/bin/env python3
"""
Script to time individual LLM tests with different providers.
"""

import os
import sys
import time
import unittest
from io import StringIO

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Set environment variables
os.environ['RUN_LLM_TESTS'] = 'true'
os.environ['PYTHONPATH'] = 'src'

def run_test_with_timing(provider, test_name):
    """Run a single test and return the execution time."""
    os.environ['MODEL_PROVIDER'] = provider
    if provider == 'gemini':
        os.environ['GEMINI_STRICT_SCHEMA'] = 'false'
    else:
        os.environ['GEMINI_STRICT_SCHEMA'] = 'true' # Default for others
    
    # Import the test class
    from tests.pcc.pcc_assessment_schema_test import TestPCCLLMSchemaCompatibility
    
    # Create test suite with just this test
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromName(f'tests.pcc.pcc_assessment_schema_test.TestPCCLLMSchemaCompatibility.{test_name}')
    
    # Run the test and measure time
    start_time = time.time()
    stream = StringIO()
    runner = unittest.TextTestRunner(stream=stream, verbosity=0)
    result = runner.run(suite)
    end_time = time.time()
    
    elapsed = end_time - start_time
    success = result.wasSuccessful()
    
    return elapsed, success

def main():
    providers = ['openai', 'gemini']
    test_names = [
        'test_assessments_llm_compatibility_without_enrichment',
        'test_assessments_llm_compatibility_with_enrichment',
        'test_assessments_llm_compatibility_with_enrichment_and_overrides'
    ]
    
    print("=" * 80)
    print("LLM Test Timing Comparison (OpenAI vs Gemini JSON Mode)")
    print("=" * 80)
    print()
    
    results = {}
    
    for provider in providers:
        print(f"Running tests with MODEL_PROVIDER={provider}...")
        print("-" * 80)
        results[provider] = {}
        
        for test_name in test_names:
            print(f"  Running {test_name}...", end=" ", flush=True)
            elapsed, success = run_test_with_timing(provider, test_name)
            results[provider][test_name] = {'time': elapsed, 'success': success}
            
            status = "✓ PASSED" if success else "✗ FAILED"
            print(f"{status} ({elapsed:.2f}s)")
        
        print()
    
    # Print comparison table
    print("=" * 80)
    print("Timing Comparison Summary")
    print("=" * 80)
    print()
    print(f"{'Test Name':<60} {'OpenAI (s)':<12} {'Gemini (s)':<12} {'Ratio':<10}")
    print("-" * 80)
    
    for test_name in test_names:
        openai_time = results['openai'][test_name]['time']
        gemini_time = results['gemini'][test_name]['time']
        ratio = gemini_time / openai_time if openai_time > 0 else 0
        
        # Shorten test name for display
        short_name = test_name.replace('test_assessments_llm_compatibility_', '')
        print(f"{short_name:<60} {openai_time:<12.2f} {gemini_time:<12.2f} {ratio:<10.2f}x")
    
    print()
    total_openai = sum(r['time'] for r in results['openai'].values())
    total_gemini = sum(r['time'] for r in results['gemini'].values())
    total_ratio = total_gemini / total_openai if total_openai > 0 else 0
    
    print(f"{'TOTAL':<60} {total_openai:<12.2f} {total_gemini:<12.2f} {total_ratio:<10.2f}x")
    print()

if __name__ == '__main__':
    main()
