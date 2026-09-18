from typing import Dict, List, Optional, Any, Literal
from pydantic import BaseModel, Field


class WorldBuilderChunk(BaseModel):
    chunk_id: int = Field(..., description="Index of this chunk, starting at 1")
    total_chunks: int = Field(..., description="Total number of chunks for the world build")
    payload: Dict[str, Any] = Field(..., description="Partial world configuration data for this chunk")


class WorldConfigUpdate(BaseModel):
    openrouter_api_key: Optional[str] = None
    openrouter_model: Optional[str] = None
    creation_status: Optional[Literal["not_started", "in_progress", "completed", "failed"]] = None
    creation_error: Optional[str] = None
    scope_selector: Optional[Literal["one-shot", "arc-only", "full-story"]] = None
    lore_rag_max_tokens: Optional[int] = None
    trait_definitions: Optional[Dict[str, Any]] = None
    titles: Optional[List[str]] = None
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
    output_length: Optional[Literal["Concise", "Standard", "Detailed"]] = None
    pov_angle: Optional[Literal["1st_person", "3rd_person_limited", "3rd_person_omniscient"]] = None
    prelude_enabled: Optional[bool] = None
    allow_unchecked_commit: Optional[bool] = None
    action_rules: Optional[List[Dict[str, Any]]] = None
    context_max_tokens: Optional[int] = None


class TraitDefinition(BaseModel):
    name: str
    type: Literal["enum", "int", "bool", "float", "string"]
    values: Optional[List[Any]] = None
    default: Optional[Any] = None


class SubBeat(BaseModel):
    beat_id: str
    description: str = ""
    required_conditions: List[Dict] = []
    completed: bool = False


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
    sub_stats: Dict[str, int] = {}
    known_skills: List[str] = []


class CreatorAssistantRequest(BaseModel):
    query: str
    section: Optional[str] = None


class LintChapterRequest(BaseModel):
    chapter_index: int


class RewriteChapterRequest(BaseModel):
    chapter_index: int
    linter_suggestions: str


class RuntimeConfigUpdate(BaseModel):
    openrouter_api_key: Optional[str] = None
    openrouter_model: Optional[str] = None
    api_key: Optional[str] = None
    api_key_action: Optional[Literal["keep", "replace", "delete"]] = None
    model_name: Optional[str] = None
    llm_provider: Optional[str] = None
    base_url: Optional[str] = None
    temperature: Optional[float] = None
    fallback_chain: Optional[list] = None
    creator_mode_enabled: Optional[bool] = None
    role_assignments: Optional[Dict[str, Optional[int]]] = None
    editor_enabled: Optional[bool] = None
    enable_extractor_cross_check: Optional[bool] = None


class ChapterContinueRequest(BaseModel):
    user_input: str
    request_id: Optional[str] = None
    expected_revision: Optional[int] = None


class ChapterStartRequest(BaseModel):
    opening_mode: Optional[str] = None
    opening_text: Optional[str] = None


class CharacterStateChange(BaseModel):
    location: Optional[str] = None
    affinity_delta: Dict[str, int] = {}
    sub_stats_delta: Dict[str, int] = {}
    exp_delta: int = 0
    knowledge_flags_add: List[str] = []
    inventory_add: List[str] = []
    inventory_remove: List[str] = []
    karma_delta: int = 0
    alive: Optional[bool] = None
    relationships_update: Dict[str, Optional[str]] = {}
    age: Optional[str] = None
    appearance: Optional[str] = None
    personality: Optional[str] = None
    backstory: Optional[str] = None
    abilities_and_limits: Optional[str] = None
    speech_style: Optional[str] = None
    secrets: Optional[str] = None


class StateChangesModel(BaseModel):
    characters: Dict[str, CharacterStateChange] = {}
    notes: str = ""
    story_clock_delta: Optional[Dict[str, Any]] = None
    foreshadowing_tracker_add: Optional[List[Any]] = None
    perception_data: Optional[Dict[str, Any]] = None
    steps: Optional[List[Dict[str, Any]]] = None
    variants: Optional[List[Dict[str, Any]]] = None


