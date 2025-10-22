"""
Template manager for handling ARM templates
"""
import json
import os
from typing import Dict, List, Optional
from pathlib import Path


class TemplateManager:
    """Manages ARM templates and their operations"""
    
    def __init__(self, templates_dir: str = "templates"):
        self.templates_dir = Path(templates_dir)
        self.templates_dir.mkdir(exist_ok=True)
    
    def list_templates(self) -> List[str]:
        """List all available templates"""
        template_files = list(self.templates_dir.glob("*.json"))
        return [f.stem for f in template_files]
    
    def get_template(self, template_name: str) -> Optional[Dict]:
        """Get a template by name"""
        template_path = self.templates_dir / f"{template_name}.json"
        
        if not template_path.exists():
            return None
        
        try:
            with open(template_path, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            raise Exception(f"Failed to load template {template_name}: {str(e)}")
    
    def save_template(self, template_name: str, template: Dict) -> bool:
        """Save a template to disk"""
        template_path = self.templates_dir / f"{template_name}.json"
        
        try:
            with open(template_path, 'w') as f:
                json.dump(template, f, indent=2)
            return True
        except (IOError, TypeError) as e:
            raise Exception(f"Failed to save template {template_name}: {str(e)}")
    
    def delete_template(self, template_name: str) -> bool:
        """Delete a template from disk"""
        template_path = self.templates_dir / f"{template_name}.json"
        
        if not template_path.exists():
            return False
        
        try:
            template_path.unlink()
            return True
        except IOError as e:
            raise Exception(f"Failed to delete template {template_name}: {str(e)}")
    
    def validate_template(self, template: Dict) -> Dict:
        """Validate an ARM template structure"""
        errors = []
        warnings = []
        
        # Check required fields
        required_fields = ["$schema", "contentVersion", "resources"]
        for field in required_fields:
            if field not in template:
                errors.append(f"Missing required field: {field}")
        
        # Check schema
        if "$schema" in template:
            schema = template["$schema"]
            if not schema.startswith("https://schema.management.azure.com/"):
                warnings.append("Schema URL may not be valid")
        
        # Check resources
        if "resources" in template:
            if not isinstance(template["resources"], list):
                errors.append("Resources must be an array")
            else:
                for i, resource in enumerate(template["resources"]):
                    if not isinstance(resource, dict):
                        errors.append(f"Resource {i} must be an object")
                        continue
                    
                    required_resource_fields = ["type", "apiVersion", "name"]
                    for field in required_resource_fields:
                        if field not in resource:
                            errors.append(f"Resource {i} missing required field: {field}")
        
        # Check parameters
        if "parameters" in template:
            if not isinstance(template["parameters"], dict):
                errors.append("Parameters must be an object")
        
        # Check outputs
        if "outputs" in template:
            if not isinstance(template["outputs"], dict):
                errors.append("Outputs must be an object")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }
    
    def get_template_parameters(self, template: Dict) -> Dict:
        """Extract parameters from a template"""
        parameters = template.get("parameters", {})
        param_info = {}
        
        for param_name, param_def in parameters.items():
            param_info[param_name] = {
                "type": param_def.get("type", "string"),
                "defaultValue": param_def.get("defaultValue"),
                "description": param_def.get("metadata", {}).get("description", ""),
                "allowedValues": param_def.get("allowedValues"),
                "required": "defaultValue" not in param_def
            }
        
        return param_info
    
    def merge_templates(self, template_names: List[str], output_name: str = None) -> Dict:
        """Merge multiple templates into a single template"""
        if not template_names:
            raise ValueError("At least one template must be specified")
        
        merged_template = {
            "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentTemplate.json#",
            "contentVersion": "1.0.0.0",
            "parameters": {},
            "variables": {},
            "resources": [],
            "outputs": {}
        }
        
        for template_name in template_names:
            template = self.get_template(template_name)
            if not template:
                raise ValueError(f"Template {template_name} not found")
            
            # Merge parameters
            if "parameters" in template:
                merged_template["parameters"].update(template["parameters"])
            
            # Merge variables
            if "variables" in template:
                merged_template["variables"].update(template["variables"])
            
            # Merge resources
            if "resources" in template:
                merged_template["resources"].extend(template["resources"])
            
            # Merge outputs
            if "outputs" in template:
                merged_template["outputs"].update(template["outputs"])
        
        if output_name:
            self.save_template(output_name, merged_template)
        
        return merged_template
