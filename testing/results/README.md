# FRANK Platform Testing Results

This directory contains test execution results and reports from the FRANK platform testing framework.

## Directory Structure

```
results/
├── session_[timestamp]/              # Individual test sessions
│   ├── test_config.json             # Session configuration
│   ├── functional_results.json      # Functional test results
│   ├── security_results.json        # Security test results
│   ├── performance_results.json     # Performance test results
│   ├── integration_results.json     # Integration test results
│   ├── chaos_results.json          # Chaos engineering results
│   ├── aws_test_results.json       # Infrastructure test results
│   ├── test_report.html            # Comprehensive HTML report
│   ├── test_report.json            # Machine-readable report
│   └── logs/                       # Individual test logs
├── latest/                         # Symlink to most recent session
└── archive/                        # Archived old results
```

## Report Types

### HTML Reports
- Interactive dashboards with visualizations
- Executive summaries for stakeholders
- Detailed test breakdowns with evidence
- Responsive design for mobile/tablet viewing

### JSON Reports
- Machine-readable format for automation
- CI/CD pipeline integration
- API consumption by external tools
- Detailed metrics and raw data

### Log Files
- Detailed execution logs per test category
- Debug information and error traces
- Performance timing data
- System interaction logs

## Usage

Reports are automatically generated during test execution:

```bash
# Reports saved to timestamped session directory
./run_all_tests.sh --environment staging --type all

# Custom output directory
./run_all_tests.sh --environment dev --type security --output custom_results/
```

## Retention Policy

- **Current Sessions**: Keep indefinitely
- **Recent Sessions** (< 30 days): Auto-archive
- **Old Sessions** (> 90 days): Auto-delete
- **Critical Results**: Manual archive to permanent storage

## Integration

### CI/CD Pipeline
```yaml
- name: Archive Test Results
  uses: actions/upload-artifact@v3
  with:
    name: frank-test-results
    path: testing/results/
    retention-days: 30
```

### Monitoring Integration
- CloudWatch metrics from test results
- Automated alerting on test failures
- Trending analysis for performance degradation
- Security posture monitoring

## Security

- Sanitized data only (no real threat intelligence)
- Encrypted storage for sensitive test configurations
- Access controls for production test results
- Audit trails for report access
