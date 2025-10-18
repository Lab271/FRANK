import os
import requests

# ====================================
# Container Metadata
# ====================================
def get_container_info():
    """Get container and runtime information for autoscaling identification"""
    try:
        # Get basic system info
        import socket
        import platform
        hostname = socket.gethostname()
        platform_info = platform.platform()
        
        # Try to get ECS task metadata (if running in Fargate)
        ecs_metadata = {}
        metadata_uri = os.environ.get('ECS_CONTAINER_METADATA_URI_V4')
        if metadata_uri:
            try:
                # Get container metadata via HTTP request
                response = requests.get(metadata_uri, timeout=2)
                container_data = response.json()
                ecs_metadata = {
                    "metadata_uri_available": True,
                    "container_name": container_data.get('Name', 'unknown'),
                    "docker_id": container_data.get('DockerId', 'unknown')[:12]  # Short format
                }
            except Exception:
                ecs_metadata = {"metadata_uri_available": False, "container_name": "unknown", "docker_id": "unknown"}
        else:
            ecs_metadata = {"metadata_uri_available": False, "container_name": "unknown", "docker_id": "unknown"}
        
        # Get process ID for uniqueness  
        pid = os.getpid()
        
        return {
            "hostname": hostname,
            "platform": platform_info,
            "pid": pid,
            "ecs_metadata": ecs_metadata,
            "container_id": ecs_metadata.get("docker_id", "unknown")
        }
    except Exception as e:
        return {
            "hostname": "unknown",
            "platform": "unknown", 
            "pid": os.getpid(),
            "ecs_metadata": {"error": str(e)},
            "container_id": "unknown"
        }
