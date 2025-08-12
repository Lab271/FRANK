#!/usr/bin/env python3
"""
FRANK Platform - Test Report Generator
Generate comprehensive HTML and JSON reports from test results.
"""

import json
import os
import time
from datetime import datetime
from typing import Dict, List, Any
from pathlib import Path

class TestReportGenerator:
    """Generate comprehensive test reports in multiple formats"""
    
    def __init__(self, session_id: str, output_dir: str = "reports"):
        self.session_id = session_id
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        self.results = {}
        self.metadata = {
            'session_id': session_id,
            'generated_at': datetime.utcnow().isoformat(),
            'generator_version': '1.0'
        }
    
    def add_test_results(self, category: str, results: List[Dict]):
        """Add test results for a specific category"""
        self.results[category] = results
    
    def generate_html_report(self) -> str:
        """Generate comprehensive HTML report"""
        html_file = self.output_dir / f"frank_test_report_{self.session_id}.html"
        
        # Calculate overall statistics
        total_tests = sum(len(results) for results in self.results.values())
        total_passed = sum(
            len([r for r in results if r.get('status') == 'PASS']) 
            for results in self.results.values()
        )
        total_failed = sum(
            len([r for r in results if r.get('status') == 'FAIL']) 
            for results in self.results.values()
        )
        total_warnings = sum(
            len([r for r in results if r.get('status') == 'WARNING']) 
            for results in self.results.values()
        )
        
        pass_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0
        
        html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>FRANK Platform Security Test Report</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
            color: #333;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            overflow: hidden;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }}
        .header h1 {{
            margin: 0;
            font-size: 2.5em;
            font-weight: 300;
        }}
        .header p {{
            margin: 10px 0 0;
            opacity: 0.9;
            font-size: 1.1em;
        }}
        .summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            padding: 30px;
            background: #fafafa;
        }}
        .summary-card {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }}
        .summary-card h3 {{
            margin: 0 0 10px;
            color: #666;
            font-size: 0.9em;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        .summary-card .value {{
            font-size: 2.5em;
            font-weight: bold;
            margin: 0;
        }}
        .pass {{ color: #27ae60; }}
        .fail {{ color: #e74c3c; }}
        .warning {{ color: #f39c12; }}
        .total {{ color: #3498db; }}
        .section {{
            margin: 0 30px 30px;
            background: white;
            border-radius: 8px;
            overflow: hidden;
        }}
        .section-header {{
            background: #34495e;
            color: white;
            padding: 15px 20px;
            font-size: 1.2em;
            font-weight: 500;
        }}
        .test-grid {{
            display: grid;
            gap: 1px;
            background: #ecf0f1;
        }}
        .test-item {{
            background: white;
            padding: 15px 20px;
            display: grid;
            grid-template-columns: 1fr auto auto;
            align-items: center;
            gap: 15px;
        }}
        .test-name {{
            font-weight: 500;
        }}
        .test-description {{
            color: #666;
            font-size: 0.9em;
        }}
        .test-status {{
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 0.85em;
            font-weight: bold;
            text-transform: uppercase;
        }}
        .status-pass {{
            background: #d5e8d4;
            color: #27ae60;
        }}
        .status-fail {{
            background: #f8d7da;
            color: #e74c3c;
        }}
        .status-warning {{
            background: #fff3cd;
            color: #856404;
        }}
        .test-time {{
            color: #666;
            font-size: 0.9em;
        }}
        .category-summary {{
            padding: 20px;
            background: #f8f9fa;
            border-bottom: 1px solid #ecf0f1;
        }}
        .progress-bar {{
            width: 100%;
            height: 8px;
            background: #ecf0f1;
            border-radius: 4px;
            overflow: hidden;
            margin: 10px 0;
        }}
        .progress-fill {{
            height: 100%;
            background: linear-gradient(90deg, #27ae60, #2ecc71);
        }}
        .details {{
            padding: 20px;
            border-top: 1px solid #ecf0f1;
            background: #f8f9fa;
            margin-top: 10px;
        }}
        .details h4 {{
            margin: 0 0 10px;
            color: #2c3e50;
        }}
        .details pre {{
            background: white;
            padding: 15px;
            border-radius: 4px;
            overflow-x: auto;
            border: 1px solid #ddd;
        }}
        .metadata {{
            padding: 20px 30px;
            background: #2c3e50;
            color: white;
            text-align: center;
        }}
        .metadata h3 {{
            margin: 0 0 15px;
            color: #ecf0f1;
        }}
        .metadata-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
        }}
        .metadata-item {{
            text-align: left;
        }}
        .metadata-label {{
            color: #bdc3c7;
            font-size: 0.9em;
        }}
        .metadata-value {{
            font-weight: bold;
            margin-top: 5px;
        }}
        @media (max-width: 768px) {{
            .test-item {{
                grid-template-columns: 1fr;
                gap: 10px;
            }}
            .summary {{
                grid-template-columns: repeat(2, 1fr);
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>FRANK Platform Security Test Report</h1>
            <p>Comprehensive Security Assessment Results</p>
            <p>Session: {self.session_id} | Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>
        
        <div class="summary">
            <div class="summary-card">
                <h3>Total Tests</h3>
                <p class="value total">{total_tests}</p>
            </div>
            <div class="summary-card">
                <h3>Passed</h3>
                <p class="value pass">{total_passed}</p>
            </div>
            <div class="summary-card">
                <h3>Failed</h3>
                <p class="value fail">{total_failed}</p>
            </div>
            <div class="summary-card">
                <h3>Warnings</h3>
                <p class="value warning">{total_warnings}</p>
            </div>
            <div class="summary-card">
                <h3>Pass Rate</h3>
                <p class="value total">{pass_rate:.1f}%</p>
            </div>
        </div>
"""
        
        # Generate sections for each test category
        for category, results in self.results.items():
            if not results:
                continue
                
            category_passed = len([r for r in results if r.get('status') == 'PASS'])
            category_failed = len([r for r in results if r.get('status') == 'FAIL'])
            category_warnings = len([r for r in results if r.get('status') == 'WARNING'])
            category_total = len(results)
            category_pass_rate = (category_passed / category_total * 100) if category_total > 0 else 0
            
            html_content += f"""
        <div class="section">
            <div class="section-header">
                {category.replace('_', ' ').title()} Tests
            </div>
            <div class="category-summary">
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 20px; margin-bottom: 15px;">
                    <div>
                        <div class="metadata-label">Total</div>
                        <div class="metadata-value">{category_total}</div>
                    </div>
                    <div>
                        <div class="metadata-label">Passed</div>
                        <div class="metadata-value pass">{category_passed}</div>
                    </div>
                    <div>
                        <div class="metadata-label">Failed</div>
                        <div class="metadata-value fail">{category_failed}</div>
                    </div>
                    <div>
                        <div class="metadata-label">Warnings</div>
                        <div class="metadata-value warning">{category_warnings}</div>
                    </div>
                    <div>
                        <div class="metadata-label">Pass Rate</div>
                        <div class="metadata-value">{category_pass_rate:.1f}%</div>
                    </div>
                </div>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: {category_pass_rate}%"></div>
                </div>
            </div>
            <div class="test-grid">
"""
            
            for result in results:
                status = result.get('status', 'UNKNOWN')
                test_name = result.get('test_name', 'Unknown Test')
                description = result.get('description', '')
                execution_time = result.get('execution_time', 0)
                
                status_class = f"status-{status.lower()}"
                
                html_content += f"""
                <div class="test-item">
                    <div>
                        <div class="test-name">{test_name}</div>
                        <div class="test-description">{description}</div>
                    </div>
                    <div class="test-status {status_class}">{status}</div>
                    <div class="test-time">{execution_time:.2f}s</div>
                </div>
"""
                
                # Add details if available
                if result.get('evidence') or result.get('remediation'):
                    html_content += f"""
                <div class="details">
"""
                    if result.get('evidence'):
                        html_content += f"""
                    <h4>Evidence:</h4>
                    <pre>{result['evidence']}</pre>
"""
                    if result.get('remediation'):
                        html_content += f"""
                    <h4>Remediation:</h4>
                    <pre>{result['remediation']}</pre>
"""
                    html_content += "</div>"
            
            html_content += """
            </div>
        </div>
"""
        
        # Add metadata section
        html_content += f"""
        <div class="metadata">
            <h3>Test Session Metadata</h3>
            <div class="metadata-grid">
                <div class="metadata-item">
                    <div class="metadata-label">Session ID</div>
                    <div class="metadata-value">{self.session_id}</div>
                </div>
                <div class="metadata-item">
                    <div class="metadata-label">Generated At</div>
                    <div class="metadata-value">{self.metadata['generated_at']}</div>
                </div>
                <div class="metadata-item">
                    <div class="metadata-label">Generator Version</div>
                    <div class="metadata-value">{self.metadata['generator_version']}</div>
                </div>
                <div class="metadata-item">
                    <div class="metadata-label">Categories Tested</div>
                    <div class="metadata-value">{len(self.results)}</div>
                </div>
            </div>
        </div>
    </div>
</body>
</html>
"""
        
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        return str(html_file)
    
    def generate_json_report(self) -> str:
        """Generate JSON report"""
        json_file = self.output_dir / f"frank_test_report_{self.session_id}.json"
        
        # Calculate statistics
        report_data = {
            'metadata': self.metadata,
            'summary': self._calculate_summary(),
            'categories': {},
            'detailed_results': self.results
        }
        
        # Add category summaries
        for category, results in self.results.items():
            report_data['categories'][category] = self._calculate_category_summary(results)
        
        with open(json_file, 'w') as f:
            json.dump(report_data, f, indent=2)
        
        return str(json_file)
    
    def _calculate_summary(self) -> Dict:
        """Calculate overall summary statistics"""
        total_tests = sum(len(results) for results in self.results.values())
        total_passed = sum(
            len([r for r in results if r.get('status') == 'PASS']) 
            for results in self.results.values()
        )
        total_failed = sum(
            len([r for r in results if r.get('status') == 'FAIL']) 
            for results in self.results.values()
        )
        total_warnings = sum(
            len([r for r in results if r.get('status') == 'WARNING']) 
            for results in self.results.values()
        )
        
        return {
            'total_tests': total_tests,
            'passed': total_passed,
            'failed': total_failed,
            'warnings': total_warnings,
            'pass_rate': (total_passed / total_tests * 100) if total_tests > 0 else 0,
            'categories_tested': len(self.results)
        }
    
    def _calculate_category_summary(self, results: List[Dict]) -> Dict:
        """Calculate summary for a specific category"""
        total = len(results)
        passed = len([r for r in results if r.get('status') == 'PASS'])
        failed = len([r for r in results if r.get('status') == 'FAIL'])
        warnings = len([r for r in results if r.get('status') == 'WARNING'])
        
        return {
            'total': total,
            'passed': passed,
            'failed': failed,
            'warnings': warnings,
            'pass_rate': (passed / total * 100) if total > 0 else 0
        }

def main():
    """Example usage of the report generator"""
    # Example test results
    sample_results = {
        'functional': [
            {
                'test_name': 'API Authentication',
                'status': 'PASS',
                'description': 'Authentication endpoint validation',
                'execution_time': 0.5
            },
            {
                'test_name': 'Data Processing',
                'status': 'FAIL',
                'description': 'Threat data processing validation',
                'execution_time': 1.2,
                'evidence': 'Invalid response format',
                'remediation': 'Fix response serialization'
            }
        ],
        'security': [
            {
                'test_name': 'SQL Injection',
                'status': 'PASS',
                'description': 'SQL injection vulnerability test',
                'execution_time': 0.8
            },
            {
                'test_name': 'XSS Protection',
                'status': 'WARNING',
                'description': 'Cross-site scripting protection',
                'execution_time': 0.6,
                'evidence': 'Some XSS vectors not blocked',
                'remediation': 'Implement comprehensive input sanitization'
            }
        ]
    }
    
    # Generate reports
    generator = TestReportGenerator('test_session_123')
    
    for category, results in sample_results.items():
        generator.add_test_results(category, results)
    
    html_file = generator.generate_html_report()
    json_file = generator.generate_json_report()
    
    print(f"Generated HTML report: {html_file}")
    print(f"Generated JSON report: {json_file}")

if __name__ == '__main__':
    main()
