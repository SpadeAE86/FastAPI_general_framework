
import sys
import os

# Ensure src directory is in python path
sys.path.append(os.path.join(os.getcwd(), "src"))

from config.config import my_config, ENV
from core.health_monitor.metric_reporter import MetricReporter

def verify_monitoring_config():
    print(f"Current Environment: {ENV}")
    
    # Instantiate MetricReporter
    reporter = MetricReporter()
    
    print("\n--- MetricReporter Configuration ---")
    print(f"Enabled: {reporter.enabled}")
    print(f"Report Interval: {reporter.report_interval}")
    print(f"Queues to Monitor: {reporter.queues}")
    print(f"Namespace: {reporter.namespace}")
    print(f"Metric Name: {reporter.metric_name}")
    
    # Expected queues check
    expected_prefixes = [f"{ENV}_"]
    if not reporter.queues:
        print("\n[ERROR] No queues configured!")
        return
        
    for queue in reporter.queues:
        if not queue.startswith(f"{ENV}_"):
            print(f"\n[ERROR] Queue '{queue}' does not start with expected prefix '{ENV}_'")
    
    print("\n[SUCCESS] MetricReporter configuration verification completed.")

if __name__ == "__main__":
    verify_monitoring_config()