class CardModel(BaseModel):
    id: str
    type: str
    name: str
    content: str = ""
    unlock_checkpoint_id: Optional[str] = None
    status: str = "locked"
    keywords: List[str] = []
    entity_id: Optional[str] = None
    aliases: List[str] = Field(default_factory=list)
    scope: Optional[Literal["world_invariant", "branch_local"]] = None
    entity_status: Literal["active", "draft", "archived"] = "active"


class CheckpointBoundaryModel(BaseModel):
    locations: List[str] = []
    allowed_characters: List[str] = []
    time_window: str = ""


class CheckpointModel(BaseModel):
    checkpoint_id: str
    description: str = ""
    required_conditions: List[Dict] = []
    cards_unlocked: List[str] = []
    boundary: CheckpointBoundaryModel = CheckpointBoundaryModel()
    realm_updates: Dict[str, str] = {}
    status_effects: List[Dict[str, Any]] = []
    alternate_outcomes: List[Dict[str, Any]] = []
    default_next_checkpoint_id: Optional[str] = None
    sub_beats: List[SubBeat] = []


class CharacterModel(BaseModel):
    name: str
    location: str = ""
    affinity: Dict[str, int] = {}
    power_stat: PowerStatModel = PowerStatModel()
    knowledge_flags: List[str] = []
    inventory: List[str] = []
    karma: int = 0
    alive: bool = True
    relationships: Dict[str, str] = {}
    age: Optional[str] = ""
    traits: Dict[str, Any] = {}
    status_effects: List[Dict[str, Any]] = []
    appearance: str = ""
    personality: str = ""
    backstory: str = ""
    abilities_and_limits: str = ""
    speech_style: str = ""
    secrets: str = ""
    perception_data: Optional[Dict[str, Any]] = None


class CardRegistryUpdate(BaseModel):
    cards: List[CardModel]


class CanonTimelineUpdate(BaseModel):
    checkpoints: List[CheckpointModel]


class CharacterStateUpdate(BaseModel):
    characters: Dict[str, CharacterModel]


class ForceAdvanceRequest(BaseModel):
    target_checkpoint_id: str


class CreateSaveRequest(BaseModel):
    label: str = ""


class BranchRequest(BaseModel):
    new_world_name: str


class RegenerateRequest(BaseModel):
    request_id: Optional[str] = None
    expected_revision: Optional[int] = None


class ForeshadowingsUpdateReq(BaseModel):
    foreshadowing_tracker: Optional[List[Any]] = None
    foreshadowings: Optional[List[Any]] = None


class ForkRequest(BaseModel):
    checkpoint_id: str
    new_world_name: str


class WorldCanonFact(BaseModel):
    fact_id: str
    statement: str
    category: str = "lore"
    source_checkpoint_id: Optional[str] = None
    immutable: bool = True


class BranchLocalDeltaModel(BaseModel):
    overrides: Dict[str, str] = Field(default_factory=dict)


class LocationNodeModel(BaseModel):
    id: str = Field(..., description="Unique ID for this location node")
    name: str = Field(..., description="Display name of the location")
    description: str = ""
    x: float = Field(default=0, ge=0, le=100, description="X coordinate on map (0-100)")
    y: float = Field(default=0, ge=0, le=100, description="Y coordinate on map (0-100)")
    zone: str = Field(default="", description="Zone/area this location belongs to")
    unlock_realm: Optional[str] = Field(default=None, description="Minimum realm required to access")
    unlock_exp: int = Field(default=0, description="Minimum EXP required to access")
    unlock_checkpoint_id: Optional[str] = Field(default=None, description="Checkpoint required to unlock")
    is_starting_location: bool = False
    connected_to: List[str] = Field(default_factory=list, description="IDs of connected locations")
    tags: List[str] = Field(default_factory=list)


class LocationMapModel(BaseModel):
    locations: List[LocationNodeModel] = Field(default_factory=list)
