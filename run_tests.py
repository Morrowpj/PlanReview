#!/usr/bin/env python3
"""
Comprehensive test runner for PlanReview FastAPI application.
Runs all tests and collects detailed results with coverage reporting.
"""

import os
import sys
import subprocess
import argparse
import json
from datetime import datetime
from pathlib import Path

def run_command(command, cwd=None):
    """Run a command and return the result"""
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=cwd
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode
        }
    except Exception as e:
        return {
            "success": False,
            "stdout": "",
            "stderr": str(e),
            "returncode": -1
        }

def ensure_dependencies():
    """Ensure test dependencies are installed"""
    print("🔧 Installing/updating test dependencies...")
    
    result = run_command("pip install -r requirements.txt")
    if not result["success"]:
        print(f"❌ Failed to install dependencies: {result['stderr']}")
        return False
    
    print("✅ Dependencies installed successfully")
    return True

def run_pytest(test_path=None, verbose=False, coverage=True, html_report=True):
    """Run pytest with various options"""
    
    # Base pytest command
    cmd_parts = ["PYTHONPATH=. python", "-m", "pytest"]
    
    # Add test path if specified
    if test_path:
        cmd_parts.append(test_path)
    else:
        cmd_parts.append("tests/")
    
    # Add verbosity
    if verbose:
        cmd_parts.append("-v")
    else:
        cmd_parts.append("-q")
    
    # Add coverage reporting
    if coverage:
        cmd_parts.extend([
            "--cov=api",
            "--cov-report=term-missing",
            "--cov-report=json:test_results/coverage.json"
        ])
        
        if html_report:
            cmd_parts.append("--cov-report=html:test_results/coverage_html")
    
    # Add other useful options
    cmd_parts.extend([
        "--tb=short",
        "--strict-markers",
        "--disable-warnings",
        f"--junitxml=test_results/junit.xml"
    ])
    
    # Ensure results directory exists
    os.makedirs("test_results", exist_ok=True)
    
    command = " ".join(cmd_parts)
    print(f"🧪 Running tests: {command}")
    
    result = run_command(command)
    return result

def run_specific_test_suite(suite_name, verbose=False):
    """Run a specific test suite"""
    test_files = {
        "auth": "tests/test_auth.py",
        "conversations": "tests/test_conversations.py", 
        "chat": "tests/test_chat.py",
        "reviewrooms": "tests/test_reviewrooms.py",
        "integration": "tests/test_integration.py",
    }
    
    if suite_name not in test_files:
        print(f"❌ Unknown test suite: {suite_name}")
        print(f"Available suites: {', '.join(test_files.keys())}")
        return {
            "success": False,
            "stdout": "",
            "stderr": f"Unknown test suite: {suite_name}",
            "returncode": 1
        }
    
    print(f"🧪 Running {suite_name} tests...")
    result = run_pytest(test_files[suite_name], verbose=verbose, coverage=False)
    
    return result

def generate_test_report(results):
    """Generate a comprehensive test report"""
    
    report = {
        "timestamp": datetime.now().isoformat(),
        "overall_success": results["pytest"]["success"],
        "test_results": results,
        "summary": {}
    }
    
    # Parse pytest output for summary
    if results["pytest"]["stdout"]:
        stdout = results["pytest"]["stdout"]
        
        # Extract test counts
        if "passed" in stdout:
            import re
            # Look for pattern like "25 passed, 3 failed, 2 skipped"
            pattern = r"(\d+) passed.*?(\d+) failed.*?(\d+) skipped"
            match = re.search(pattern, stdout)
            if match:
                report["summary"]["passed"] = int(match.group(1))
                report["summary"]["failed"] = int(match.group(2)) 
                report["summary"]["skipped"] = int(match.group(3))
    
    # Load coverage data if available
    coverage_file = Path("test_results/coverage.json")
    if coverage_file.exists():
        try:
            with open(coverage_file) as f:
                coverage_data = json.load(f)
                report["coverage"] = {
                    "total_coverage": coverage_data.get("totals", {}).get("percent_covered", 0),
                    "files": coverage_data.get("files", {})
                }
        except Exception as e:
            print(f"⚠️  Could not load coverage data: {e}")
    
    # Save report
    os.makedirs("test_results", exist_ok=True)
    with open("test_results/test_report.json", "w") as f:
        json.dump(report, f, indent=2)
    
    return report

def print_summary(report):
    """Print a formatted test summary"""
    
    print("\n" + "="*60)
    print("🧪 TEST SUMMARY")
    print("="*60)
    
    # Overall status
    if report["overall_success"]:
        print("✅ Overall Status: PASSED")
    else:
        print("❌ Overall Status: FAILED")
    
    # Test counts
    summary = report.get("summary", {})
    if summary:
        print(f"\n📊 Test Results:")
        print(f"   ✅ Passed: {summary.get('passed', 0)}")
        print(f"   ❌ Failed: {summary.get('failed', 0)}")
        print(f"   ⏭️  Skipped: {summary.get('skipped', 0)}")
    
    # Coverage
    coverage = report.get("coverage", {})
    if coverage:
        total_coverage = coverage.get("total_coverage", 0)
        print(f"\n📈 Code Coverage: {total_coverage:.1f}%")
        
        if total_coverage >= 90:
            print("   🎉 Excellent coverage!")
        elif total_coverage >= 80:
            print("   👍 Good coverage")
        elif total_coverage >= 70:
            print("   ⚠️  Acceptable coverage")
        else:
            print("   🔴 Coverage needs improvement")
    
    # Files and reports
    print(f"\n📁 Results saved to:")
    print(f"   - Detailed report: test_results/test_report.json")
    print(f"   - JUnit XML: test_results/junit.xml")
    
    if coverage:
        print(f"   - Coverage JSON: test_results/coverage.json") 
        print(f"   - Coverage HTML: test_results/coverage_html/index.html")
    
    print("\n" + "="*60)

def main():
    """Main test runner function"""
    
    parser = argparse.ArgumentParser(description="Run PlanReview API tests")
    parser.add_argument(
        "--suite", 
        choices=["auth", "conversations", "chat", "reviewrooms", "integration", "all"],
        default="all",
        help="Test suite to run (default: all)"
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--no-coverage", action="store_true", help="Skip coverage reporting")
    parser.add_argument("--no-html", action="store_true", help="Skip HTML coverage report")
    parser.add_argument("--install-deps", action="store_true", help="Install dependencies before running")
    
    args = parser.parse_args()
    
    print("🚀 PlanReview API Test Runner")
    print(f"📅 Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Install dependencies if requested
    if args.install_deps:
        if not ensure_dependencies():
            sys.exit(1)
    
    # Initialize results
    results = {}
    
    # Run tests
    if args.suite == "all":
        print("\n🧪 Running all test suites...")
        result = run_pytest(
            verbose=args.verbose,
            coverage=not args.no_coverage,
            html_report=not args.no_html
        )
        results["pytest"] = result
        
    else:
        print(f"\n🧪 Running {args.suite} test suite...")
        result = run_specific_test_suite(args.suite, verbose=args.verbose)
        results["pytest"] = result
    
    # Generate and display report
    report = generate_test_report(results)
    print_summary(report)
    
    # Exit with appropriate code
    if report["overall_success"]:
        print("🎉 All tests passed!")
        sys.exit(0)
    else:
        print("💥 Some tests failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()