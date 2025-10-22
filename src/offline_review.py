"""
Offline template review and analysis system
"""
import json
import os
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from datetime import datetime
from .template_manager import TemplateManager
from .workload_config import WorkloadConfigManager, WorkloadConfiguration


class OfflineReviewManager:
    """Manages offline template review and analysis"""
    
    def __init__(self, templates_dir: str = "templates", sessions_file: str = "review_sessions.json"):
        self.template_manager = TemplateManager(templates_dir)
        self.workload_config = WorkloadConfigManager()
        self.sessions_file = sessions_file
        self.review_sessions = self._load_sessions()
    
    def _load_sessions(self) -> Dict:
        """Load sessions from file"""
        if os.path.exists(self.sessions_file):
            try:
                with open(self.sessions_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}
    
    def _save_sessions(self):
        """Save sessions to file"""
        try:
            with open(self.sessions_file, 'w') as f:
                json.dump(self.review_sessions, f, indent=2, default=str)
        except IOError as e:
            print(f"Warning: Failed to save sessions: {e}")
    
    def create_review_session(self, session_name: str, environment: str, size: str) -> str:
        """Create a new offline review session"""
        session_id = f"{session_name}_{environment}_{size}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Get workload configuration
        config = self.workload_config.get_configuration(environment, size)
        if not config:
            raise ValueError(f"No configuration found for {environment}_{size}")
        
        # Create session data
        session_data = {
            "session_id": session_id,
            "session_name": session_name,
            "environment": environment,
            "size": size,
            "workload_config": config,
            "created_at": datetime.now().isoformat(),
            "templates": {},
            "analysis": {},
            "recommendations": []
        }
        
        self.review_sessions[session_id] = session_data
        self._save_sessions()
        return session_id
    
    def add_template_to_session(self, session_id: str, template_name: str, 
                              custom_parameters: Dict = None) -> Dict:
        """Add a template to a review session with custom parameters"""
        if session_id not in self.review_sessions:
            raise ValueError(f"Session {session_id} not found")
        
        session = self.review_sessions[session_id]
        
        # Get the template
        template = self.template_manager.get_template(template_name)
        if not template:
            raise ValueError(f"Template {template_name} not found")
        
        # Apply workload configuration to parameters
        parameters = self._apply_workload_config_to_template(
            template, session["workload_config"], custom_parameters
        )
        
        # Generate template preview
        preview = self._generate_template_preview(template, parameters)
        
        # Store in session
        session["templates"][template_name] = {
            "template": template,
            "parameters": parameters,
            "preview": preview,
            "added_at": datetime.now().isoformat()
        }
        
        self._save_sessions()
        return preview
    
    def _apply_workload_config_to_template(self, template: Dict, 
                                         config: WorkloadConfiguration,
                                         custom_parameters: Dict = None) -> Dict:
        """Apply workload configuration to template parameters"""
        parameters = custom_parameters or {}
        
        # Apply configuration based on template type
        if "app-service" in template.get("$schema", ""):
            parameters.update({
                "sku": {"value": config.app_service.sku},
                "location": {"value": "East US"}  # Default location
            })
        elif "blob-storage" in template.get("$schema", ""):
            parameters.update({
                "sku": {"value": config.storage.sku},
                "accessTier": {"value": config.storage.access_tier},
                "location": {"value": "East US"}
            })
        elif "sql-server" in template.get("$schema", ""):
            parameters.update({
                "location": {"value": "East US"}
            })
        elif "sql-database" in template.get("$schema", ""):
            # This will be handled by the main template
            parameters.update({
                "sku": {"value": config.sql_databases.get("meta", {}).sku},
                "maxSizeBytes": {"value": config.sql_databases.get("meta", {}).max_size_gb * 1024**3},
                "location": {"value": "East US"}
            })
        elif "main-template" in template.get("$schema", ""):
            # Main template gets full configuration
            parameters.update({
                "environment": {"value": config.environment.value},
                "appServiceSku": {"value": config.app_service.sku},
                "sqlDatabaseSku": {"value": config.sql_databases.get("meta", {}).sku},
                "location": {"value": "East US"}
            })
        
        return parameters
    
    def _generate_template_preview(self, template: Dict, parameters: Dict) -> Dict:
        """Generate a preview of what the template will create"""
        preview = {
            "resources": [],
            "estimated_costs": {},
            "parameters_used": parameters,
            "validation": self.template_manager.validate_template(template)
        }
        
        # Analyze resources
        resources = template.get("resources", [])
        for resource in resources:
            resource_info = {
                "type": resource.get("type", "Unknown"),
                "name": resource.get("name", "Unknown"),
                "api_version": resource.get("apiVersion", "Unknown"),
                "location": resource.get("location", "Not specified"),
                "properties": self._extract_resource_properties(resource)
            }
            preview["resources"].append(resource_info)
        
        # Estimate costs (simplified)
        preview["estimated_costs"] = self._estimate_costs(resources, parameters)
        
        return preview
    
    def _extract_resource_properties(self, resource: Dict) -> Dict:
        """Extract key properties from a resource definition"""
        properties = {}
        
        # Extract SKU information
        if "sku" in resource:
            properties["sku"] = resource["sku"]
        
        # Extract size information
        if "properties" in resource:
            props = resource["properties"]
            if "maxSizeBytes" in props:
                properties["max_size_gb"] = props["maxSizeBytes"] / (1024**3)
            if "requestedServiceObjectiveName" in props:
                properties["service_objective"] = props["requestedServiceObjectiveName"]
        
        return properties
    
    def _estimate_costs(self, resources: List[Dict], parameters: Dict) -> Dict:
        """Estimate costs for resources (simplified)"""
        costs = {
            "monthly_estimate": 0,
            "breakdown": {}
        }
        
        # Simplified cost estimation based on SKUs
        sku_costs = {
            # App Service SKUs
            "F1": 0, "B1": 13, "B2": 26, "B3": 52,
            "S1": 73, "S2": 146, "S3": 292,
            "P1": 219, "P2": 438, "P3": 876,
            # SQL Database SKUs
            "Basic": 5, "S0": 15, "S1": 30, "S2": 60, "S3": 120,
            "P1": 90, "P2": 180, "P4": 360, "P6": 720, "P11": 1440, "P15": 2880,
            # Storage SKUs
            "Standard_LRS": 0.02, "Standard_GRS": 0.04, "Standard_RAGRS": 0.05
        }
        
        for resource in resources:
            resource_type = resource.get("type", "")
            resource_name = resource.get("name", "")
            
            # Estimate based on resource type and SKU
            if "Microsoft.Web" in resource_type:
                sku = resource.get("sku", {}).get("name", "F1")
                cost = sku_costs.get(sku, 0)
                costs["breakdown"][f"App Service ({resource_name})"] = cost
                costs["monthly_estimate"] += cost
            
            elif "Microsoft.Sql" in resource_type and "databases" in resource_type:
                sku = resource.get("properties", {}).get("requestedServiceObjectiveName", "Basic")
                cost = sku_costs.get(sku, 5)
                costs["breakdown"][f"SQL Database ({resource_name})"] = cost
                costs["monthly_estimate"] += cost
            
            elif "Microsoft.Storage" in resource_type:
                sku = resource.get("sku", {}).get("name", "Standard_LRS")
                cost = sku_costs.get(sku, 0.02)
                costs["breakdown"][f"Storage ({resource_name})"] = cost
                costs["monthly_estimate"] += cost
        
        return costs
    
    def analyze_session(self, session_id: str) -> Dict:
        """Analyze a review session and provide recommendations"""
        if session_id not in self.review_sessions:
            raise ValueError(f"Session {session_id} not found")
        
        session = self.review_sessions[session_id]
        analysis = {
            "session_id": session_id,
            "total_templates": len(session["templates"]),
            "total_resources": 0,
            "total_estimated_cost": 0,
            "recommendations": [],
            "warnings": [],
            "resource_summary": {}
        }
        
        # Analyze each template
        for template_name, template_data in session["templates"].items():
            preview = template_data["preview"]
            analysis["total_resources"] += len(preview["resources"])
            analysis["total_estimated_cost"] += preview["estimated_costs"]["monthly_estimate"]
            
            # Add resource types to summary
            for resource in preview["resources"]:
                resource_type = resource["type"]
                if resource_type not in analysis["resource_summary"]:
                    analysis["resource_summary"][resource_type] = 0
                analysis["resource_summary"][resource_type] += 1
        
        # Generate recommendations
        analysis["recommendations"] = self._generate_recommendations(session, analysis)
        
        # Store analysis in session
        session["analysis"] = analysis
        self._save_sessions()
        return analysis
    
    def _generate_recommendations(self, session: Dict, analysis: Dict) -> List[str]:
        """Generate recommendations based on session analysis"""
        recommendations = []
        
        # Cost recommendations
        if analysis["total_estimated_cost"] > 1000:
            recommendations.append("Consider using smaller SKUs for non-production environments")
        
        # Resource recommendations
        if "Microsoft.Web/sites" in analysis["resource_summary"]:
            recommendations.append("App Service is configured - ensure HTTPS is enabled")
        
        if "Microsoft.Sql/servers" in analysis["resource_summary"]:
            recommendations.append("SQL Server is configured - consider enabling firewall rules")
        
        if "Microsoft.Storage/storageAccounts" in analysis["resource_summary"]:
            recommendations.append("Storage Account is configured - consider enabling soft delete")
        
        # Environment-specific recommendations
        if session["environment"] == "prod":
            recommendations.append("Production environment - consider enabling monitoring and alerts")
            recommendations.append("Production environment - ensure backup policies are configured")
        
        return recommendations
    
    def get_session(self, session_id: str) -> Optional[Dict]:
        """Get a review session by ID"""
        return self.review_sessions.get(session_id)
    
    def list_sessions(self) -> List[Dict]:
        """List all review sessions"""
        return [
            {
                "session_id": session_id,
                "session_name": session["session_name"],
                "environment": session["environment"],
                "size": session["size"],
                "created_at": session["created_at"],
                "template_count": len(session["templates"])
            }
            for session_id, session in self.review_sessions.items()
        ]
    
    def export_session(self, session_id: str, output_dir: str = "exports") -> str:
        """Export a review session to files"""
        if session_id not in self.review_sessions:
            raise ValueError(f"Session {session_id} not found")
        
        session = self.review_sessions[session_id]
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        # Create session directory
        session_dir = output_path / session_id
        session_dir.mkdir(exist_ok=True)
        
        # Export session data
        with open(session_dir / "session.json", "w") as f:
            json.dump(session, f, indent=2, default=str)
        
        # Export individual templates
        templates_dir = session_dir / "templates"
        templates_dir.mkdir(exist_ok=True)
        
        for template_name, template_data in session["templates"].items():
            with open(templates_dir / f"{template_name}.json", "w") as f:
                json.dump(template_data["template"], f, indent=2)
            
            with open(templates_dir / f"{template_name}_parameters.json", "w") as f:
                json.dump(template_data["parameters"], f, indent=2)
        
        return str(session_dir)
    
    def compare_sessions(self, session_id1: str, session_id2: str) -> Dict:
        """Compare two review sessions"""
        session1 = self.get_session(session_id1)
        session2 = self.get_session(session_id2)
        
        if not session1 or not session2:
            raise ValueError("One or both sessions not found")
        
        comparison = {
            "session1": {
                "id": session_id1,
                "name": session1["session_name"],
                "environment": session1["environment"],
                "size": session1["size"]
            },
            "session2": {
                "id": session_id2,
                "name": session2["session_name"],
                "environment": session2["environment"],
                "size": session2["size"]
            },
            "differences": {
                "templates": [],
                "resources": [],
                "costs": {}
            }
        }
        
        # Compare templates
        templates1 = set(session1["templates"].keys())
        templates2 = set(session2["templates"].keys())
        
        comparison["differences"]["templates"] = {
            "only_in_session1": list(templates1 - templates2),
            "only_in_session2": list(templates2 - templates1),
            "common": list(templates1 & templates2)
        }
        
        # Compare costs
        cost1 = sum(t["preview"]["estimated_costs"]["monthly_estimate"] 
                   for t in session1["templates"].values())
        cost2 = sum(t["preview"]["estimated_costs"]["monthly_estimate"] 
                   for t in session2["templates"].values())
        
        comparison["differences"]["costs"] = {
            "session1_cost": cost1,
            "session2_cost": cost2,
            "difference": cost2 - cost1,
            "percentage_change": ((cost2 - cost1) / cost1 * 100) if cost1 > 0 else 0
        }
        
        return comparison
