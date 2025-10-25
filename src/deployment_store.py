"""
Deployment Data Store
Persistent storage for deployment metrics and history
"""

import sqlite3
import json
import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import os


@dataclass
class DeploymentRecord:
    """Deployment record data structure"""
    id: Optional[int] = None
    deployment_name: str = ""
    resource_group: str = ""
    template_name: str = ""
    location: str = ""
    project: str = ""
    environment: str = ""
    status: str = ""  # Running, Succeeded, Failed, Canceled
    start_time: Optional[datetime.datetime] = None
    end_time: Optional[datetime.datetime] = None
    duration_seconds: Optional[int] = None
    user_initiated: str = ""  # Could be enhanced with actual user tracking
    parameters: Optional[Dict] = None
    outputs: Optional[Dict] = None
    error_details: Optional[Dict] = None
    resource_count: int = 0
    resource_types: Optional[List[str]] = None
    retry_count: int = 0
    estimated_cost: Optional[float] = None
    validation_passed: bool = True
    vnet_address_space: Optional[str] = None
    sql_password_complexity: bool = True
    created_at: Optional[datetime.datetime] = None
    updated_at: Optional[datetime.datetime] = None


class DeploymentStore:
    """SQLite-based deployment data store"""
    
    def __init__(self, db_path: str = "deployments.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize the database with required tables"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Create deployments table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS deployments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    deployment_name TEXT NOT NULL,
                    resource_group TEXT NOT NULL,
                    template_name TEXT NOT NULL,
                    location TEXT NOT NULL,
                    project TEXT NOT NULL,
                    environment TEXT NOT NULL,
                    status TEXT NOT NULL,
                    start_time TIMESTAMP,
                    end_time TIMESTAMP,
                    duration_seconds INTEGER,
                    user_initiated TEXT,
                    parameters TEXT,  -- JSON
                    outputs TEXT,    -- JSON
                    error_details TEXT,  -- JSON
                    resource_count INTEGER DEFAULT 0,
                    resource_types TEXT,  -- JSON array
                    retry_count INTEGER DEFAULT 0,
                    estimated_cost REAL,
                    validation_passed BOOLEAN DEFAULT 1,
                    vnet_address_space TEXT,
                    sql_password_complexity BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indexes for better query performance
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_deployment_name ON deployments(deployment_name)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_resource_group ON deployments(resource_group)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_status ON deployments(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_start_time ON deployments(start_time)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_template_name ON deployments(template_name)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_project_env ON deployments(project, environment)")
            
            # Create deployment_metrics view for easy querying
            cursor.execute("""
                CREATE VIEW IF NOT EXISTS deployment_metrics AS
                SELECT 
                    deployment_name,
                    resource_group,
                    template_name,
                    location,
                    project,
                    environment,
                    status,
                    start_time,
                    end_time,
                    duration_seconds,
                    CASE 
                        WHEN duration_seconds < 60 THEN duration_seconds || 's'
                        WHEN duration_seconds < 3600 THEN (duration_seconds / 60) || 'm ' || (duration_seconds % 60) || 's'
                        ELSE (duration_seconds / 3600) || 'h ' || ((duration_seconds % 3600) / 60) || 'm'
                    END as duration_formatted,
                    resource_count,
                    retry_count,
                    estimated_cost,
                    validation_passed,
                    vnet_address_space,
                    sql_password_complexity,
                    created_at,
                    updated_at
                FROM deployments
            """)
            
            conn.commit()
    
    def create_deployment(self, record: DeploymentRecord) -> int:
        """Create a new deployment record"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Set timestamps
            now = datetime.datetime.now()
            record.created_at = now
            record.updated_at = now
            
            cursor.execute("""
                INSERT INTO deployments (
                    deployment_name, resource_group, template_name, location,
                    project, environment, status, start_time, end_time,
                    duration_seconds, user_initiated, parameters, outputs,
                    error_details, resource_count, resource_types, retry_count,
                    estimated_cost, validation_passed, vnet_address_space,
                    sql_password_complexity, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record.deployment_name, record.resource_group, record.template_name,
                record.location, record.project, record.environment, record.status,
                record.start_time, record.end_time, record.duration_seconds,
                record.user_initiated,
                json.dumps(record.parameters) if record.parameters else None,
                json.dumps(record.outputs) if record.outputs else None,
                json.dumps(record.error_details) if record.error_details else None,
                record.resource_count,
                json.dumps(record.resource_types) if record.resource_types else None,
                record.retry_count, record.estimated_cost, record.validation_passed,
                record.vnet_address_space, record.sql_password_complexity,
                record.created_at, record.updated_at
            ))
            
            return cursor.lastrowid
    
    def update_deployment(self, deployment_name: str, updates: Dict[str, Any]) -> bool:
        """Update an existing deployment record"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Prepare update fields
            set_clauses = []
            values = []
            
            for key, value in updates.items():
                if key in ['parameters', 'outputs', 'error_details', 'resource_types']:
                    set_clauses.append(f"{key} = ?")
                    values.append(json.dumps(value) if value else None)
                elif key == 'updated_at':
                    set_clauses.append(f"{key} = ?")
                    values.append(datetime.datetime.now())
                else:
                    set_clauses.append(f"{key} = ?")
                    values.append(value)
            
            if not set_clauses:
                return False
            
            values.append(deployment_name)
            
            cursor.execute(f"""
                UPDATE deployments 
                SET {', '.join(set_clauses)}
                WHERE deployment_name = ?
            """, values)
            
            return cursor.rowcount > 0
    
    def get_deployment(self, deployment_name: str) -> Optional[DeploymentRecord]:
        """Get a deployment record by name"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM deployments WHERE deployment_name = ?", (deployment_name,))
            row = cursor.fetchone()
            
            if not row:
                return None
            
            return self._row_to_record(row)
    
    def list_deployments(self, 
                        status: Optional[str] = None,
                        project: Optional[str] = None,
                        environment: Optional[str] = None,
                        template_name: Optional[str] = None,
                        limit: Optional[int] = None,
                        order_by: str = "start_time DESC") -> List[DeploymentRecord]:
        """List deployments with optional filters"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            where_clauses = []
            params = []
            
            if status:
                where_clauses.append("status = ?")
                params.append(status)
            
            if project:
                where_clauses.append("project = ?")
                params.append(project)
            
            if environment:
                where_clauses.append("environment = ?")
                params.append(environment)
            
            if template_name:
                where_clauses.append("template_name = ?")
                params.append(template_name)
            
            where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""
            limit_sql = f"LIMIT {limit}" if limit else ""
            
            cursor.execute(f"""
                SELECT * FROM deployments 
                {where_sql}
                ORDER BY {order_by}
                {limit_sql}
            """, params)
            
            rows = cursor.fetchall()
            return [self._row_to_record(row) for row in rows]
    
    def get_deployment_statistics(self) -> Dict[str, Any]:
        """Get comprehensive deployment statistics"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Basic counts
            cursor.execute("SELECT COUNT(*) FROM deployments")
            total_deployments = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM deployments WHERE status = 'Succeeded'")
            successful_deployments = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM deployments WHERE status = 'Failed'")
            failed_deployments = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM deployments WHERE status = 'Running'")
            running_deployments = cursor.fetchone()[0]
            
            # Success rate
            success_rate = (successful_deployments / total_deployments * 100) if total_deployments > 0 else 0
            
            # Average duration
            cursor.execute("""
                SELECT AVG(duration_seconds) 
                FROM deployments 
                WHERE status IN ('Succeeded', 'Failed') AND duration_seconds IS NOT NULL
            """)
            avg_duration = cursor.fetchone()[0] or 0
            
            # Template usage
            cursor.execute("""
                SELECT template_name, COUNT(*) as count
                FROM deployments 
                GROUP BY template_name 
                ORDER BY count DESC
            """)
            template_usage = dict(cursor.fetchall())
            
            # Location usage
            cursor.execute("""
                SELECT location, COUNT(*) as count
                FROM deployments 
                GROUP BY location 
                ORDER BY count DESC
            """)
            location_usage = dict(cursor.fetchall())
            
            # Recent deployments (last 7 days)
            cursor.execute("""
                SELECT COUNT(*) 
                FROM deployments 
                WHERE start_time >= datetime('now', '-7 days')
            """)
            recent_deployments = cursor.fetchone()[0]
            
            # Common failure reasons
            cursor.execute("""
                SELECT error_details
                FROM deployments 
                WHERE status = 'Failed' AND error_details IS NOT NULL
                ORDER BY start_time DESC
                LIMIT 10
            """)
            error_samples = [json.loads(row[0]) for row in cursor.fetchall() if row[0]]
            
            return {
                "total_deployments": total_deployments,
                "successful_deployments": successful_deployments,
                "failed_deployments": failed_deployments,
                "running_deployments": running_deployments,
                "success_rate": round(success_rate, 2),
                "average_duration_seconds": round(avg_duration, 2),
                "average_duration_formatted": self._format_duration(avg_duration),
                "template_usage": template_usage,
                "location_usage": location_usage,
                "recent_deployments_7_days": recent_deployments,
                "error_samples": error_samples
            }
    
    def get_deployment_trends(self, days: int = 30) -> Dict[str, Any]:
        """Get deployment trends over time"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Daily deployment counts
            cursor.execute("""
                SELECT DATE(start_time) as date, 
                       COUNT(*) as total,
                       SUM(CASE WHEN status = 'Succeeded' THEN 1 ELSE 0 END) as successful,
                       SUM(CASE WHEN status = 'Failed' THEN 1 ELSE 0 END) as failed
                FROM deployments 
                WHERE start_time >= datetime('now', '-{} days')
                GROUP BY DATE(start_time)
                ORDER BY date
            """.format(days))
            
            daily_trends = []
            for row in cursor.fetchall():
                daily_trends.append({
                    "date": row[0],
                    "total": row[1],
                    "successful": row[2],
                    "failed": row[3],
                    "success_rate": round((row[2] / row[1] * 100) if row[1] > 0 else 0, 2)
                })
            
            return {
                "daily_trends": daily_trends,
                "period_days": days
            }
    
    def _row_to_record(self, row) -> DeploymentRecord:
        """Convert database row to DeploymentRecord"""
        record = DeploymentRecord()
        record.id = row[0]
        record.deployment_name = row[1]
        record.resource_group = row[2]
        record.template_name = row[3]
        record.location = row[4]
        record.project = row[5]
        record.environment = row[6]
        record.status = row[7]
        record.start_time = datetime.datetime.fromisoformat(row[8]) if row[8] else None
        record.end_time = datetime.datetime.fromisoformat(row[9]) if row[9] else None
        record.duration_seconds = row[10]
        record.user_initiated = row[11]
        record.parameters = json.loads(row[12]) if row[12] else None
        record.outputs = json.loads(row[13]) if row[13] else None
        record.error_details = json.loads(row[14]) if row[14] else None
        record.resource_count = row[15]
        record.resource_types = json.loads(row[16]) if row[16] else None
        record.retry_count = row[17]
        record.estimated_cost = row[18]
        record.validation_passed = bool(row[19])
        record.vnet_address_space = row[20]
        record.sql_password_complexity = bool(row[21])
        record.created_at = datetime.datetime.fromisoformat(row[22]) if row[22] else None
        record.updated_at = datetime.datetime.fromisoformat(row[23]) if row[23] else None
        
        return record
    
    def _format_duration(self, seconds: float) -> str:
        """Format duration in seconds to human readable format"""
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{minutes}m {secs}s"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            return f"{hours}h {minutes}m"
    
    def cleanup_old_deployments(self, days: int = 90) -> int:
        """Remove deployments older than specified days"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM deployments 
                WHERE start_time < datetime('now', '-{} days')
            """.format(days))
            return cursor.rowcount
