import httpx
from dataclasses import dataclass
from typing import List
from utils.logger import get_logger

logger = get_logger("farm_sync_service")


@dataclass
class FieldData:
    field_id: int
    field_name: str
    field_size: float
    soil_type: str


@dataclass
class SyncResult:
    new_fields: List[int]
    existing_fields: List[int]
    inactive_fields: List[int]


class FarmSyncService:
    def __init__(self, api_url: str, api_token: str, timeout: int = 10):
        self.api_url = api_url.rstrip('/')
        self.api_token = api_token
        self.timeout = timeout
    
    def load_farm_fields(self, farm_id: int) -> List[FieldData]:
        url = f"{self.api_url}/api/v1/fields/{farm_id}/enterprise/"
        headers = {"Authorization": f"Token {self.api_token}"}
        
        try:
            fields = []
            with httpx.Client(timeout=self.timeout) as client:
                while url:
                    response = client.get(url, headers=headers)
                    response.raise_for_status()
                    data = response.json()
                    
                    for result in data.get("results", []):
                        fields.append(FieldData(
                            field_id=result["id"],
                            field_name=result["name"],
                            field_size=result["area"],
                            soil_type=result.get("soil_type", "sand")
                        ))
                    
                    url = data.get("next")
            
            logger.info("Farm fields loaded from API", farm_id=farm_id, field_count=len(fields))
            return fields
        
        except httpx.HTTPStatusError as e:
            logger.error("API request failed", farm_id=farm_id, status_code=e.response.status_code, error=str(e))
            raise ValueError(f"Failed to load farm {farm_id} from API: HTTP {e.response.status_code}")
        except httpx.RequestError as e:
            logger.error("API connection failed", farm_id=farm_id, error=str(e))
            raise ValueError(f"Failed to connect to API: {e}")
    
    def sync_fields(self, api_fields: List[FieldData], local_field_ids: List[int]) -> SyncResult:
        api_field_ids = {f.field_id for f in api_fields}
        local_field_ids_set = set(local_field_ids)
        
        new_fields = list(api_field_ids - local_field_ids_set)
        existing_fields = list(api_field_ids & local_field_ids_set)
        inactive_fields = list(local_field_ids_set - api_field_ids)
        
        result = SyncResult(
            new_fields=sorted(new_fields),
            existing_fields=sorted(existing_fields),
            inactive_fields=sorted(inactive_fields)
        )
        
        logger.info(
            "Field sync completed",
            new=len(result.new_fields),
            existing=len(result.existing_fields),
            inactive=len(result.inactive_fields)
        )
        
        return result
