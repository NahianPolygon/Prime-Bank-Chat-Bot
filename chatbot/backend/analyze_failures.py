#!/usr/bin/env python3
"""
Comprehensive Analysis of Test Failures
Compares bot responses against expected behavior from knowledge base
"""

import csv
import json
import os
from pathlib import Path

def analyze_results():
    csv_path = 'test_results/latest_results.csv'
    
    # Read CSV
    results = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            results.append(row)
    
    # Categorize by status
    passed = [r for r in results if '✅ PASS' in r.get('Turn Status', '')]
    failed = [r for r in results if '❌ FAIL' in r.get('Turn Status', '')]
    
    print("\n" + "="*120)
    print("COMPREHENSIVE TEST FAILURE ANALYSIS REPORT")
    print("="*120)
    
    print(f"\n📊 OVERALL STATISTICS:")
    print(f"   Total test turns: {len(results)}")
    print(f"   ✅ Passed: {len(passed)} ({len(passed)*100//len(results) if results else 0}%)")
    print(f"   ❌ Failed: {len(failed)} ({len(failed)*100//len(results) if results else 0}%)")
    
    # Analyze failures by category
    print(f"\n📋 FAILURES BY CATEGORY:")
    categories = {}
    for r in failed:
        cat = r.get('Category', 'Unknown')
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(r)
    
    for cat in sorted(categories.keys()):
        print(f"\n   {cat}: {len(categories[cat])} failures")
    
    # Show sample failures
    print(f"\n\n🔴 DETAILED FAILURE ANALYSIS (First 20 failures):")
    print("="*120)
    
    for i, failure in enumerate(failed[:20]):
        print(f"\n[Failure {i+1}] {failure.get('Category')} > {failure.get('Scenario Name')}")
        print(f"   Turn: {failure.get('Turn #')}")
        print(f"   👤 User Query: {failure.get('User Query', '')[:120]}")
        print(f"   🤖 Bot Response: {failure.get('Bot Response', '')[:150]}")
        print(f"   ⚠️  Issues: {failure.get('Issues', '')[:150]}")
        print(f"   ⏱️  Time: {failure.get('Turn Time (s)', '')}s")
    
    # Analyze passed tests
    print(f"\n\n✅ PASSED TESTS (First 10):")
    print("="*120)
    
    for i, passed_test in enumerate(passed[:10]):
        print(f"\n[Pass {i+1}] {passed_test.get('Category')} > {passed_test.get('Scenario Name')}")
        print(f"   👤 User: {passed_test.get('User Query', '')[:80]}")
        print(f"   🤖 Bot: {passed_test.get('Bot Response', '')[:120]}")
    
    # Show unique failure patterns
    print(f"\n\n🎯 UNIQUE FAILURE PATTERNS:")
    print("="*120)
    
    issues_list = []
    for r in failed:
        issues = r.get('Issues', '').strip()
        if issues:
            issues_list.append(issues)
    
    # Count issue patterns
    from collections import Counter
    issue_patterns = Counter(issues_list)
    print(f"\nMost common issues:")
    for issue, count in issue_patterns.most_common(15):
        if issue:
            print(f"   • {issue[:100]} ({count} times)")
    
    # Analyze by keyword type
    print(f"\n\n📌 KEYWORD MISSING PATTERNS:")
    print("="*120)
    
    missing_keywords = {}
    for r in failed:
        issues = r.get('Issues', '')
        if 'Missing expected' in issues:
            # Extract the keyword
            parts = issues.split("Missing expected: '")
            if len(parts) > 1:
                keyword = parts[1].split("'")[0]
                missing_keywords[keyword] = missing_keywords.get(keyword, 0) + 1
    
    print(f"\nMost frequently missing keywords:")
    for keyword in sorted(missing_keywords.keys(), key=lambda x: missing_keywords[x], reverse=True)[:15]:
        print(f"   • '{keyword}': {missing_keywords[keyword]} times")

    return len(passed), len(failed), len(results)

if __name__ == '__main__':
    analyze_results()
