"""
VNet Address Space Validator
Checks for IP address range overlaps with existing VNets
"""
import ipaddress
from typing import List, Dict, Tuple
from azure.mgmt.network import NetworkManagementClient
from azure.identity import DefaultAzureCredential
import os


class VNetValidator:
    """Validates VNet address spaces to prevent overlaps"""
    
    def __init__(self, azure_client=None, subscription_id: str = None):
        if azure_client:
            self.network_client = azure_client.network_client
            self.subscription_id = azure_client.subscription_id
        else:
            self.subscription_id = subscription_id or os.getenv('AZURE_SUBSCRIPTION_ID')
            if not self.subscription_id:
                raise ValueError("Azure subscription ID is required")
            
            self.credential = DefaultAzureCredential()
            self.network_client = NetworkManagementClient(
                self.credential, 
                self.subscription_id
            )
    
    def get_existing_vnet_ranges(self, location: str = None) -> List[Dict]:
        """Get all existing VNet address spaces in the subscription or region"""
        try:
            vnets = self.network_client.virtual_networks.list_all()
            
            existing_ranges = []
            for vnet in vnets:
                # Filter by location if specified
                if location and vnet.location.lower() != location.lower():
                    continue
                
                if vnet.address_space and vnet.address_space.address_prefixes:
                    for prefix in vnet.address_space.address_prefixes:
                        existing_ranges.append({
                            'vnet_name': vnet.name,
                            'resource_group': vnet.id.split('/')[4],
                            'location': vnet.location,
                            'address_prefix': prefix,
                            'network': ipaddress.ip_network(prefix, strict=False)
                        })
            
            return existing_ranges
        except Exception as e:
            raise Exception(f"Failed to get existing VNet ranges: {str(e)}")
    
    def check_address_space_overlap(self, proposed_prefix: str, location: str = None) -> Dict:
        """
        Check if a proposed address space overlaps with existing VNets
        
        Args:
            proposed_prefix: The proposed CIDR block (e.g., "10.0.0.0/16")
            location: Optional location to limit the check to
            
        Returns:
            Dict with validation results
        """
        try:
            # Parse the proposed address space
            proposed_network = ipaddress.ip_network(proposed_prefix, strict=False)
            
            # Get existing VNet ranges
            existing_ranges = self.get_existing_vnet_ranges(location)
            
            overlaps = []
            for existing in existing_ranges:
                if proposed_network.overlaps(existing['network']):
                    overlaps.append({
                        'vnet_name': existing['vnet_name'],
                        'resource_group': existing['resource_group'],
                        'location': existing['location'],
                        'conflicting_prefix': existing['address_prefix'],
                        'overlap_type': self._get_overlap_type(proposed_network, existing['network'])
                    })
            
            return {
                'is_valid': len(overlaps) == 0,
                'proposed_prefix': proposed_prefix,
                'overlaps': overlaps,
                'total_existing_vnets_checked': len(existing_ranges),
                'recommendations': self._get_recommendations(proposed_network, overlaps)
            }
            
        except Exception as e:
            return {
                'is_valid': False,
                'error': str(e),
                'proposed_prefix': proposed_prefix,
                'overlaps': [],
                'total_existing_vnets_checked': 0,
                'recommendations': []
            }
    
    def _get_overlap_type(self, proposed: ipaddress.IPv4Network, existing: ipaddress.IPv4Network) -> str:
        """Determine the type of overlap"""
        if proposed == existing:
            return "Exact match"
        elif proposed.subnet_of(existing):
            return "Proposed range is subset of existing"
        elif existing.subnet_of(proposed):
            return "Existing range is subset of proposed"
        else:
            return "Partial overlap"
    
    def _get_recommendations(self, proposed_network: ipaddress.IPv4Network, overlaps: List[Dict]) -> List[str]:
        """Generate recommendations for non-overlapping address spaces"""
        if not overlaps:
            return ["Address space is available and does not overlap with existing VNets"]
        
        recommendations = []
        
        # Get the network class
        if proposed_network.prefixlen <= 8:  # Class A
            base_networks = [
                ipaddress.ip_network("10.0.0.0/8"),
                ipaddress.ip_network("172.16.0.0/12"),
                ipaddress.ip_network("192.168.0.0/16")
            ]
        elif proposed_network.prefixlen <= 16:  # Class B
            base_networks = [
                ipaddress.ip_network("10.0.0.0/16"),
                ipaddress.ip_network("10.1.0.0/16"),
                ipaddress.ip_network("10.2.0.0/16"),
                ipaddress.ip_network("172.16.0.0/16"),
                ipaddress.ip_network("172.17.0.0/16"),
                ipaddress.ip_network("192.168.0.0/16"),
                ipaddress.ip_network("192.168.1.0/16")
            ]
        else:  # Class C or smaller
            base_networks = [
                ipaddress.ip_network("10.0.0.0/24"),
                ipaddress.ip_network("10.0.1.0/24"),
                ipaddress.ip_network("10.0.2.0/24"),
                ipaddress.ip_network("10.1.0.0/24"),
                ipaddress.ip_network("10.1.1.0/24"),
                ipaddress.ip_network("172.16.0.0/24"),
                ipaddress.ip_network("172.16.1.0/24"),
                ipaddress.ip_network("192.168.0.0/24"),
                ipaddress.ip_network("192.168.1.0/24")
            ]
        
        # Find non-overlapping alternatives
        for base_net in base_networks:
            if base_net.prefixlen == proposed_network.prefixlen:
                # Check if this base network overlaps with any existing
                overlaps_with_existing = False
                for overlap in overlaps:
                    # This is a simplified check - in practice you'd want to check against all existing VNets
                    if base_net.overlaps(ipaddress.ip_network(overlap['conflicting_prefix'])):
                        overlaps_with_existing = True
                        break
                
                if not overlaps_with_existing:
                    recommendations.append(f"Consider using: {base_net}")
                    if len(recommendations) >= 3:  # Limit to 3 recommendations
                        break
        
        if not recommendations:
            recommendations.append("Consider using a different IP range or contacting your network administrator")
        
        return recommendations
    
    def get_common_address_spaces(self) -> List[str]:
        """Get commonly used non-overlapping address spaces"""
        return [
            "10.0.0.0/16",    # Development
            "10.1.0.0/16",    # Staging
            "10.2.0.0/16",    # Production
            "10.3.0.0/16",    # Testing
            "10.4.0.0/16",    # UAT
            "172.16.0.0/16",  # Alternative range
            "172.17.0.0/16",  # Alternative range
            "192.168.0.0/16", # Local development
            "192.168.1.0/16"  # Local development
        ]
