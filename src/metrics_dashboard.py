"""
Metrics Dashboard
API endpoints for deployment metrics and analytics
"""

from flask import Blueprint, jsonify, request
from src.deployment_store import DeploymentStore, DeploymentRecord
import datetime
from typing import Dict, Any

metrics_bp = Blueprint('metrics', __name__, url_prefix='/api/metrics')

# Initialize deployment store
deployment_store = DeploymentStore()


@metrics_bp.route('/statistics')
def get_statistics():
    """Get overall deployment statistics"""
    try:
        stats = deployment_store.get_deployment_statistics()
        return jsonify({
            "success": True,
            "statistics": stats
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Error getting statistics: {str(e)}"
        }), 500


@metrics_bp.route('/deployments')
def get_deployments():
    """Get deployments with optional filters"""
    try:
        # Get query parameters
        status = request.args.get('status')
        project = request.args.get('project')
        environment = request.args.get('environment')
        template_name = request.args.get('template_name')
        limit = request.args.get('limit', type=int)
        order_by = request.args.get('order_by', 'start_time DESC')
        
        deployments = deployment_store.list_deployments(
            status=status,
            project=project,
            environment=environment,
            template_name=template_name,
            limit=limit,
            order_by=order_by
        )
        
        # Convert to dictionaries for JSON serialization
        deployment_data = []
        for deployment in deployments:
            data = {
                "id": deployment.id,
                "deployment_name": deployment.deployment_name,
                "resource_group": deployment.resource_group,
                "template_name": deployment.template_name,
                "location": deployment.location,
                "project": deployment.project,
                "environment": deployment.environment,
                "status": deployment.status,
                "start_time": deployment.start_time.isoformat() if deployment.start_time else None,
                "end_time": deployment.end_time.isoformat() if deployment.end_time else None,
                "duration_seconds": deployment.duration_seconds,
                "duration_formatted": deployment_store._format_duration(deployment.duration_seconds) if deployment.duration_seconds else None,
                "user_initiated": deployment.user_initiated,
                "parameters": deployment.parameters,
                "outputs": deployment.outputs,
                "error_details": deployment.error_details,
                "resource_count": deployment.resource_count,
                "resource_types": deployment.resource_types,
                "retry_count": deployment.retry_count,
                "estimated_cost": deployment.estimated_cost,
                "validation_passed": deployment.validation_passed,
                "vnet_address_space": deployment.vnet_address_space,
                "sql_password_complexity": deployment.sql_password_complexity,
                "created_at": deployment.created_at.isoformat() if deployment.created_at else None,
                "updated_at": deployment.updated_at.isoformat() if deployment.updated_at else None
            }
            deployment_data.append(data)
        
        return jsonify({
            "success": True,
            "deployments": deployment_data,
            "total": len(deployment_data)
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Error getting deployments: {str(e)}"
        }), 500


@metrics_bp.route('/trends')
def get_trends():
    """Get deployment trends over time"""
    try:
        days = request.args.get('days', 30, type=int)
        trends = deployment_store.get_deployment_trends(days)
        
        return jsonify({
            "success": True,
            "trends": trends
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Error getting trends: {str(e)}"
        }), 500


@metrics_bp.route('/deployment/<deployment_name>')
def get_deployment_details(deployment_name):
    """Get detailed information about a specific deployment"""
    try:
        deployment = deployment_store.get_deployment(deployment_name)
        
        if not deployment:
            return jsonify({
                "success": False,
                "message": "Deployment not found"
            }), 404
        
        data = {
            "id": deployment.id,
            "deployment_name": deployment.deployment_name,
            "resource_group": deployment.resource_group,
            "template_name": deployment.template_name,
            "location": deployment.location,
            "project": deployment.project,
            "environment": deployment.environment,
            "status": deployment.status,
            "start_time": deployment.start_time.isoformat() if deployment.start_time else None,
            "end_time": deployment.end_time.isoformat() if deployment.end_time else None,
            "duration_seconds": deployment.duration_seconds,
            "duration_formatted": deployment_store._format_duration(deployment.duration_seconds) if deployment.duration_seconds else None,
            "user_initiated": deployment.user_initiated,
            "parameters": deployment.parameters,
            "outputs": deployment.outputs,
            "error_details": deployment.error_details,
            "resource_count": deployment.resource_count,
            "resource_types": deployment.resource_types,
            "retry_count": deployment.retry_count,
            "estimated_cost": deployment.estimated_cost,
            "validation_passed": deployment.validation_passed,
            "vnet_address_space": deployment.vnet_address_space,
            "sql_password_complexity": deployment.sql_password_complexity,
            "created_at": deployment.created_at.isoformat() if deployment.created_at else None,
            "updated_at": deployment.updated_at.isoformat() if deployment.updated_at else None
        }
        
        return jsonify({
            "success": True,
            "deployment": data
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Error getting deployment details: {str(e)}"
        }), 500


@metrics_bp.route('/health')
def health_check():
    """Health check for metrics service"""
    try:
        # Test database connection
        stats = deployment_store.get_deployment_statistics()
        
        return jsonify({
            "success": True,
            "status": "healthy",
            "database": "connected",
            "total_deployments": stats.get("total_deployments", 0)
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "status": "unhealthy",
            "error": str(e)
        }), 500
