#!/usr/bin/env python3
"""
Diagnostic script to test LLM inference performance and check if GPU is being used.
High latency (>2s) typically indicates CPU-only inference.
Low latency (<1s) typically indicates GPU acceleration.
"""

import time
import requests
import json
from statistics import mean

OLLAMA_URL = "http://192.168.12.41:11434"
OLLAMA_MODEL = "qwen3:4b"

def test_ollama_performance(num_tests: int = 3) -> dict:
    """Test inference speed and estimate GPU usage."""
    
    test_query = "What is 2+2? Answer in one word."
    times = []
    
    print(f"\n🔍 Testing {OLLAMA_MODEL} performance at {OLLAMA_URL}\n")
    print(f"Running {num_tests} inference tests...\n")
    
    for i in range(num_tests):
        try:
            start = time.time()
            
            resp = requests.post(
                f"{OLLAMA_URL}/api/chat",
                json={
                    "model": OLLAMA_MODEL,
                    "messages": [
                        {"role": "system", "content": "You are helpful. Be concise."},
                        {"role": "user", "content": test_query},
                    ],
                    "stream": False,
                    "options": {
                        "temperature": 0.3,
                        "num_predict": 20,
                    },
                },
                timeout=30,
            )
            
            elapsed = time.time() - start
            times.append(elapsed)
            
            print(f"  Test {i+1}: {elapsed:.2f}s")
            
            if resp.status_code == 200:
                content = resp.json().get("message", {}).get("content", "")
                print(f"    Response: {content[:50]}")
            else:
                print(f"    ⚠️ HTTP {resp.status_code}")
        
        except Exception as e:
            print(f"  Test {i+1}: ❌ Error - {e}")
            return {"status": "failed", "error": str(e)}
    
    if not times:
        return {"status": "failed", "error": "No successful tests"}
    
    avg_time = mean(times)
    min_time = min(times)
    max_time = max(times)
    
    print(f"\n📊 Results:")
    print(f"  Average: {avg_time:.2f}s")
    print(f"  Min:     {min_time:.2f}s")
    print(f"  Max:     {max_time:.2f}s")
    
    # Estimate GPU usage based on latency
    if avg_time < 0.5:
        gpu_status = "✅ LIKELY GPU (very fast)"
    elif avg_time < 1.0:
        gpu_status = "✅ LIKELY GPU (fast)"
    elif avg_time < 2.0:
        gpu_status = "⚠️  UNCLEAR (could be GPU or strong CPU)"
    elif avg_time < 5.0:
        gpu_status = "❌ LIKELY CPU-ONLY (slow)"
    else:
        gpu_status = "❌ DEFINITELY CPU-ONLY (very slow)"
    
    print(f"\n🎯 Inference Speed Estimate: {gpu_status}")
    
    return {
        "status": "success",
        "avg_time": avg_time,
        "min_time": min_time,
        "max_time": max_time,
        "gpu_estimate": gpu_status,
    }


def check_ollama_status() -> dict:
    """Check if Ollama server is responding."""
    try:
        resp = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        if resp.status_code == 200:
            models = resp.json().get("models", [])
            qwen3_4b = [m for m in models if "qwen3:4b" in m.get("name", "")]
            return {
                "status": "online",
                "models": len(models),
                "has_qwen3_4b": bool(qwen3_4b),
            }
    except Exception as e:
        return {"status": "offline", "error": str(e)}


if __name__ == "__main__":
    print("=" * 60)
    print("LLM PERFORMANCE DIAGNOSTICS")
    print("=" * 60)
    
    # Check Ollama server
    print("\n1️⃣  Checking Ollama server status...")
    server_check = check_ollama_status()
    print(f"   Status: {server_check.get('status')}")
    if server_check.get("status") == "online":
        print(f"   Models: {server_check.get('models')}")
        print(f"   qwen3:4b available: {server_check.get('has_qwen3_4b')}")
    else:
        print(f"   ❌ Error: {server_check.get('error')}")
        exit(1)
    
    # Test performance
    print("\n2️⃣  Testing inference performance...")
    perf_check = test_ollama_performance(num_tests=3)
    
    print("\n" + "=" * 60)
    print("DIAGNOSIS SUMMARY")
    print("=" * 60)
    
    if perf_check["status"] == "success":
        avg = perf_check["avg_time"]
        estimate = perf_check["gpu_estimate"]
        
        print(f"\nAverage inference time: {avg:.2f}s")
        print(f"Estimate: {estimate}")
        
        if avg > 2.0:
            print("\n💡 RECOMMENDATIONS:")
            print("   1. SSH to 192.168.12.41 and check GPU availability:")
            print("      $ nvidia-smi  (for NVIDIA)")
            print("      $ rocm-smi    (for AMD)")
            print("\n   2. Check Ollama GPU settings:")
            print("      $ env | grep CUDA")
            print("      $ ollama serve --help | grep -i gpu")
            print("\n   3. If GPU not available:")
            print("      - Run Ollama on a different machine with GPU")
            print("      - Or: Use smaller model (qwen2.5:1.5b runs faster on CPU)")
    else:
        print(f"\n❌ Test failed: {perf_check.get('error')}")
