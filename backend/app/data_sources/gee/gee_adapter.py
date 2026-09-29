"""Google Earth Engine (GEE) Source Adapter.

Connects to authentic Earth Engine datasets (SRTM, Dynamic World).
Explicitly reports UNAVAILABLE when credentials/session are inactive.
Strictly prohibits mathematical synthetic terrain generation.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel

from app.domain.provenance import DataMode, DataSourceMeta


class GEEStatus(BaseModel):
    """Operational status of Earth Engine integration."""

    is_authenticated: bool
    project_id: Optional[str]
    datasets_available: List[str]
    error_message: Optional[str]
    provenance: DataSourceMeta


class GEEAdapter:
    """Adapter for querying authentic satellite datasets from Google Earth Engine."""

    def __init__(
        self,
        project_id: Optional[str] = None,
        service_account_email: Optional[str] = None,
        private_key_path: Optional[str] = None,
    ) -> None:
        self.project_id = project_id
        self.service_account_email = service_account_email
        self.private_key_path = private_key_path
        self._is_initialized = False
        self._init_error: Optional[str] = None

    def initialize(self) -> bool:
        """Attempt to authenticate and initialize Earth Engine session."""
        if self._is_initialized:
            return True

        try:
            import ee
            if self.service_account_email and self.private_key_path:
                credentials = ee.ServiceAccountCredentials(
                    self.service_account_email,
                    self.private_key_path,
                )
                ee.Initialize(credentials, project=self.project_id)
            elif self.project_id:
                ee.Initialize(project=self.project_id)
            else:
                ee.Initialize()

            self._is_initialized = True
            self._init_error = None
            return True
        except Exception as exc:
            self._is_initialized = False
            self._init_error = str(exc)
            return False

    def get_status(self) -> GEEStatus:
        """Return connectivity state and available satellite collections."""
        is_ok = self.initialize()
        now_utc = datetime.now(timezone.utc).isoformat()

        if is_ok:
            return GEEStatus(
                is_authenticated=True,
                project_id=self.project_id,
                datasets_available=[
                    "USGS/SRTMGL1_003 (SRTM 30m Digital Elevation)",
                    "GOOGLE/DYNAMICWORLD/V1 (10m Near Real-Time Land Cover)",
                ],
                error_message=None,
                provenance=DataSourceMeta(
                    source="Google Earth Engine",
                    dataset="NASA SRTM & ESA Sentinel-2 Dynamic World",
                    retrieved_at=now_utc,
                    status=DataMode.LIVE,
                    confidence="HIGH",
                    is_forecast=False,
                    attribution="Google Earth Engine planetary data catalog",
                ),
            )
        else:
            return GEEStatus(
                is_authenticated=False,
                project_id=self.project_id,
                datasets_available=[],
                error_message=self._init_error or "GEE credentials not authenticated in local environment",
                provenance=DataSourceMeta(
                    source="Google Earth Engine",
                    dataset="Planetary Satellite Collections",
                    retrieved_at=now_utc,
                    status=DataMode.UNAVAILABLE,
                    confidence="ESTIMATED",
                    is_forecast=False,
                    attribution="Requires authenticated Google Earth Engine project",
                ),
            )

    def get_elevation_at_point(self, lat: float, lon: float) -> Optional[float]:
        """Query authentic SRTM 30m elevation. Returns None if GEE is unavailable."""
        if not self.initialize():
            return None

        try:
            import ee
            point = ee.Geometry.Point([lon, lat])
            srtm = ee.Image("USGS/SRTMGL1_003")
            val = srtm.reduceRegion(ee.Reducer.first(), point, 30).get("elevation").getInfo()
            return float(val) if val is not None else None
        except Exception:
            return None
