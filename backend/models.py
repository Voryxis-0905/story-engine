import json
from typing import List, Dict, Optional, Literal, Any
from pydantic import BaseModel, Field

class WorldBuilderChunk(BaseModel):
    """Chunk of data for incremental world building."""
    chunk_id: int = Field(..., description="Index of this chunk, starting at 1")
    total_chunks: int = Field(..., description="Total number of chunks for the world build")
    payload: Dict[str, Any] = Field(..., description="Partial world configuration data for this chunk")

class WorldConfigUpdate(BaseModel):
    """Partial update payload for world_config.json via PUT endpoint."""
    # From models.py originally
    openrouter_api_key: Optional[str] = None
    openrouter_model: Optional[str] = None
    creation_status: Optional[Literal["not_started", "in_progress", "completed", "failed"]] = None
    creation_error: Optional[str] = None
    scope_selector: Optional[Literal["one-shot", "arc-only", "full-story"]] = None
    lore_rag_max_tokens: Optional[int] = None
    trait_definitions: Optional[Dict[str, Any]] = None  # simple schema storage per trait name
    titles: Optional[List[str]] = None
    # From main.py
    display_name: Optional[str] = None
    genre: Optional[str] = None
    power_system: Optional[str] = None
    tone: Optional[str] = None
    fixed_rules: Optional[List[str]] = None
    opening_mode: Optional[str] = None
    opening_text: Optional[str] = None
    protagonist_id: Optional[str] = None
    story_clock: Optional[Dict[str, Any]] = None
    foreshadowing_tracker: Optional[List[Any]] = None
    linter_notification_enabled: Optional[bool] = None
    linter_auto_run: Optional[bool] = None
    pacing_level: Optional[Literal["Slowburn", "Balanced", "Fast"]] = None
    pov_angle: Optional[Literal["1st_person", "3rd_person_limited", "3rd_person_omniscient"]] = None
    prelude_enabled: Optional[bool] = None

class TraitDefinition(BaseModel):
    name: str
    type: Literal["enum", "int", "bool", "float", "string"]
    values: Optional[List[Any]] = None  # allowed values for enum or range for int, etc.
    default: Optional[Any] = None

class CheckpointBranch(BaseModel):
    checkpoint_id: str
    next_checkpoint_ids: List[str]

class WorldCreationRequest(BaseModel):
    world_name: Optional[str] = None
    scope_type: Literal["one-shot", "arc-only", "full-story"] = "arc-only"
    prompt: Optional[str] = None
    interaction_mode: Optional[str] = None

class InterviewRequest(BaseModel):
    prompt: str
    scope_type: Literal["one-shot", "arc-only", "full-story"] = "arc-only"

class InterviewRespondRequest(BaseModel):
    prompt: str
    answers: List[str]
    scope_type: Literal["one-shot", "arc-only", "full-story"] = "arc-only"

class ImportWorldRequest(BaseModel):
    world_name: Optional[str] = None
    package_data: Dict[str, Any]

class StyleCardModel(BaseModel):
    perspective: str = "third_person_limited"
    voice: str = "narrative"
    pacing: str = "moderate"
    tone: str = "balanced"
    prose_guidelines: List[str] = Field(default_factory=list)
    taboo_words: List[str] = Field(default_factory=list)
    custom_instructions: str = ""

class PowerStatModel(BaseModel):
    realm: str = ""
    exp: int = 0
    sub_stats: Dict[str, Any] = Field(default_factory=dict)
    known_skills: List[str] = Field(default_factory=list)

class CreatorAssistantRequest(BaseModel):
    query: str
    section: Optional[str] = None

class LintChapterRequest(BaseModel):
    chapter_index: int

class RewriteChapterRequest(BaseModel):
    chapter_index: int
    linter_suggestions: str
