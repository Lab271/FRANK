#!/usr/bin/env python3
"""
Security Log Analysis MCP Server
Generates synthetic security logs using Faker for incident response demos
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Any, Sequence
import random

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
from faker import Faker

# Initialize Faker
fake = Faker()
Faker.seed(0)  # For reproducible demos, remove for random data

# Configuration
ATTACKER_IP = "203.0.113.42"
ATTACKER_COUNTRY = "North Korea"
TARGET_SERVER = "web-server-01"
DB_SERVER = "db-server-01"
NORMAL_USER_COUNT = 8

# Global cache for logs
_cached_logs = None
_attack_timeline = None

class SecurityLogGenerator:
    """Generates synthetic security logs with realistic attack patterns"""
    
    def __init__(self):
        self.fake = Faker()
        self.normal_users = self._generate_normal_users()
        
    def _generate_normal_users(self):
        """Generate consistent normal users with profiles"""
        users = []
        for _ in range(NORMAL_USER_COUNT):
            users.append({
                'username': self.fake.user_name(),
                'ip': self.fake.ipv4_private(),
                'department': self.fake.random_element([
                    'Engineering', 'Marketing', 'Sales', 'HR', 
                    'Finance', 'Operations', 'IT', 'Legal'
                ]),
                'email': self.fake.email()
            })
        return users
    
    def generate_ssh_logs(self, start_time: datetime, duration_hours: int = 2):
        """Generate SSH authentication logs with brute force attack"""
        logs = []
        current_time = start_time
        end_time = start_time + timedelta(hours=duration_hours)
        
        # Phase 1: Normal legitimate logins (first 45 minutes)
        phase1_end = start_time + timedelta(minutes=45)
        while current_time < phase1_end:
            user = self.fake.random_element(self.normal_users)
            logs.append({
                'timestamp': current_time.isoformat(),
                'log_type': 'ssh',
                'host': TARGET_SERVER,
                'service': 'sshd',
                'pid': self.fake.random_int(1000, 9999),
                'event': 'authentication_success',
                'user': user['username'],
                'source_ip': user['ip'],
                'source_port': self.fake.random_int(49152, 65535),
                'method': 'publickey',
                'message': f"Accepted publickey for {user['username']} from {user['ip']} port {self.fake.random_int(49152, 65535)} ssh2: RSA SHA256:{self.fake.sha256()[:43]}",
                'severity': 'info',
                'department': user['department']
            })
            current_time += timedelta(seconds=self.fake.random_int(30, 300))
        
        # Phase 2: Brute force attack (15 minutes of intensive attempts)
        attack_start = current_time
        common_usernames = [
            'root', 'admin', 'administrator', 'user', 'test', 
            'oracle', 'postgres', 'mysql', 'tomcat', 'jenkins',
            'ubuntu', 'centos', 'guest', 'backup', 'monitor'
        ]
        
        for i in range(250):
            target_user = self.fake.random_element(common_usernames)
            logs.append({
                'timestamp': current_time.isoformat(),
                'log_type': 'ssh',
                'host': TARGET_SERVER,
                'service': 'sshd',
                'pid': self.fake.random_int(1000, 9999),
                'event': 'authentication_failure',
                'user': target_user,
                'source_ip': ATTACKER_IP,
                'source_port': self.fake.random_int(49152, 65535),
                'method': 'password',
                'message': f"Failed password for {target_user} from {ATTACKER_IP} port {self.fake.random_int(49152, 65535)} ssh2",
                'severity': 'warning',
                'tags': ['brute_force_attempt', 'authentication_failure'],
                'country': ATTACKER_COUNTRY
            })
            current_time += timedelta(seconds=self.fake.random_int(2, 10))
        
        # Phase 3: Successful breach after brute force
        breach_time = current_time
        logs.append({
            'timestamp': breach_time.isoformat(),
            'log_type': 'ssh',
            'host': TARGET_SERVER,
            'service': 'sshd',
            'pid': self.fake.random_int(1000, 9999),
            'event': 'authentication_success',
            'user': 'admin',
            'source_ip': ATTACKER_IP,
            'source_port': self.fake.random_int(49152, 65535),
            'method': 'password',
            'message': f"Accepted password for admin from {ATTACKER_IP} port {self.fake.random_int(49152, 65535)} ssh2",
            'severity': 'critical',
            'tags': ['successful_breach', 'suspicious_login', 'post_bruteforce'],
            'country': ATTACKER_COUNTRY,
            'alert': 'SUCCESSFUL LOGIN AFTER BRUTE FORCE ATTACK'
        })
        current_time += timedelta(seconds=5)
        
        # Add session established
        logs.append({
            'timestamp': current_time.isoformat(),
            'log_type': 'ssh',
            'host': TARGET_SERVER,
            'service': 'sshd',
            'pid': logs[-1]['pid'],
            'event': 'session_opened',
            'user': 'admin',
            'source_ip': ATTACKER_IP,
            'message': f"pam_unix(sshd:session): session opened for user admin by (uid=0)",
            'severity': 'high',
            'tags': ['session_start', 'suspicious_session']
        })
        
        # Phase 4: Continue normal activity after breach
        current_time += timedelta(minutes=2)
        while current_time < end_time:
            user = self.fake.random_element(self.normal_users)
            logs.append({
                'timestamp': current_time.isoformat(),
                'log_type': 'ssh',
                'host': TARGET_SERVER,
                'service': 'sshd',
                'pid': self.fake.random_int(1000, 9999),
                'event': 'authentication_success',
                'user': user['username'],
                'source_ip': user['ip'],
                'source_port': self.fake.random_int(49152, 65535),
                'method': 'publickey',
                'message': f"Accepted publickey for {user['username']} from {user['ip']}",
                'severity': 'info',
                'department': user['department']
            })
            current_time += timedelta(seconds=self.fake.random_int(60, 400))
        
        return logs, breach_time, attack_start
    
    def generate_system_logs(self, breach_time: datetime):
        """Generate system/command execution logs showing post-exploitation"""
        logs = []
        current_time = breach_time + timedelta(minutes=2)
        
        # Privilege escalation
        logs.append({
            'timestamp': current_time.isoformat(),
            'log_type': 'system',
            'host': TARGET_SERVER,
            'service': 'sudo',
            'event': 'privilege_escalation',
            'user': 'admin',
            'effective_user': 'root',
            'command': 'sudo su -',
            'working_directory': '/home/admin',
            'message': 'USER=admin ; PWD=/home/admin ; COMMAND=/bin/su -',
            'severity': 'critical',
            'tags': ['privilege_escalation', 'sudo_usage']
        })
        current_time += timedelta(seconds=3)
        
        # Post-exploitation reconnaissance commands
        recon_commands = [
            {
                'cmd': 'whoami',
                'desc': 'Identity verification',
                'output': 'root',
                'severity': 'high'
            },
            {
                'cmd': 'id',
                'desc': 'Permission enumeration',
                'output': 'uid=0(root) gid=0(root) groups=0(root)',
                'severity': 'high'
            },
            {
                'cmd': 'uname -a',
                'desc': 'System information gathering',
                'output': f'Linux {TARGET_SERVER} 5.15.0-91-generic',
                'severity': 'medium'
            },
            {
                'cmd': 'cat /etc/passwd',
                'desc': 'User enumeration',
                'output': f'{len(self.normal_users)} users found',
                'severity': 'high'
            },
            {
                'cmd': 'cat /etc/shadow',
                'desc': 'Password hash theft attempt',
                'output': 'Access to password hashes',
                'severity': 'critical'
            },
            {
                'cmd': 'find / -name "*.db" 2>/dev/null',
                'desc': 'Database file discovery',
                'output': '3 database files found',
                'severity': 'high'
            },
            {
                'cmd': 'find / -name "*.conf" 2>/dev/null | grep -i database',
                'desc': 'Configuration file search',
                'output': 'Database configs discovered',
                'severity': 'high'
            },
            {
                'cmd': 'netstat -tlnp',
                'desc': 'Network service enumeration',
                'output': '12 listening ports',
                'severity': 'medium'
            },
            {
                'cmd': 'ps aux | grep -i sql',
                'desc': 'Database process identification',
                'output': 'PostgreSQL running on port 5432',
                'severity': 'medium'
            },
            {
                'cmd': 'ls -la /var/www/',
                'desc': 'Web application file listing',
                'output': 'Application source code accessed',
                'severity': 'high'
            },
            {
                'cmd': 'cat /var/www/app/config/database.yml',
                'desc': 'Database credential theft',
                'output': 'DB credentials extracted',
                'severity': 'critical'
            },
            {
                'cmd': 'history',
                'desc': 'Command history review',
                'output': 'Previous admin commands reviewed',
                'severity': 'medium'
            }
        ]
        
        for cmd_info in recon_commands:
            current_time += timedelta(seconds=self.fake.random_int(15, 45))
            logs.append({
                'timestamp': current_time.isoformat(),
                'log_type': 'system',
                'host': TARGET_SERVER,
                'service': 'bash',
                'event': 'command_executed',
                'user': 'root',
                'command': cmd_info['cmd'],
                'description': cmd_info['desc'],
                'working_directory': '/root',
                'message': f"Command executed: {cmd_info['cmd']} - {cmd_info['output']}",
                'severity': cmd_info['severity'],
                'tags': ['post_exploitation', 'reconnaissance', 'suspicious_command']
            })
        
        recon_end_time = current_time
        return logs, recon_end_time
    
    def generate_database_logs(self, start_time: datetime, breach_time: datetime, duration_hours: int = 2):
        """Generate database access logs with data exfiltration"""
        logs = []
        current_time = start_time
        end_time = start_time + timedelta(hours=duration_hours)
        
        tables = ['orders', 'products', 'inventory', 'shipping', 'customers', 'suppliers']
        
        # Normal database activity throughout the period
        while current_time < end_time:
            user = self.fake.random_element(self.normal_users)
            table = self.fake.random_element(tables)
            rows = self.fake.random_int(10, 500)
            
            logs.append({
                'timestamp': current_time.isoformat(),
                'log_type': 'database',
                'host': DB_SERVER,
                'service': 'postgresql',
                'event': 'query_executed',
                'user': 'app_user',
                'database': 'production',
                'table': table,
                'query_type': 'SELECT',
                'query': f"SELECT * FROM {table} WHERE updated_at > NOW() - INTERVAL '1 day' LIMIT 100",
                'rows_returned': rows,
                'rows_affected': 0,
                'duration_ms': self.fake.random_int(50, 500),
                'client_ip': user['ip'],
                'severity': 'info'
            })
            current_time += timedelta(seconds=self.fake.random_int(20, 120))
        
        # Attack: Mass data extraction (10 minutes after breach)
        exfil_time = breach_time + timedelta(minutes=10)
        
        # Customer data theft
        logs.append({
            'timestamp': exfil_time.isoformat(),
            'log_type': 'database',
            'host': DB_SERVER,
            'service': 'postgresql',
            'event': 'query_executed',
            'user': 'admin',
            'database': 'production',
            'table': 'customers',
            'query_type': 'SELECT',
            'query': 'SELECT customer_id, name, email, phone, address, ssn, date_of_birth FROM customers',
            'rows_returned': 487653,
            'rows_affected': 0,
            'duration_ms': 45230,
            'client_ip': '127.0.0.1',  # Local connection from compromised server
            'severity': 'critical',
            'tags': ['mass_data_access', 'pii_access', 'data_exfiltration'],
            'alert': 'MASSIVE CUSTOMER DATA EXTRACTION - ALL RECORDS'
        })
        
        exfil_time += timedelta(seconds=50)
        
        # Payment methods theft
        logs.append({
            'timestamp': exfil_time.isoformat(),
            'log_type': 'database',
            'host': DB_SERVER,
            'service': 'postgresql',
            'event': 'query_executed',
            'user': 'admin',
            'database': 'production',
            'table': 'payment_methods',
            'query_type': 'SELECT',
            'query': 'SELECT * FROM payment_methods WHERE card_number IS NOT NULL',
            'rows_returned': 412890,
            'rows_affected': 0,
            'duration_ms': 38420,
            'client_ip': '127.0.0.1',
            'severity': 'critical',
            'tags': ['mass_data_access', 'pci_data', 'card_data_theft', 'data_exfiltration'],
            'alert': 'PAYMENT CARD DATA ACCESS - PCI VIOLATION'
        })
        
        exfil_time += timedelta(seconds=45)
        
        # Order history theft
        logs.append({
            'timestamp': exfil_time.isoformat(),
            'log_type': 'database',
            'host': DB_SERVER,
            'service': 'postgresql',
            'event': 'query_executed',
            'user': 'admin',
            'database': 'production',
            'table': 'orders',
            'query_type': 'SELECT',
            'query': 'SELECT * FROM orders JOIN order_items ON orders.id = order_items.order_id',
            'rows_returned': 1247892,
            'rows_affected': 0,
            'duration_ms': 67840,
            'client_ip': '127.0.0.1',
            'severity': 'critical',
            'tags': ['mass_data_access', 'business_data', 'data_exfiltration'],
            'alert': 'COMPLETE ORDER HISTORY EXTRACTED'
        })
        
        return logs, exfil_time
    
    def generate_network_logs(self, start_time: datetime, exfil_time: datetime, duration_hours: int = 2):
        """Generate network/firewall logs with data exfiltration traffic"""
        logs = []
        current_time = start_time
        end_time = start_time + timedelta(hours=duration_hours)
        
        # Normal outbound traffic
        normal_destinations = [self.fake.ipv4() for _ in range(20)]
        
        while current_time < end_time:
            dest_ip = self.fake.random_element(normal_destinations)
            logs.append({
                'timestamp': current_time.isoformat(),
                'log_type': 'network',
                'host': TARGET_SERVER,
                'service': 'firewall',
                'event': 'connection_allowed',
                'source_ip': '10.0.0.5',
                'source_port': self.fake.random_int(49152, 65535),
                'dest_ip': dest_ip,
                'dest_port': self.fake.random_element([443, 80, 8080]),
                'protocol': 'tcp',
                'bytes_sent': self.fake.random_int(1024, 1048576),
                'bytes_received': self.fake.random_int(2048, 2097152),
                'packets_sent': self.fake.random_int(10, 500),
                'packets_received': self.fake.random_int(20, 1000),
                'duration_seconds': self.fake.random_int(1, 30),
                'action': 'ALLOW',
                'severity': 'info'
            })
            current_time += timedelta(seconds=self.fake.random_int(5, 60))
        
        # Attack: Large data exfiltration (5 minutes after DB queries)
        data_exfil_time = exfil_time + timedelta(minutes=5)
        
        logs.append({
            'timestamp': data_exfil_time.isoformat(),
            'log_type': 'network',
            'host': TARGET_SERVER,
            'service': 'firewall',
            'event': 'connection_allowed',
            'source_ip': '10.0.0.5',
            'source_port': self.fake.random_int(49152, 65535),
            'dest_ip': ATTACKER_IP,
            'dest_port': 443,
            'protocol': 'tcp',
            'bytes_sent': 734003200,  # 700 MB
            'bytes_received': 8192,
            'packets_sent': 512800,
            'packets_received': 256,
            'duration_seconds': 247,
            'action': 'ALLOW',
            'connection_type': 'TLS 1.3',
            'severity': 'critical',
            'tags': ['large_upload', 'data_exfiltration', 'suspicious_destination', 'anomalous_traffic'],
            'alert': 'MASSIVE OUTBOUND DATA TRANSFER TO UNKNOWN IP'
        })
        
        return logs

# Initialize generator
generator = SecurityLogGenerator()

def generate_all_logs():
    """Generate complete log dataset and cache it"""
    global _cached_logs, _attack_timeline
    
    if _cached_logs:
        return _cached_logs
    
    start_time = datetime.now() - timedelta(hours=2)
    
    # Generate all log types
    ssh_logs, breach_time, attack_start = generator.generate_ssh_logs(start_time)
    system_logs, recon_end = generator.generate_system_logs(breach_time)
    db_logs, exfil_time = generator.generate_database_logs(start_time, breach_time)
    network_logs = generator.generate_network_logs(start_time, exfil_time)
    
    # Combine and sort
    all_logs = sorted(
        ssh_logs + system_logs + db_logs + network_logs,
        key=lambda x: x['timestamp']
    )
    
    # Build attack timeline
    _attack_timeline = {
        'incident_id': fake.uuid4(),
        'detection_time': datetime.now().isoformat(),
        'attack_start': attack_start.isoformat(),
        'breach_time': breach_time.isoformat(),
        'reconnaissance_complete': recon_end.isoformat(),
        'data_access_time': exfil_time.isoformat(),
        'exfiltration_time': (exfil_time + timedelta(minutes=5)).isoformat(),
        'attacker_ip': ATTACKER_IP,
        'attacker_country': ATTACKER_COUNTRY,
        'compromised_user': 'admin',
        'compromised_host': TARGET_SERVER,
        'target_database': DB_SERVER,
        'attack_duration_minutes': int((exfil_time + timedelta(minutes=5) - attack_start).total_seconds() / 60),
        'attack_vector': 'SSH Brute Force',
        'data_stolen': {
            'customer_records': 487653,
            'payment_cards': 412890,
            'order_records': 1247892,
            'estimated_size_mb': 700
        },
        'mitre_attack_techniques': [
            'T1110.001 - Brute Force: Password Guessing',
            'T1078 - Valid Accounts',
            'T1548.003 - Abuse Elevation Control Mechanism: Sudo',
            'T1087 - Account Discovery',
            'T1082 - System Information Discovery',
            'T1083 - File and Directory Discovery',
            'T1005 - Data from Local System',
            'T1071.001 - Application Layer Protocol: Web Protocols',
            'T1041 - Exfiltration Over C2 Channel'
        ]
    }
    
    # Calculate statistics
    stats = {
        'total_events': len(all_logs),
        'log_type_breakdown': {
            'ssh': len([l for l in all_logs if l['log_type'] == 'ssh']),
            'system': len([l for l in all_logs if l['log_type'] == 'system']),
            'database': len([l for l in all_logs if l['log_type'] == 'database']),
            'network': len([l for l in all_logs if l['log_type'] == 'network'])
        },
        'severity_breakdown': {
            'info': len([l for l in all_logs if l.get('severity') == 'info']),
            'warning': len([l for l in all_logs if l.get('severity') == 'warning']),
            'medium': len([l for l in all_logs if l.get('severity') == 'medium']),
            'high': len([l for l in all_logs if l.get('severity') == 'high']),
            'critical': len([l for l in all_logs if l.get('severity') == 'critical'])
        },
        'alerts': len([l for l in all_logs if 'alert' in l]),
        'unique_users': len(set(l['user'] for l in all_logs if 'user' in l)),
        'unique_source_ips': len(set(l['source_ip'] for l in all_logs if 'source_ip' in l)),
        'time_range': {
            'start': all_logs[0]['timestamp'],
            'end': all_logs[-1]['timestamp']
        }
    }
    
    _cached_logs = {
        'all_logs': all_logs,
        'ssh_logs': ssh_logs,
        'system_logs': system_logs,
        'database_logs': db_logs,
        'network_logs': network_logs,
        'attack_timeline': _attack_timeline,
        'statistics': stats
    }
    
    return _cached_logs

# Create MCP server
app = Server("security-log-server")

@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available security analysis tools"""
    return [
        Tool(
            name="get_all_logs",
            description="Get all security logs (SSH, system, database, network) from the past 2 hours. Returns complete timeline including attack events.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="get_logs_by_type",
            description="Get logs filtered by type: ssh, system, database, or network. Useful for focused analysis of specific log sources.",
            inputSchema={
                "type": "object",
                "properties": {
                    "log_type": {
                        "type": "string",
                        "enum": ["ssh", "system", "database", "network"],
                        "description": "Type of logs to retrieve"
                    }
                },
                "required": ["log_type"]
            },
        ),
        Tool(
            name="get_attack_timeline",
            description="Get detailed attack timeline with key timestamps, MITRE ATT&CK techniques, and indicators of compromise (IOCs).",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="search_logs",
            description="Search and filter logs by IP address, username, severity level, or tags. Supports multiple filter criteria.",
            inputSchema={
                "type": "object",
                "properties": {
                    "ip": {
                        "type": "string",
                        "description": "Filter by source or destination IP address"
                    },
                    "user": {
                        "type": "string",
                        "description": "Filter by username"
                    },
                    "severity": {
                        "type": "string",
                        "enum": ["info", "warning", "medium", "high", "critical"],
                        "description": "Filter by severity level"
                    },
                    "tag": {
                        "type": "string",
                        "description": "Filter by tag (e.g., 'brute_force_attempt', 'data_exfiltration', 'privilege_escalation')"
                    },
                    "has_alert": {
                        "type": "boolean",
                        "description": "Filter for logs that have alert messages"
                    }
                }
            },
        ),
        Tool(
            name="get_statistics",
            description="Get comprehensive statistical summary including event counts, severity breakdown, and unique entities.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="regenerate_logs",
            description="Generate a new set of synthetic logs with different random data but same attack pattern. Useful for repeated demos.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
    ]

@app.call_tool()
async def call_tool(name: str, arguments: Any) -> Sequence[TextContent]:
    """Handle tool execution"""
    global _cached_logs, _attack_timeline
    
    try:
        logs = generate_all_logs()
        
        if name == "get_all_logs":
            return [TextContent(
                type="text",
                text=json.dumps(logs['all_logs'], indent=2)
            )]
        
        elif name == "get_logs_by_type":
            log_type = arguments.get('log_type')
            filtered = logs[f'{log_type}_logs']
            return [TextContent(
                type="text",
                text=json.dumps(filtered, indent=2)
            )]
        
        elif name == "get_attack_timeline":
            return [TextContent(
                type="text",
                text=json.dumps(logs['attack_timeline'], indent=2)
            )]
        
        elif name == "search_logs":
            results = logs['all_logs']
            
            if 'ip' in arguments:
                ip = arguments['ip']
                results = [l for l in results if 
                          l.get('source_ip') == ip or l.get('dest_ip') == ip]
            
            if 'user' in arguments:
                user = arguments['user']
                results = [l for l in results if l.get('user') == user]
            
            if 'severity' in arguments:
                severity = arguments['severity']
                results = [l for l in results if l.get('severity') == severity]
            
            if 'tag' in arguments:
                tag = arguments['tag']
                results = [l for l in results if 
                          'tags' in l and tag in l['tags']]
            
            if arguments.get('has_alert'):
                results = [l for l in results if 'alert' in l]
            
            return [TextContent(
                type="text",
                text=json.dumps({
                    'matching_logs': results,
                    'count': len(results),
                    'filters_applied': arguments
                }, indent=2)
            )]
        
        elif name == "get_statistics":
            return [TextContent(
                type="text",
                text=json.dumps(logs['statistics'], indent=2)
            )]
        
        elif name == "regenerate_logs":
            _cached_logs = None
            _attack_timeline = None
            Faker.seed()  # Use random seed
            new_logs = generate_all_logs()
            return [TextContent(
                type="text",
                text=json.dumps({
                    'message': 'New logs generated successfully',
                    'statistics': new_logs['statistics'],
                    'new_incident_id': new_logs['attack_timeline']['incident_id']
                }, indent=2)
            )]
        
        else:
            return [TextContent(
                type="text",
                text=json.dumps({'error': f'Unknown tool: {name}'})
            )]
    
    except Exception as e:
        return [TextContent(
            type="text",
            text=json.dumps({'error': str(e)})
        )]

async def main():
    """Run the MCP server"""
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )

if __name__ == "__main__":
    asyncio.run(main())