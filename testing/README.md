# FRANK Platform Testing Framework

## Overview

The FRANK Platform Testing Framework is a comprehensive security testing suite designed to validate the functionality, security, and resilience of the FRANK threat intelligence sharing platform. This framework covers all aspects of testing from basic functional validation to advanced security assessments and attack simulations.

## Framework Architecture

```
testing/
├── README.md                           # This documentation
├── requirements.txt                    # Python dependencies
├── run_all_tests.sh                   # Master test runner script
├── results/                           # Test execution results
├── functional/                        # Functional testing modules
│   └── api-tests/
│       └── test_api_endpoints.py      # Comprehensive API testing
├── security/                          # Security validation tests
├── exploits/                          # Vulnerability testing
│   └── owasp-top10/
│       └── test_owasp_top10.py        # OWASP Top 10 2021 tests
├── attacks/                           # Attack simulation
│   └── red-team/
│       └── apt_simulation.py          # Advanced Persistent Threat simulation
├── performance/                       # Performance and load testing
│   └── load_testing.py               # Comprehensive load testing
├── infrastructure/                    # Infrastructure validation
│   └── aws_testing.py                # AWS service configuration testing
├── chaos/                             # Chaos engineering
│   └── chaos_engineering.py          # System resilience testing
├── integration/                       # End-to-end testing
│   └── integration_tests.py          # Complete workflow testing
└── tools/                             # Testing utilities
```

## Testing Categories

### 1. Functional Testing
**Purpose**: Validate core platform functionality and API behavior
**Location**: `functional/`

- **API Endpoint Testing**: Comprehensive validation of all REST API endpoints
  - Authentication flows (login, logout, token refresh)
  - CRUD operations for threats, users, organizations
  - Search functionality and filtering
  - Data validation and error handling
  - Multi-tenancy and access controls

### 2. Security Testing
**Purpose**: Identify security vulnerabilities and validate security controls
**Location**: `security/` and `exploits/`

- **OWASP Top 10 2021 Testing**:
  - A01: Broken Access Control
  - A02: Cryptographic Failures
  - A03: Injection Attacks
  - A04: Insecure Design
  - A05: Security Misconfiguration
  - A06: Vulnerable and Outdated Components
  - A07: Identification and Authentication Failures
  - A08: Software and Data Integrity Failures
  - A09: Security Logging and Monitoring Failures
  - A10: Server-Side Request Forgery (SSRF)

### 3. Attack Simulation
**Purpose**: Simulate real-world attack scenarios to test defensive capabilities
**Location**: `attacks/`

- **Advanced Persistent Threat (APT) Simulation**:
  - Reconnaissance phase
  - Initial access attempts
  - Persistence establishment
  - Lateral movement
  - Data exfiltration
  - Command and control communication

### 4. Performance Testing
**Purpose**: Validate system performance under various load conditions
**Location**: `performance/`

- **Load Testing**: Normal operational load simulation
- **Stress Testing**: Identifying breaking points
- **Volume Testing**: Large data set handling
- **Endurance Testing**: Extended operation periods

### 5. Infrastructure Testing
**Purpose**: Validate AWS infrastructure configuration and security
**Location**: `infrastructure/`

- **AWS Service Configuration**:
  - Lambda function validation
  - API Gateway configuration
  - DynamoDB table setup
  - S3 bucket security
  - Cognito user pool configuration
  - CloudWatch monitoring setup

### 6. Chaos Engineering
**Purpose**: Test system resilience under failure conditions
**Location**: `chaos/`

- **Failure Simulation**:
  - Service degradation
  - Network partitions
  - Resource exhaustion
  - Third-party service failures

### 7. Integration Testing
**Purpose**: Validate end-to-end workflows and system integration
**Location**: `integration/`

- **Complete Workflows**:
  - User registration and authentication
  - Threat data submission and processing
  - Search and retrieval operations
  - Multi-tenant data isolation
  - Data pipeline processing

## Quick Start

### Prerequisites

