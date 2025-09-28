#!/usr/bin/env python3
"""
FRANK 008 AWS Spike - Setup Script

Sets up the Python environment and validates prerequisites for deployment.
"""

import sys
import subprocess
import json
from pathlib import Path

def check_python_version():
    """Check Python version"""
    if sys.version_info < (3, 8):
        print("❌ Python 3.8+ required")
        sys.exit(1)
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor}")

def install_requirements():
    """Install Python requirements"""
    print("📦 Installing Python requirements...")
    
    requirements = [
        "boto3>=1.26.0",
        "pyyaml>=6.0",
        "requests>=2.28.0",
        "click>=8.0.0",
        "fastapi==0.104.1",
        "uvicorn[standard]==0.24.0"
    ]
    
    for req in requirements:
        subprocess.run([sys.executable, "-m", "pip", "install", req], check=True)
    
    print("✅ Requirements installed")

def check_aws_cli():
    """Check AWS CLI installation and configuration"""
    try:
        result = subprocess.run(["aws", "--version"], capture_output=True, text=True)
        print(f"✅ AWS CLI: {result.stdout.strip()}")
        
        # Check AWS credentials
        result = subprocess.run(["aws", "sts", "get-caller-identity"], capture_output=True, text=True)
        if result.returncode == 0:
            identity = json.loads(result.stdout)
            print(f"✅ AWS Identity: {identity['Arn']}")
        else:
            print("⚠️  AWS credentials not configured")
            print("   Run: aws configure")
            
    except FileNotFoundError:
        print("❌ AWS CLI not found")
        print("   Install: pip install awscli")
        sys.exit(1)

def check_docker():
    """Check Docker installation"""
    try:
        result = subprocess.run(["docker", "--version"], capture_output=True, text=True)
        print(f"✅ Docker: {result.stdout.strip()}")
        
        # Check if Docker daemon is running
        result = subprocess.run(["docker", "info"], capture_output=True, text=True)
        if result.returncode != 0:
            print("⚠️  Docker daemon not running")
            print("   Start Docker Desktop or dockerd")
            
    except FileNotFoundError:
        print("❌ Docker not found")
        print("   Install Docker Desktop or Docker Engine")

def create_directories():
    """Create required directories"""
    directories = [
        "config",
        "templates", 
        "utils",
        "logs"
    ]
    
    for directory in directories:
        Path(directory).mkdir(exist_ok=True)
    
    print("✅ Directories created")

def create_init_files():
    """Create __init__.py files for Python packages"""
    init_files = [
        "utils/__init__.py"
    ]
    
    for init_file in init_files:
        Path(init_file).touch()
    
    print("✅ Package files created")

def validate_config_files():
    """Validate configuration files exist"""
    required_configs = [
        "config/accounts.yaml",
        "config/spike-params.yaml"
    ]
    
    missing_configs = []
    for config in required_configs:
        if not Path(config).exists():
            missing_configs.append(config)
    
    if missing_configs:
        print("⚠️  Missing configuration files:")
        for config in missing_configs:
            print(f"   - {config}")
        print("   Please create these files before deployment")
    else:
        print("✅ Configuration files present")

def main():
    """Main setup function"""
    print("🚀 FRANK 008 AWS Spike Setup")
    print("=" * 40)
    
    check_python_version()
    install_requirements()
    check_aws_cli()
    check_docker()
    create_directories()
    create_init_files()
    validate_config_files()
    
    print("\n" + "=" * 40)
    print("✅ Setup complete!")
    print("\n📋 Next steps:")
    print("1. Update config/accounts.yaml with your account IDs")
    print("2. Update config/spike-params.yaml with your domain")
    print("3. Create cross-account IAM role in main account")
    print("4. Run: python deploy.py setup-accounts")
    print("5. Run: python deploy.py deploy")

if __name__ == "__main__":
    main()