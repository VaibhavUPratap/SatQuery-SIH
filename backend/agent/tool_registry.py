import logging
from typing import Dict, Optional
from backend.models.base import BaseSpecialistModel
from backend.models.vqa.model import RemoteSensingVQAModel
from backend.models.captioning.model import RemoteSensingCaptionModel
from backend.models.grounding.model import RemoteSensingGroundingModel
from backend.models.change_detection.model import ChangeDetectionModel
from backend.models.change_vqa.model import ChangeVQAModel
from backend.models.optical_sar.model import OpticalSARFusionModel
from backend.models.land_cover.model import BigEarthNetLandCoverModel
from backend.models.nisar.change_detection import NISARChangeDetectionModel
from backend.models.nisar.flood_inundation import NISARFloodInundationModel

logger = logging.getLogger("terrapulse.registry")

class ToolRegistry:
    """
    Registry for managing and fetching specialist remote sensing models.
    Provides model-agnostic abstraction so tools can be hot-swapped.
    """
    
    def __init__(self):
        self._tools: Dict[str, BaseSpecialistModel] = {}
        self._initialize_registry()

    def _initialize_registry(self):
        logger.info("Initializing specialist tool registry...")
        try:
            # Register specialist models
            self.register("vqa", RemoteSensingVQAModel())
            self.register("caption", RemoteSensingCaptionModel())
            self.register("grounding", RemoteSensingGroundingModel())
            self.register("change_detection", ChangeDetectionModel())
            self.register("change_vqa", ChangeVQAModel())
            self.register("optical_sar", OpticalSARFusionModel())
            self.register("land_cover", BigEarthNetLandCoverModel())
            # TerraPulse NISAR Specialist Tools
            self.register("nisar_change", NISARChangeDetectionModel())
            self.register("nisar_flood", NISARFloodInundationModel())
            logger.info("Successfully registered specialist models including NISAR radar engines.")
        except Exception as e:
            logger.error(f"Error registering specialist models: {str(e)}")

    def register(self, name: str, tool: BaseSpecialistModel):
        """Register a new specialist tool."""
        self._tools[name] = tool
        logger.info(f"Registered tool '{name}': {tool.name} (v{tool.version})")

    def get_tool(self, name: str) -> Optional[BaseSpecialistModel]:
        """Fetch a registered specialist tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> Dict[str, str]:
        """List all registered tools and their class names."""
        return {name: f"{tool.name} (v{tool.version})" for name, tool in self._tools.items()}

# Global registry instance
tool_registry = ToolRegistry()