1. **Python 3.8+** with pip
2. **AWS CLI** configured (for infrastructure tests)
3. **Access to FRANK platform** (staging/development environment)

### Installation

```bash
# Clone the repository
cd /path/to/FRANK

# Install Python dependencies
pip install -r testing/requirements.txt

# Make test runner executable
chmod +x testing/run_all_tests.sh
```

### Basic Usage

```bash
# Run all tests against staging environment
./testing/run_all_tests.sh --environment staging --url https://api.frank.staging.com --type all

# Run only functional tests
./testing/run_all_tests.sh --environment dev --url https://api.frank.dev.com --type functional

# Run security tests with verbose output
./testing/run_all_tests.sh --environment staging --url https://api.frank.staging.com --type security --verbose

# Run specific test categories
./testing/run_all_tests.sh --url https://api.frank.dev.com --type "functional,security,performance"
```

## Test Execution Options

### Environment Types
- `dev`: Development environment (all tests enabled)
- `staging`: Staging environment (all tests enabled)
- `prod`: Production environment (destructive tests disabled)

### Test Types
- `functional`: API and functionality tests
- `security`: Security vulnerability tests
- `performance`: Load and performance tests
- `infrastructure`: AWS infrastructure validation
- `chaos`: Chaos engineering tests (non-production only)
- `integration`: End-to-end workflow tests
- `exploits`: Vulnerability exploitation tests (non-production only)
- `attacks`: Attack simulation tests (non-production only)
- `all`: All applicable tests for the environment

### Command Line Options

```bash
Usage: ./run_all_tests.sh [OPTIONS]

Options:
  -e, --environment ENV    Target environment (dev|staging|prod)
  -u, --url URL           Base URL of the FRANK API
  -t, --type TYPE         Test types to run (comma-separated or 'all')
  -f, --format FORMAT     Report format (json|html|xml)
  -o, --output DIR        Output directory for results
  -p, --parallel          Enable parallel test execution
  -v, --verbose           Enable verbose logging
  -h, --help              Show this help message

Examples:
  ./run_all_tests.sh -e staging -u https://api.frank.staging.com -t all
  ./run_all_tests.sh -e dev -u https://localhost:8000 -t functional,security
  ./run_all_tests.sh -e staging -u https://api.frank.staging.com -t performance -f html
```

## Individual Test Modules

### API Testing
```bash
cd testing/functional/api-tests
python test_api_endpoints.py --url https://api.frank.dev.com --output results.json
```

### OWASP Security Testing
```bash
cd testing/exploits/owasp-top10
python test_owasp_top10.py --url https://api.frank.staging.com --output owasp_results.json
```

### Load Testing
```bash
cd testing/performance
python load_testing.py --url https://api.frank.staging.com --test-type load --output load_results.json
```

### Infrastructure Testing
```bash
cd testing/infrastructure
python aws_testing.py --region us-west-2 --output aws_results.json
```

### Chaos Engineering
```bash
cd testing/chaos
python chaos_engineering.py --environment staging --output chaos_results.json
```

### Integration Testing
```bash
cd testing/integration
python integration_tests.py --url https://api.frank.staging.com --workflow all --output integration_results.json
```

## Report Generation

Test results are automatically generated in multiple formats:

### JSON Reports
- Machine-readable format
- Detailed test results and metrics
- Easy integration with CI/CD pipelines

### HTML Reports
- Human-readable format
- Interactive dashboards
- Executive summaries
- Detailed test breakdowns

### Test Result Structure
```json
{
  "session_id": "20241201_143022",
  "timestamp": "2024-12-01T14:30:22Z",
  "environment": "staging",
  "target_url": "https://api.frank.staging.com",
  "summary": {
    "total_tests": 150,
    "passed": 142,
    "failed": 3,
    "warnings": 5,
    "execution_time": 1847.2
  },
  "categories": {
    "functional": { "passed": 45, "failed": 0, "warnings": 1 },
    "security": { "passed": 38, "failed": 2, "warnings": 3 },
    "performance": { "passed": 25, "failed": 0, "warnings": 1 },
    "infrastructure": { "passed": 34, "failed": 1, "warnings": 0 }
  }
}
```

