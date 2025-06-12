#!/usr/bin/env python3
"""
Performance and stress testing for Sentinel
Tests system performance with larger datasets and edge cases
"""

import time
import psutil
import sys
from pathlib import Path
from mock_data import MockDataGenerator

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

class PerformanceTester:
    def __init__(self):
        self.generator = MockDataGenerator()
        
    def measure_time(self, func, *args, **kwargs):
        """Measure execution time of a function"""
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        return result, end_time - start_time
    
    def measure_memory(self):
        """Get current memory usage"""
        process = psutil.Process()
        return process.memory_info().rss / 1024 / 1024  # MB
    
    def test_email_processing_performance(self, email_count=1000):
        """Test performance with large number of emails"""
        print(f"\n🚀 Performance test: Processing {email_count} emails")
        
        # Generate test emails
        print("  Generating mock emails...")
        emails, gen_time = self.measure_time(
            self.generator.generate_mock_emails, 
            email_count
        )
        print(f"  ✓ Generated {len(emails)} emails in {gen_time:.2f}s")
        
        # Memory before processing
        mem_before = self.measure_memory()
        
        try:
            from src.extraction import FallbackExtractor
            extractor = FallbackExtractor()
            
            print("  Processing emails...")
            start_time = time.time()
            
            opportunities_found = 0
            for email in emails:
                opportunity = extractor.extract_opportunity(
                    email["subject"],
                    email["sender"],
                    email["content"]
                )
                if opportunity:
                    opportunities_found += 1
            
            processing_time = time.time() - start_time
            mem_after = self.measure_memory()
            
            print(f"  ✓ Processed {email_count} emails in {processing_time:.2f}s")
            print(f"  ✓ Found {opportunities_found} opportunities")
            print(f"  ✓ Processing rate: {email_count/processing_time:.1f} emails/sec")
            print(f"  ✓ Memory usage: {mem_before:.1f}MB → {mem_after:.1f}MB (Δ{mem_after-mem_before:.1f}MB)")
            
            return True
            
        except Exception as e:
            print(f"  ❌ Performance test failed: {e}")
            return False
    
    def test_memory_leak(self, iterations=100):
        """Test for memory leaks during repeated processing"""
        print(f"\n🔍 Memory leak test: {iterations} iterations")
        
        try:
            from src.extraction import FallbackExtractor
            extractor = FallbackExtractor()
            
            # Single test email
            test_email = self.generator.generate_mock_emails(1)[0]
            
            memory_readings = []
            
            for i in range(iterations):
                # Process email
                extractor.extract_opportunity(
                    test_email["subject"],
                    test_email["sender"],
                    test_email["content"]
                )
                
                # Record memory every 10 iterations
                if i % 10 == 0:
                    memory_readings.append(self.measure_memory())
            
            # Check for memory growth
            initial_memory = memory_readings[0]
            final_memory = memory_readings[-1]
            memory_growth = final_memory - initial_memory
            
            print(f"  ✓ Initial memory: {initial_memory:.1f}MB")
            print(f"  ✓ Final memory: {final_memory:.1f}MB")
            print(f"  ✓ Memory growth: {memory_growth:.1f}MB")
            
            if memory_growth < 10:  # Less than 10MB growth is acceptable
                print("  ✅ No significant memory leak detected")
                return True
            else:
                print("  ⚠️  Potential memory leak detected")
                return False
                
        except Exception as e:
            print(f"  ❌ Memory leak test failed: {e}")
            return False
    
    def test_edge_cases(self):
        """Test system with edge cases and malformed data"""
        print("\n🎯 Edge case testing")
        
        edge_cases = [
            {"subject": "", "sender": "", "content": ""},  # Empty fields
            {"subject": "A" * 1000, "sender": "test@example.com", "content": "B" * 10000},  # Very long text
            {"subject": "Test 🚀 🎉", "sender": "test@🌟.com", "content": "Unicode test 中文 العربية"},  # Unicode
            {"subject": None, "sender": None, "content": None},  # None values
            {"subject": "Test", "sender": "invalid-email", "content": "<script>alert('xss')</script>"},  # Invalid/malicious
        ]
        
        try:
            from src.extraction import FallbackExtractor
            extractor = FallbackExtractor()
            
            passed = 0
            failed = 0
            
            for i, case in enumerate(edge_cases):
                try:
                    result = extractor.extract_opportunity(
                        case.get("subject"),
                        case.get("sender"),
                        case.get("content")
                    )
                    print(f"  ✓ Edge case {i+1}: Handled gracefully")
                    passed += 1
                except Exception as e:
                    print(f"  ❌ Edge case {i+1}: Failed - {e}")
                    failed += 1
            
            print(f"  Summary: {passed} passed, {failed} failed")
            return failed == 0
            
        except Exception as e:
            print(f"  ❌ Edge case testing failed: {e}")
            return False

def run_performance_tests():
    """Run all performance tests"""
    print("SENTINEL PERFORMANCE & STRESS TESTING")
    print("=" * 50)
    
    tester = PerformanceTester()
    
    tests = [
        ("Small dataset (100 emails)", lambda: tester.test_email_processing_performance(100)),
        ("Medium dataset (1000 emails)", lambda: tester.test_email_processing_performance(1000)),
        ("Memory leak test", lambda: tester.test_memory_leak(100)),
        ("Edge cases", lambda: tester.test_edge_cases()),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        try:
            if test_func():
                passed += 1
                print(f"✅ {test_name} PASSED")
            else:
                print(f"❌ {test_name} FAILED")
        except Exception as e:
            print(f"❌ {test_name} CRASHED: {e}")
    
    print(f"\n{'='*50}")
    print(f"PERFORMANCE TEST SUMMARY: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All performance tests passed! System is performant and stable.")
    else:
        print("⚠️  Some performance tests failed. Consider optimization.")
    
    return passed == total

if __name__ == "__main__":
    run_performance_tests()
