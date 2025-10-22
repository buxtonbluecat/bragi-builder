"""
Workload configuration management for different environment types and sizes
"""
import json
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum


class WorkloadSize(Enum):
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
    ENTERPRISE = "enterprise"


class EnvironmentType(Enum):
    DEV = "dev"
    SIT = "sit"
    UAT = "uat"
    PRE_PROD = "pre-prod"
    PROD = "prod"


@dataclass
class AppServiceConfig:
    sku: str
    tier: str
    capacity: int = 1
    description: str = ""


@dataclass
class SqlDatabaseConfig:
    sku: str
    max_size_gb: int
    description: str = ""


@dataclass
class StorageConfig:
    sku: str
    replication: str
    access_tier: str
    description: str = ""


@dataclass
class WorkloadConfiguration:
    size: WorkloadSize
    environment: EnvironmentType
    app_service: AppServiceConfig
    sql_databases: Dict[str, SqlDatabaseConfig]  # database_name -> config
    storage: StorageConfig
    dwh_environments: List[str] = None  # Additional DWH environments to create
    
    def __post_init__(self):
        if self.dwh_environments is None:
            self.dwh_environments = []


class WorkloadConfigManager:
    """Manages workload configurations for different environments and sizes"""
    
    def __init__(self):
        self.configurations = self._load_default_configurations()
    
    def _load_default_configurations(self) -> Dict[str, WorkloadConfiguration]:
        """Load default workload configurations"""
        configs = {}
        
        # Define base configurations for each size
        size_configs = {
            WorkloadSize.SMALL: {
                "app_service": AppServiceConfig("B1", "Basic", 1, "Small development workload"),
                "sql_databases": {
                    "meta": SqlDatabaseConfig("Basic", 2, "Metadata database"),
                    "dwh": SqlDatabaseConfig("Basic", 5, "Data warehouse")
                },
                "storage": StorageConfig("Standard_LRS", "LRS", "Hot", "Local redundant storage"),
                "dwh_environments": []
            },
            WorkloadSize.MEDIUM: {
                "app_service": AppServiceConfig("S1", "Standard", 2, "Medium workload with scaling"),
                "sql_databases": {
                    "meta": SqlDatabaseConfig("S0", 10, "Metadata database"),
                    "dwh": SqlDatabaseConfig("S1", 20, "Data warehouse")
                },
                "storage": StorageConfig("Standard_GRS", "GRS", "Hot", "Geo-redundant storage"),
                "dwh_environments": ["sit", "uat"]
            },
            WorkloadSize.LARGE: {
                "app_service": AppServiceConfig("P1", "Premium", 3, "Large production workload"),
                "sql_databases": {
                    "meta": SqlDatabaseConfig("P1", 50, "Metadata database"),
                    "dwh": SqlDatabaseConfig("P2", 100, "Data warehouse")
                },
                "storage": StorageConfig("Standard_RAGRS", "RAGRS", "Hot", "Read-access geo-redundant storage"),
                "dwh_environments": ["sit", "uat", "pre-prod"]
            },
            WorkloadSize.ENTERPRISE: {
                "app_service": AppServiceConfig("P3", "Premium", 5, "Enterprise-scale workload"),
                "sql_databases": {
                    "meta": SqlDatabaseConfig("P4", 100, "Metadata database"),
                    "dwh": SqlDatabaseConfig("P6", 200, "Data warehouse")
                },
                "storage": StorageConfig("Standard_RAGRS", "RAGRS", "Hot", "Read-access geo-redundant storage"),
                "dwh_environments": ["sit", "uat", "pre-prod", "prod"]
            }
        }
        
        # Create configurations for each environment type and size combination
        for env_type in EnvironmentType:
            for size in WorkloadSize:
                base_config = size_configs[size]
                
                # Customize for production environments
                if env_type == EnvironmentType.PROD:
                    # Production gets enterprise-level resources regardless of size
                    config = WorkloadConfiguration(
                        size=WorkloadSize.ENTERPRISE,
                        environment=env_type,
                        app_service=AppServiceConfig("P3", "Premium", 5, "Production workload"),
                        sql_databases={
                            "meta": SqlDatabaseConfig("P4", 100, "Production metadata database"),
                            "dwh": SqlDatabaseConfig("P6", 200, "Production data warehouse")
                        },
                        storage=StorageConfig("Standard_RAGRS", "RAGRS", "Hot", "Production storage"),
                        dwh_environments=["prod"]
                    )
                else:
                    config = WorkloadConfiguration(
                        size=size,
                        environment=env_type,
                        app_service=base_config["app_service"],
                        sql_databases=base_config["sql_databases"].copy(),
                        storage=base_config["storage"],
                        dwh_environments=base_config["dwh_environments"].copy()
                    )
                
                configs[f"{env_type.value}_{size.value}"] = config
        
        return configs
    
    def get_configuration(self, environment: str, size: str) -> Optional[WorkloadConfiguration]:
        """Get a specific workload configuration"""
        key = f"{environment}_{size}"
        return self.configurations.get(key)
    
    def list_configurations(self) -> List[Dict]:
        """List all available configurations"""
        return [
            {
                "key": key,
                "environment": config.environment.value,
                "size": config.size.value,
                "app_service_sku": config.app_service.sku,
                "sql_databases": {name: {"sku": db.sku, "max_size_gb": db.max_size_gb} 
                                for name, db in config.sql_databases.items()},
                "storage_sku": config.storage.sku,
                "dwh_environments": config.dwh_environments
            }
            for key, config in self.configurations.items()
        ]
    
    def create_custom_configuration(self, environment: str, size: str, 
                                  custom_config: Dict) -> WorkloadConfiguration:
        """Create a custom workload configuration"""
        base_config = self.get_configuration(environment, size)
        if not base_config:
            raise ValueError(f"No base configuration found for {environment}_{size}")
        
        # Create a copy and apply customizations
        config_dict = asdict(base_config)
        config_dict.update(custom_config)
        
        # Convert back to WorkloadConfiguration
        return WorkloadConfiguration(
            size=WorkloadSize(config_dict["size"]),
            environment=EnvironmentType(config_dict["environment"]),
            app_service=AppServiceConfig(**config_dict["app_service"]),
            sql_databases={name: SqlDatabaseConfig(**db_config) 
                          for name, db_config in config_dict["sql_databases"].items()},
            storage=StorageConfig(**config_dict["storage"]),
            dwh_environments=config_dict.get("dwh_environments", [])
        )
    
    def get_available_sizes(self) -> List[str]:
        """Get list of available workload sizes"""
        return [size.value for size in WorkloadSize]
    
    def get_available_environments(self) -> List[str]:
        """Get list of available environment types"""
        return [env.value for env in EnvironmentType]
    
    def get_dwh_environments_for_config(self, environment: str, size: str) -> List[str]:
        """Get recommended DWH environments for a configuration"""
        config = self.get_configuration(environment, size)
        if not config:
            return []
        
        # Base environments based on the main environment
        base_envs = [environment]
        
        # Add recommended DWH environments
        if config.dwh_environments:
            base_envs.extend(config.dwh_environments)
        
        return list(set(base_envs))  # Remove duplicates