## Security Considerations

### Test Environment Isolation
- Never run destructive tests against production
- Use dedicated test environments
- Implement proper access controls
- Monitor test execution

### Data Protection
- Use synthetic test data only
- Implement data cleanup procedures
- Respect data retention policies
- Anonymize sensitive information

### Access Control
- Implement role-based access for testing
- Use temporary credentials when possible
- Audit test execution activities
- Secure test result storage

## CI/CD Integration

### GitHub Actions Example
```yaml
name: FRANK Security Testing
on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  security-tests:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    - name: Set up Python
      uses: actions/setup-python@v3
      with:
        python-version: '3.11'
    - name: Install dependencies
      run: |
        pip install -r testing/requirements.txt
    - name: Run security tests
      run: |
        ./testing/run_all_tests.sh --environment staging --url ${{ secrets.STAGING_URL }} --type security
    - name: Upload results
      uses: actions/upload-artifact@v3
      with:
        name: test-results
        path: testing/results/
```

### Jenkins Pipeline Example
```groovy
pipeline {
    agent any
    
    environment {
        FRANK_API_URL = credentials('frank-staging-url')
        FRANK_AUTH_TOKEN = credentials('frank-test-token')
    }
    
    stages {
        stage('Setup') {
            steps {
                sh 'pip install -r testing/requirements.txt'
            }
        }
        
        stage('Security Tests') {
            steps {
                sh './testing/run_all_tests.sh --environment staging --url $FRANK_API_URL --type security --format html'
            }
        }
        
        stage('Performance Tests') {
            steps {
                sh './testing/run_all_tests.sh --environment staging --url $FRANK_API_URL --type performance'
            }
        }
    }
    
    post {
        always {
            archiveArtifacts artifacts: 'testing/results/**/*', fingerprint: true
            publishHTML([
                allowMissing: false,
                alwaysLinkToLastBuild: true,
                keepAll: true,
                reportDir: 'testing/results',
                reportFiles: '*.html',
                reportName: 'FRANK Security Test Report'
            ])
        }
    }
}
```

## Troubleshooting

### Common Issues

1. **Authentication Failures**
   - Verify API credentials
   - Check token expiration
   - Validate environment configuration

2. **Network Connectivity**
   - Verify target URL accessibility
   - Check firewall rules
   - Validate DNS resolution

3. **Permission Errors**
   - Verify file permissions for test scripts
   - Check write permissions for result directories
   - Validate AWS credentials for infrastructure tests

4. **Dependency Issues**
   - Update Python packages: `pip install -r testing/requirements.txt --upgrade`
   - Check Python version compatibility
   - Verify system dependencies

### Debug Mode

Enable verbose logging for troubleshooting:
```bash
./testing/run_all_tests.sh --verbose --environment dev --url https://api.frank.dev.com --type functional
```

### Log Analysis

Test execution logs are available in:
- `testing/results/session_[timestamp]/`
- Individual test module logs
- Detailed error traces and stack dumps

## Contributing

### Adding New Tests

1. **Choose appropriate category** (functional, security, performance, etc.)
2. **Follow naming conventions** (`test_*.py`)
3. **Implement proper logging** and error handling
4. **Add cleanup procedures** for created resources
5. **Update documentation** and test runner scripts

### Test Development Guidelines

- Use descriptive test names and docstrings
- Implement proper assertion mechanisms
- Handle test data lifecycle (creation/cleanup)
- Follow security best practices
- Add comprehensive error handling

## Support

For questions, issues, or contributions:
- Review existing documentation
- Check troubleshooting section
- Create GitHub issues for bug reports
- Submit pull requests for improvements

## Version History

- **v1.0.0**: Initial comprehensive testing framework
  - Functional API testing
  - OWASP Top 10 security tests
  - APT attack simulation
  - Performance and load testing
  - AWS infrastructure validation
  - Chaos engineering capabilities
  - End-to-end integration testing
