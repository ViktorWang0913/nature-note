from typing import Literal, get_args
from pydantic import BaseModel, Field, ConfigDict, field_validator


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


class WechatLogin(Input):
    code: str = Field(min_length=1, max_length=300)
    create_new: bool = False


class DevLogin(Input):
    device_id: str = Field(min_length=1, max_length=100)
    create_new: bool = False


class CloseAccountInput(Input):
    code: str = Field(min_length=1, max_length=300)
    confirmation: Literal['注销账号']


class ProfilePatch(Input):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    nickname: str | None = Field(default=None, min_length=1, max_length=80)
    avatar_url: str | None = Field(default=None, max_length=2000)
    bio: str | None = Field(default=None, max_length=500)


class ProjectCreate(Input):
    title: str = Field(default='我的自然笔记', min_length=1, max_length=200)
    layout: dict | None = None
    operation_id: str | None = Field(default=None, min_length=1, max_length=150)


class ProjectPatch(Input):
    base_version: int = Field(ge=1)
    title: str | None = Field(default=None, min_length=1, max_length=200)
    layout: dict | None = None
    asset_ids: list[str] | None = None
    cover_asset_id: str | None = None


class FavoriteInput(Input):
    favorite: bool


class Crop(Input):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    width: float = Field(gt=0, le=1)
    height: float = Field(gt=0, le=1)


class EditInput(Input):
    rotation: float = Field(default=0, ge=-360, le=360)
    brightness: float = Field(default=1, ge=0, le=3)
    contrast: float = Field(default=1, ge=0, le=3)
    saturation: float = Field(default=1, ge=0, le=3)
    crop: Crop | None = None
    filter: Literal['none', 'warm', 'cool', 'grayscale', 'sepia'] = 'none'
    save_as_copy: bool = True


class TaskCreate(Input):
    kind: Literal['image_generation', 'image_recognition', 'image_polish', 'rag']
    input: dict = Field(default_factory=dict)
    operation_id: str | None = Field(default=None, min_length=1, max_length=150)


taskKinds = frozenset(get_args(TaskCreate.model_fields['kind'].annotation))


class ObservationCreate(Input):
    asset_id: str
    species_id: str | None = None
    species_name: str = Field(default='', max_length=100)
    scientific_name: str = Field(default='', max_length=150)
    confirmed_by: Literal['user', 'ai_suggestion'] = 'user'
    evidence: dict = Field(default_factory=dict)
    project_id: str | None = None
    node_id: str | None = None
    text: str = Field(default='', max_length=10000)
    observed_at: str | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    is_mock: bool = False


class SpeciesCover(Input):
    asset_id: str


class ObservationPatch(Input):
    species_id: str | None = None
    species_name: str = Field(default='', max_length=100)
    scientific_name: str = Field(default='', max_length=150)
    confirmed_by: Literal['user', 'ai_suggestion'] = 'user'
    evidence: dict | None = None
    text: str | None = Field(default=None, max_length=10000)
    observed_at: str | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)


class TrackCreate(Input):
    operation_id: str | None = Field(default=None, min_length=1, max_length=150)
    project_id: str | None = None
    title: str = Field(default='观察轨迹', max_length=200)


class TrackPatch(Input):
    status: Literal['recording', 'paused', 'ended']


class Point(Input):
    sequence: int = Field(ge=0)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    accuracy: float = Field(ge=0)
    timestamp: str = Field(max_length=40)
    segment: int = Field(default=0, ge=0)


class PointsInput(Input):
    points: list[Point] = Field(max_length=1000)


class NodeCreate(Input):
    place_name: str = Field(default='', max_length=120)
    operation_id: str | None = Field(default=None, min_length=1, max_length=150)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    time: str | None = None
    text: str = Field(default='', max_length=10000)
    asset_ids: list[str] = Field(default_factory=list, max_length=200)
    cover_asset_id: str | None = None
    species_id: str | None = None


class NodePatch(Input):
    place_name: str | None = Field(default=None, max_length=120)
    text: str | None = Field(default=None, max_length=10000)
    asset_ids: list[str] | None = Field(default=None, max_length=200)
    cover_asset_id: str | None = None
    species_id: str | None = None


class PostCreate(Input):
    title: str = Field(min_length=1, max_length=200)
    text: str = Field(default='', max_length=10000)
    asset_ids: list[str] = Field(min_length=1, max_length=9)
    project_id: str | None = None
    operation_id: str = Field(min_length=1, max_length=150)
    location_text: str = Field(default='', max_length=200)


class PostPatch(Input):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    text: str | None = Field(default=None, max_length=10000)
    location_text: str | None = Field(default=None, max_length=200)


class LikeInput(Input):
    liked: bool


class FollowInput(Input):
    following: bool


class CommentInput(Input):
    text: str = Field(min_length=1, max_length=2000)


class ReportInput(Input):
    target_type: Literal['post', 'comment', 'user']
    target_id: str
    reason: str = Field(min_length=1, max_length=2000)


class ReportResolve(Input):
    action: Literal['dismiss', 'hide']
