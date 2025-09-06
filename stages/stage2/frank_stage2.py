#!/usr/bin/env python3
"""
FRANK Platform - Stage 2 Implementation
Based on spikes/004_sqlite.py but using RDS/MariaDB via LocalStack

This implementation provides:
1. FastAPI server adapted from your existing SQLite implementation
2. RDS/MariaDB integration via LocalStack 
3. Repository pattern for database abstraction
4. Minimal submission model from your existing spikes
5. Direct migration path from SQLite to RDS
"""

import os
import json
import uuid
import hashlib
import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Union
from pathlib import Path

import pymysql
from pydantic import BaseModel, Field, validator
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from frank import __version__

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ================================
# PYDANTIC MODELS (Based on your existing SQLite models)
# ================================

class SimpleObservable(BaseModel):
    """Observable model based on spikes/004_sqlite.py"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: str = Field(..., description="Observable type")
    value: str = Field(..., description="Observable value")
    confidence: Optional[int] = Field(None, ge=0, le=100, description="Confidence level 0-100")
    role: Optional[str] = Field(None, description="Role in attack")
    port: Optional[int] = Field(None, description="Network port")
    protocol: Optional[str] = Field(None, description="Network protocol")
    
    @validator('type')
    def validate_type(cls, v):
        allowed_types = ['ipv4', 'ipv6', 'domain', 'url', 'file_hash', 'email', 'registry_key']
        if v not in allowed_types:
            raise ValueError(f'Observable type must be one of: {allowed_types}')
        return v

class MinimalSubmission(BaseModel):
    """Minimal submission model based on your existing implementation"""
    submission_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    submitter_org_id: str = Field(..., description="Organization ID of submitter")
    hit_target_org_id: Optional[str] = Field(None, description="Target organization ID")
    observables: List[SimpleObservable] = Field(..., description="List of threat observables")
    confidence: Optional[int] = Field(None, ge=0, le=100, description="Overall confidence level")
    severity: Optional[str] = Field(None, description="Threat severity")
    submission_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    format_version: str = Field(default="1.0", description="Submission format version")
    tlp_level: Optional[str] = Field('GREEN', description="TLP classification")
    
    @validator('severity')
    def validate_severity(cls, v):
        if v is not None:
            allowed = ['low', 'medium', 'high', 'critical']
            if v not in allowed:
                raise ValueError(f'Severity must be one of: {allowed}')
        return v
    
    @validator('tlp_level')
    def validate_tlp(cls, v):
        if v is not None:
            allowed = ['RED', 'AMBER+', 'AMBER', 'GREEN', 'CLEAR']
            if v not in allowed:
                raise ValueError(f'TLP level must be one of: {allowed}')
        return v

class SubmissionResponse(BaseModel):
    """API response model"""
    status: str
    submission_id: str
    message: str
    database_used: str = "rds"
    performance_ms: Optional[float] = None

# ================================
# CONFIGURATION MANAGEMENT
# ================================

class FrankConfig:
    """Environment-based configuration management"""
    
    def __init__(self, environment: str = None):
        self.environment = environment or os.getenv('FRANK_ENVIRONMENT', 'localstack')
        self.setup_config()
    
    def setup_config(self):
        """Setup configuration based on environment"""
        if self.environment == 'local':
            self.setup_local_config()
        elif self.environment in ['mysql']:
            # Direct MySQL connection
            self.database_type = 'mysql'
            self.mysql_host = os.getenv('RDS_HOST', 'localhost')
            self.mysql_port = int(os.getenv('RDS_PORT', '3306'))
            self.mysql_database = os.getenv('RDS_DATABASE', 'frank')
            self.mysql_username = os.getenv('RDS_USERNAME', 'frank_user')
            self.mysql_password = os.getenv('RDS_PASSWORD', 'frank_pass')
        elif self.environment == 'hybrid':
            self.setup_localstack_hybrid_config()
        elif self.environment == 'localstack':
            self.setup_localstack_config()
        elif self.environment == 'aws':
            self.setup_aws_config()
        else:
            raise ValueError(f"Unknown environment: {self.environment}")
    
    def setup_local_config(self):
        """Local SQLite configuration (fallback)"""
        self.database_type = 'sqlite'
        self.sqlite_path = os.getenv('SQLITE_PATH', '/tmp/frank_local.db')

    def setup_localstack_hybrid_config(self):
        """Hybrid LocalStack with external MySQL configuration"""
        self.database_type = 'rds'
        self.localstack_endpoint = os.getenv('LOCALSTACK_ENDPOINT', 'http://localhost:4566')
        
        # MySQL Configuration (external)
        self.rds_host = os.getenv('RDS_HOST', 'mysql')
        self.rds_port = int(os.getenv('RDS_PORT', '3306'))
        self.rds_database = os.getenv('RDS_DATABASE', 'frank')
        self.rds_username = os.getenv('RDS_USERNAME', 'frank_user')
        self.rds_password = os.getenv('RDS_PASSWORD', 'frank_pass')
        
        # AWS Credentials (for LocalStack)
        self.aws_access_key = os.getenv('AWS_ACCESS_KEY_ID', 'test')
        self.aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY', 'test')
        self.aws_region = os.getenv('AWS_DEFAULT_REGION', 'eu-west-1')

    def setup_localstack_config(self):
        """LocalStack RDS configuration"""
        self.database_type = 'rds'
        self.localstack_endpoint = os.getenv('LOCALSTACK_ENDPOINT', 'http://localhost:4566')
        
        # RDS Configuration (via LocalStack)
        self.rds_host = os.getenv('RDS_HOST', 'localhost')
        self.rds_port = int(os.getenv('RDS_PORT', '4566'))
        self.rds_database = os.getenv('RDS_DATABASE', 'frank')
        self.rds_username = os.getenv('RDS_USERNAME', 'frank_user')
        self.rds_password = os.getenv('RDS_PASSWORD', 'frank_pass')
        
        # AWS Credentials (for LocalStack)
        self.aws_access_key = os.getenv('AWS_ACCESS_KEY_ID', 'test')
        self.aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY', 'test')
        self.aws_region = os.getenv('AWS_DEFAULT_REGION', 'eu-west-1')
    
    def setup_aws_config(self):
        """Real AWS RDS configuration"""
        self.database_type = 'rds'
        self.rds_host = os.getenv('RDS_HOST')
        self.rds_port = int(os.getenv('RDS_PORT', '3306'))
        self.rds_database = os.getenv('RDS_DATABASE', 'frank')
        self.rds_username = os.getenv('RDS_USERNAME')
        self.rds_password = os.getenv('RDS_PASSWORD')
        self.aws_region = os.getenv('AWS_DEFAULT_REGION', 'eu-west-1')

# ================================
# DATABASE LAYER (Based on spikes/004_sqlite.py schema)
# ================================

class FRANKDatabase:
    """
    RDS/MariaDB database handler adapted from your SQLite implementation
    Schema based on spikes/004_sqlite.py
    """
    
    def __init__(self, config: FrankConfig):
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)
        logger.info(f"Initializing FRANK Database - {config.database_type}")
        
    def get_connection(self):
        """Get database connection"""
        if self.config.database_type == 'sqlite':
            # Fallback for local development
            import sqlite3
            return sqlite3.connect(self.config.sqlite_path)
        else:
            # RDS/MariaDB connection
            return pymysql.connect(
                host=self.config.rds_host,
                port=self.config.rds_port,
                user=self.config.rds_username,
                password=self.config.rds_password,
                database=self.config.rds_database,
                charset='utf8mb4',
                autocommit=False
            )
    
    async def initialize_schema(self):
        """Initialize database schema - adapted from spikes/004_sqlite.py"""
        try:
            conn = self.get_connection()
            
            if self.config.database_type == 'sqlite':
                cursor = conn.cursor()
                execute_func = cursor.execute
            else:
                cursor = conn.cursor()
                execute_func = cursor.execute
            
            # Organizations table (cyber partners and customers)
            execute_func("""
                CREATE TABLE IF NOT EXISTS organizations (
                    organization_id VARCHAR(255) PRIMARY KEY,
                    organization_type VARCHAR(50) NOT NULL,
                    tier VARCHAR(50),
                    sector VARCHAR(100),
                    region VARCHAR(100),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_active TIMESTAMP,
                    contribution_score INTEGER DEFAULT 0,
                    client_count INTEGER DEFAULT 0
                )
            """)
            
            # Submissions table (main submission data)
            execute_func("""
                CREATE TABLE IF NOT EXISTS submissions (
                    submission_id VARCHAR(255) PRIMARY KEY,
                    submitter_org_id VARCHAR(255) NOT NULL,
                    hit_target_org_id VARCHAR(255),
                    format_version VARCHAR(10) DEFAULT '1.0',
                    submission_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    confidence INTEGER,
                    severity VARCHAR(20),
                    tlp_level VARCHAR(10),
                    full_submission_json TEXT NOT NULL,
                    INDEX idx_submitter_org (submitter_org_id),
                    INDEX idx_timestamp (submission_timestamp),
                    INDEX idx_severity (severity)
                )
            """)
            
            # Sightings table (individual threat sightings)
            execute_func("""
                CREATE TABLE IF NOT EXISTS sightings (
                    sighting_id VARCHAR(255) PRIMARY KEY,
                    submission_id VARCHAR(255) NOT NULL,
                    first_observed TIMESTAMP,
                    last_observed TIMESTAMP,
                    observation_count INTEGER DEFAULT 1,
                    confidence INTEGER,
                    severity VARCHAR(20),
                    INDEX idx_submission (submission_id),
                    FOREIGN KEY (submission_id) REFERENCES submissions(submission_id) ON DELETE CASCADE
                )
            """)
            
            # Observables table (IoCs and artifacts)
            execute_func("""
                CREATE TABLE IF NOT EXISTS observables (
                    observable_id VARCHAR(255) PRIMARY KEY,
                    sighting_id VARCHAR(255),
                    submission_id VARCHAR(255) NOT NULL,
                    observable_type VARCHAR(50) NOT NULL,
                    observable_value TEXT NOT NULL,
                    observable_hash VARCHAR(64),
                    confidence INTEGER,
                    role VARCHAR(100),
                    port INTEGER,
                    protocol VARCHAR(50),
                    first_seen TIMESTAMP,
                    INDEX idx_submission (submission_id),
                    INDEX idx_type (observable_type),
                    INDEX idx_hash (observable_hash),
                    INDEX idx_value (observable_value(255)),
                    FOREIGN KEY (submission_id) REFERENCES submissions(submission_id) ON DELETE CASCADE
                )
            """)
            
            # Statistics table (aggregated data)
            execute_func("""
                CREATE TABLE IF NOT EXISTS observable_statistics (
                    id INTEGER PRIMARY KEY AUTO_INCREMENT,
                    observable_hash VARCHAR(64) NOT NULL,
                    observable_type VARCHAR(50) NOT NULL,
                    observable_value TEXT NOT NULL,
                    total_sightings INTEGER DEFAULT 1,
                    unique_organizations INTEGER DEFAULT 1,
                    first_seen TIMESTAMP,
                    last_seen TIMESTAMP,
                    avg_confidence DECIMAL(5,2),
                    sectors_json TEXT,
                    regions_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_hash (observable_hash),
                    INDEX idx_type (observable_type)
                )
            """)
            
            # Access logs for auditing
            execute_func("""
                CREATE TABLE IF NOT EXISTS access_logs (
                    id INTEGER PRIMARY KEY AUTO_INCREMENT,
                    organization_id VARCHAR(255) NOT NULL,
                    action VARCHAR(100) NOT NULL,
                    resource_type VARCHAR(50),
                    resource_id VARCHAR(255),
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    access_level VARCHAR(50),
                    success BOOLEAN DEFAULT TRUE,
                    INDEX idx_org (organization_id),
                    INDEX idx_timestamp (timestamp)
                )
            """)
            
            conn.commit()
            if cursor:
                cursor.close()
            conn.close()
            
            self.logger.info("Database schema initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Database initialization error: {e}")
            raise
    
    def hash_observable(self, observable_type: str, observable_value: str) -> str:
        """Create a hash for observable deduplication - from spikes/004_sqlite.py"""
        combined = f"{observable_type}:{observable_value}".lower()
        return hashlib.sha256(combined.encode()).hexdigest()
    
    async def store_submission(self, submission: MinimalSubmission) -> bool:
        """Store a complete submission - adapted from spikes/004_sqlite.py"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Create default sighting ID for this submission
            sighting_id = str(uuid.uuid4())
            
            # Insert submission record
            cursor.execute("""
                INSERT INTO submissions 
                (submission_id, submitter_org_id, hit_target_org_id, format_version, 
                 submission_timestamp, confidence, severity, tlp_level, full_submission_json)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                submission.submission_id,
                submission.submitter_org_id,
                submission.hit_target_org_id,
                submission.format_version,
                submission.submission_timestamp,
                submission.confidence,
                submission.severity,
                submission.tlp_level,
                submission.json()
            ))
            
            # Insert sighting record
            cursor.execute("""
                INSERT INTO sightings 
                (sighting_id, submission_id, first_observed, last_observed, 
                 observation_count, confidence, severity)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                sighting_id,
                submission.submission_id,
                submission.submission_timestamp,
                submission.submission_timestamp,
                1,
                submission.confidence,
                submission.severity
            ))
            
            # Insert observable records
            for observable in submission.observables:
                observable_hash = self.hash_observable(observable.type, observable.value)
                
                cursor.execute("""
                    INSERT INTO observables 
                    (observable_id, sighting_id, submission_id, observable_type, observable_value,
                     observable_hash, confidence, role, port, protocol, first_seen)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    observable.id,
                    sighting_id,
                    submission.submission_id,
                    observable.type,
                    observable.value,
                    observable_hash,
                    observable.confidence,
                    observable.role,
                    observable.port,
                    observable.protocol,
                    submission.submission_timestamp
                ))
                
                # Update or create statistics record
                await self._update_observable_statistics(
                    cursor, observable_hash, observable.type, observable.value,
                    submission.submitter_org_id, submission.confidence, submission.submission_timestamp
                )
            
            # Log access
            cursor.execute("""
                INSERT INTO access_logs 
                (organization_id, action, resource_type, resource_id, access_level, success)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                submission.submitter_org_id,
                'submit_threat_intelligence',
                'submission',
                submission.submission_id,
                'write',
                True
            ))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            self.logger.info(f"Stored submission {submission.submission_id} successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to store submission: {e}")
            if conn:
                conn.rollback()
                cursor.close()
                conn.close()
            return False
    
    async def _update_observable_statistics(self, cursor, observable_hash: str, observable_type: str, 
                                          observable_value: str, org_id: str, confidence: Optional[int], 
                                          timestamp: datetime):
        """Update aggregated statistics for an observable"""
        try:
            # Check if statistics record exists
            cursor.execute("""
                SELECT total_sightings, unique_organizations, avg_confidence, sectors_json 
                FROM observable_statistics 
                WHERE observable_hash = %s
            """, (observable_hash,))
            
            result = cursor.fetchone()
            
            if result:
                # Update existing record
                total_sightings, unique_orgs, avg_conf, sectors_json = result
                
                # Parse existing sectors
                sectors = json.loads(sectors_json) if sectors_json else []
                if org_id not in sectors:
                    sectors.append(org_id)
                    unique_orgs += 1
                
                # Update average confidence
                if confidence and avg_conf:
                    new_avg_conf = ((avg_conf * total_sightings) + confidence) / (total_sightings + 1)
                else:
                    new_avg_conf = confidence or avg_conf
                
                cursor.execute("""
                    UPDATE observable_statistics 
                    SET total_sightings = %s, unique_organizations = %s, avg_confidence = %s,
                        sectors_json = %s, last_seen = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE observable_hash = %s
                """, (
                    total_sightings + 1,
                    unique_orgs,
                    new_avg_conf,
                    json.dumps(sectors),
                    timestamp,
                    observable_hash
                ))
            else:
                # Create new statistics record
                cursor.execute("""
                    INSERT INTO observable_statistics 
                    (observable_hash, observable_type, observable_value, total_sightings,
                     unique_organizations, first_seen, last_seen, avg_confidence, sectors_json)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    observable_hash,
                    observable_type,
                    observable_value,
                    1,
                    1,
                    timestamp,
                    timestamp,
                    confidence,
                    json.dumps([org_id])
                ))
                
        except Exception as e:
            self.logger.error(f"Failed to update observable statistics: {e}")
    
    async def get_submission(self, submission_id: str) -> Optional[MinimalSubmission]:
        """Retrieve a submission by ID"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT full_submission_json FROM submissions WHERE submission_id = %s
            """, (submission_id,))
            
            result = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if result:
                return MinimalSubmission.parse_raw(result[0])
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to get submission: {e}")
            return None
    
    async def list_submissions(self, org_id: str, limit: int = 100) -> List[MinimalSubmission]:
        """List submissions for an organization"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT full_submission_json FROM submissions 
                WHERE submitter_org_id = %s 
                ORDER BY submission_timestamp DESC 
                LIMIT %s
            """, (org_id, limit))
            
            results = cursor.fetchall()
            cursor.close()
            conn.close()
            
            submissions = []
            for result in results:
                submissions.append(MinimalSubmission.parse_raw(result[0]))
            
            return submissions
            
        except Exception as e:
            self.logger.error(f"Failed to list submissions: {e}")
            return []
    
    async def get_platform_statistics(self, requesting_org_id: str) -> Dict[str, Any]:
        """Get platform statistics - adapted from spikes/004_sqlite.py"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Total submissions
            cursor.execute("SELECT COUNT(*) FROM submissions")
            total_submissions = cursor.fetchone()[0]
            
            # Active organizations
            cursor.execute("SELECT COUNT(DISTINCT submitter_org_id) FROM submissions")
            active_orgs = cursor.fetchone()[0]
            
            # Total observables
            cursor.execute("SELECT COUNT(*) FROM observables")
            total_observables = cursor.fetchone()[0]
            
            # Top observable types
            cursor.execute("""
                SELECT observable_type, COUNT(*) as count 
                FROM observables 
                GROUP BY observable_type 
                ORDER BY count DESC 
                LIMIT 5
            """)
            top_types = {row[0]: row[1] for row in cursor.fetchall()}
            
            # Recent activity (last 7 days)
            cursor.execute("""
                SELECT COUNT(*) FROM submissions 
                WHERE submission_timestamp >= DATE_SUB(NOW(), INTERVAL 7 DAY)
            """)
            recent_submissions = cursor.fetchone()[0]
            
            cursor.close()
            conn.close()
            
            return {
                'total_submissions': total_submissions,
                'active_organizations': active_orgs,
                'total_observables': total_observables,
                'top_observable_types': top_types,
                'recent_submissions_7_days': recent_submissions,
                'requesting_org': requesting_org_id
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get platform statistics: {e}")
            return {}
    
    async def health_check(self) -> bool:
        """Check database connectivity"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            conn.close()
            return True
        except Exception as e:
            self.logger.error(f"Database health check failed: {e}")
            return False

# ================================
# FASTAPI APPLICATION
# ================================

# Initialize configuration and database
config = FrankConfig()
frank_db = FRANKDatabase(config)

# Create FastAPI app
app = FastAPI(
    title="FRANK Platform - Stage 2",
    description="RDS/MariaDB Implementation with LocalStack",
    version="2.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    logger.info(f"Starting FRANK Platform Stage 2 - Environment: {config.environment}")
    await frank_db.initialize_schema()

# ================================
# API ENDPOINTS
# ================================

@app.get("/")
async def root():
    """Root endpoint with system information"""
    return {
        "service": "FRANK Platform",
        "stage": "Stage 2 - RDS/MariaDB Implementation",
        "environment": config.environment,
        "database_type": config.database_type,
        "version": __version__,
        "features": [
            "RDS/MariaDB integration",
            "LocalStack simulation",
            "SQLite schema compatibility",
            "Minimal submission model",
            "Performance monitoring"
        ]
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    db_healthy = await frank_db.health_check()
    
    return {
        "status": "healthy" if db_healthy else "unhealthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "database": {
            "type": config.database_type,
            "status": "healthy" if db_healthy else "unhealthy",
            "endpoint": f"{config.rds_host}:{config.rds_port}" if hasattr(config, 'rds_host') else "local"
        }
    }

@app.post("/v1/submissions", response_model=SubmissionResponse)
async def submit_threat_intelligence(submission: MinimalSubmission):
    """Submit threat intelligence data"""
    import time
    start_time = time.time()
    
    try:
        success = await frank_db.store_submission(submission)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to store submission")
        
        total_time = (time.time() - start_time) * 1000
        
        return SubmissionResponse(
            status="success",
            submission_id=submission.submission_id,
            message=f"Submission stored successfully in {config.database_type}",
            database_used=config.database_type,
            performance_ms=total_time
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to submit threat intelligence: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/v1/submissions/{submission_id}")
async def get_submission(submission_id: str):
    """Get a specific submission by ID"""
    try:
        submission = await frank_db.get_submission(submission_id)
        
        if not submission:
            raise HTTPException(status_code=404, detail="Submission not found")
        
        return {
            "submission": submission,
            "database_used": config.database_type
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get submission: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/v1/organizations/{org_id}/submissions")
async def list_organization_submissions(org_id: str, limit: int = 100):
    """List submissions for an organization"""
    try:
        submissions = await frank_db.list_submissions(org_id, limit)
        
        return {
            "organization_id": org_id,
            "submission_count": len(submissions),
            "submissions": submissions,
            "database_used": config.database_type
        }
        
    except Exception as e:
        logger.error(f"Failed to list submissions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/v1/statistics")
async def get_platform_statistics(org_id: str = "anonymous"):
    """Get platform statistics"""
    try:
        stats = await frank_db.get_platform_statistics(org_id)
        
        return {
            "statistics": stats,
            "database_used": config.database_type,
            "generated_at": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/test/generate-sample-data")
async def generate_sample_data(count: int = 10):
    """Generate sample threat intelligence data for testing"""
    try:
        generated_submissions = []
        
        sample_orgs = ["bank-alpha", "retail-beta", "tech-gamma", "gov-delta"]
        sample_observables = [
            {"type": "ipv4", "value": "192.168.1.100"},
            {"type": "domain", "value": "malicious-site.com"},
            {"type": "file_hash", "value": "a1b2c3d4e5f6"},
            {"type": "url", "value": "http://evil.example.com/payload"},
            {"type": "email", "value": "attacker@evil.com"}
        ]
        
        for i in range(count):
            # Create random submission
            submission = MinimalSubmission(
                submitter_org_id=sample_orgs[i % len(sample_orgs)],
                observables=[
                    SimpleObservable(
                        type=obs["type"],
                        value=f"{obs['value']}-{i}",
                        confidence=80 + (i % 20)
                    ) for obs in sample_observables[:((i % 3) + 1)]
                ],
                confidence=70 + (i % 30),
                severity=['low', 'medium', 'high'][i % 3]
            )
            
            # Save to database
            await frank_db.store_submission(submission)
            generated_submissions.append(submission.submission_id)
        
        return {
            "status": "success",
            "generated_count": count,
            "submission_ids": generated_submissions,
            "message": f"Generated {count} sample submissions",
            "database_used": config.database_type
        }
        
    except Exception as e:
        logger.error(f"Failed to generate sample data: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ================================
# MAIN EXECUTION
# ================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="FRANK Platform Stage 2 Server")
    parser.add_argument("--environment", choices=["local", "localstack", "aws"], 
                       default="localstack", help="Environment to run in")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    
    args = parser.parse_args()
    
    # Set environment
    os.environ['FRANK_ENVIRONMENT'] = args.environment
    
    logger.info(f"Starting FRANK Platform Stage 2")
    logger.info(f"Environment: {args.environment}")
    logger.info(f"Database type: {config.database_type}")
    
    # Run server
    uvicorn.run(
        "frank_stage2:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info"
    )