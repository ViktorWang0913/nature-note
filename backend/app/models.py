import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, Integer, BigInteger, Float, Boolean, JSON, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base


def uid():
    return str(uuid.uuid4())


def now():
    return datetime.now(timezone.utc).isoformat()


class Entity:
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uid)
    created_at: Mapped[str] = mapped_column(String(40), default=now, index=True)


class User(Entity, Base):
    __tablename__ = 'users'
    identity: Mapped[str] = mapped_column(String(150), unique=True)
    name: Mapped[str] = mapped_column(String(80), default='自然观察者')
    avatar_url: Mapped[str] = mapped_column(Text, default='')
    bio: Mapped[str] = mapped_column(Text, default='')
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    deleted_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    last_seen_at: Mapped[str | None] = mapped_column(String(40), nullable=True)


class Asset(Entity, Base):
    __tablename__ = 'assets'
    user_id: Mapped[str | None] = mapped_column(ForeignKey('users.id'), index=True, nullable=True)
    title: Mapped[str] = mapped_column(String(200), default='照片')
    category: Mapped[str] = mapped_column(String(30), default='birds')
    source: Mapped[str] = mapped_column(String(30), default='photo')
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    key: Mapped[str] = mapped_column(Text)
    original_key: Mapped[str] = mapped_column(Text)
    thumbnail_key: Mapped[str] = mapped_column(Text)
    original_asset_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    version: Mapped[int] = mapped_column(Integer, default=1)
    history: Mapped[list] = mapped_column(JSON, default=list)
    is_mock: Mapped[bool] = mapped_column(Boolean, default=False)
    deleted: Mapped[bool] = mapped_column(Boolean, default=False)


class Favorite(Base):
    __tablename__ = 'favorites'
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), primary_key=True)
    asset_id: Mapped[str] = mapped_column(ForeignKey('assets.id'), primary_key=True)


class HiddenAsset(Base):
    __tablename__ = 'hidden_assets'
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), primary_key=True)
    asset_id: Mapped[str] = mapped_column(ForeignKey('assets.id'), primary_key=True)


class Project(Entity, Base):
    __tablename__ = 'projects'
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    title: Mapped[str] = mapped_column(String(200))
    version: Mapped[int] = mapped_column(Integer, default=1)
    layout: Mapped[dict] = mapped_column(JSON, default=dict)
    route_draft: Mapped[dict] = mapped_column(JSON, default=dict)
    asset_ids: Mapped[list] = mapped_column(JSON, default=list)
    cover_asset_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    updated_at: Mapped[str] = mapped_column(String(40), default=now)
    deleted: Mapped[bool] = mapped_column(Boolean, default=False)


class Template(Entity, Base):
    __tablename__ = 'templates'
    title: Mapped[str] = mapped_column(String(200))
    cover_key: Mapped[str] = mapped_column(Text, default='')
    layout: Mapped[dict] = mapped_column(JSON)


class GenerationSession(Entity, Base):
    __tablename__ = 'generation_sessions'
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    title: Mapped[str] = mapped_column(String(200), default='素材生成')
    messages: Mapped[list] = mapped_column(JSON, default=list)
    deleted: Mapped[bool] = mapped_column(Boolean, default=False)


class Task(Entity, Base):
    __tablename__ = 'tasks'
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(30), default='queued')
    input: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    is_mock: Mapped[bool] = mapped_column(Boolean, default=True)
    saved_asset_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    lease_owner: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lease_until: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    updated_at: Mapped[str] = mapped_column(String(40), default=now)
    deleted: Mapped[bool] = mapped_column(Boolean, default=False)


class Species(Entity, Base):
    __tablename__ = 'species'
    user_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    group_key: Mapped[str] = mapped_column(String(64), default='', index=True)
    cover_asset_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    name: Mapped[str] = mapped_column(String(100))
    scientific_name: Mapped[str] = mapped_column(String(150))
    aliases: Mapped[list] = mapped_column(JSON, default=list)
    category: Mapped[str] = mapped_column(String(40))
    description: Mapped[str] = mapped_column(Text)
    image_key: Mapped[str] = mapped_column(Text, default='')
    rarity: Mapped[str] = mapped_column(String(30), default='未标注')
    knowledge_version: Mapped[str] = mapped_column(String(30), default='seed-v1')
    source: Mapped[str] = mapped_column(Text, default='项目示例资料，待团队审核')


class Observation(Entity, Base):
    __tablename__ = 'observations'
    __table_args__ = (UniqueConstraint('user_id', 'asset_id', name='uq_observation_photo'),)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    asset_id: Mapped[str] = mapped_column(ForeignKey('assets.id'))
    species_id: Mapped[str | None] = mapped_column(ForeignKey('species.id'), nullable=True, index=True)
    project_id: Mapped[str | None] = mapped_column(ForeignKey('projects.id'), nullable=True)
    node_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    text: Mapped[str] = mapped_column(Text, default='')
    observed_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_mock: Mapped[bool] = mapped_column(Boolean, default=False)
    confirmation: Mapped[str] = mapped_column(String(30), default='pending')
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    confirmed_by: Mapped[str] = mapped_column(String(30), default='user')
    deleted: Mapped[bool] = mapped_column(Boolean, default=False)


class Archive(Entity, Base):
    __tablename__ = 'archives'
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    resource_type: Mapped[str] = mapped_column(String(40), index=True)
    resource_id: Mapped[str] = mapped_column(String(64), index=True)
    snapshot: Mapped[dict] = mapped_column(JSON)
    reason: Mapped[str] = mapped_column(String(200), default='用户删除')
    expires_at: Mapped[str | None] = mapped_column(String(40), nullable=True)


class Audit(Entity, Base):
    __tablename__ = 'audit_events'
    actor_id: Mapped[str] = mapped_column(String(64), index=True)
    action: Mapped[str] = mapped_column(String(80), index=True)
    target_id: Mapped[str] = mapped_column(String(64))
    detail: Mapped[dict] = mapped_column(JSON, default=dict)


class Provider(Base):
    __tablename__ = 'providers'
    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    message: Mapped[str] = mapped_column(String(200), default='服务维护中，请稍后再试')
    concurrency: Mapped[int] = mapped_column(Integer, default=10)
    daily_micros: Mapped[int] = mapped_column(BigInteger, default=5000000)
    next_daily_micros: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    effective_day: Mapped[str | None] = mapped_column(String(10), nullable=True)
    reserve_micros: Mapped[int] = mapped_column(BigInteger, default=5000000)
    context_limit: Mapped[int] = mapped_column(Integer, default=16000)
    output_limit: Mapped[int] = mapped_column(Integer, default=2000)
    updated_at: Mapped[str] = mapped_column(String(40), default=now)


class DailyBudget(Base):
    __tablename__ = 'daily_budgets'
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    identity_key: Mapped[str] = mapped_column(String(64), index=True)
    provider_id: Mapped[str] = mapped_column(String(20), index=True)
    day: Mapped[str] = mapped_column(String(10), index=True)
    limit_micros: Mapped[int] = mapped_column(BigInteger)
    held_micros: Mapped[int] = mapped_column(BigInteger, default=0)
    spent_micros: Mapped[int] = mapped_column(BigInteger, default=0)


class QuotaOverride(Base):
    __tablename__ = 'quota_overrides'
    id: Mapped[str] = mapped_column(String(90), primary_key=True)
    identity_key: Mapped[str] = mapped_column(String(64), index=True)
    provider_id: Mapped[str] = mapped_column(String(20))
    amount_micros: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    next_amount_micros: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    effective_day: Mapped[str | None] = mapped_column(String(10), nullable=True)


class UserTaskSlot(Base):
    __tablename__ = 'user_task_slots'
    id: Mapped[str] = mapped_column(String(90), primary_key=True)
    task_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class Charge(Base):
    __tablename__ = 'charges'
    task_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    budget_id: Mapped[str] = mapped_column(String(100))
    slot_id: Mapped[str] = mapped_column(String(90))
    provider_id: Mapped[str] = mapped_column(String(20), index=True)
    reserved_micros: Mapped[int] = mapped_column(BigInteger)
    actual_micros: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    state: Mapped[str] = mapped_column(String(30), default='reserved')
    usage: Mapped[dict] = mapped_column(JSON, default=dict)
    pricing: Mapped[dict] = mapped_column(JSON, default=dict)
    metering: Mapped[dict] = mapped_column(JSON, default=dict)
    evidence: Mapped[str] = mapped_column(Text, default='')
    created_at: Mapped[str] = mapped_column(String(40), default=now)
    updated_at: Mapped[str] = mapped_column(String(40), default=now)


class Track(Entity, Base):
    __tablename__ = 'tracks'
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    project_id: Mapped[str | None] = mapped_column(ForeignKey('projects.id'), nullable=True)
    title: Mapped[str] = mapped_column(String(200), default='观察轨迹')
    status: Mapped[str] = mapped_column(String(30), default='recording')
    coordinate_system: Mapped[str] = mapped_column(String(20), default='gcj02')
    ended_at: Mapped[str | None] = mapped_column(String(40), nullable=True)


class TrackPoint(Base):
    __tablename__ = 'track_points'
    track_id: Mapped[str] = mapped_column(ForeignKey('tracks.id'), primary_key=True)
    sequence: Mapped[int] = mapped_column(Integer, primary_key=True)
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    accuracy: Mapped[float] = mapped_column(Float)
    timestamp: Mapped[str] = mapped_column(String(40))
    segment: Mapped[int] = mapped_column(Integer, default=0)


class Node(Entity, Base):
    __tablename__ = 'nodes'
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    track_id: Mapped[str] = mapped_column(ForeignKey('tracks.id'))
    project_id: Mapped[str | None] = mapped_column(ForeignKey('projects.id'), nullable=True)
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    time: Mapped[str] = mapped_column(String(40), default=now)
    text: Mapped[str] = mapped_column(Text, default='')
    place_name: Mapped[str] = mapped_column(String(120), default='')
    asset_ids: Mapped[list] = mapped_column(JSON, default=list)
    cover_asset_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    species_id: Mapped[str | None] = mapped_column(ForeignKey('species.id'), nullable=True)


class Post(Entity, Base):
    __tablename__ = 'posts'
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    title: Mapped[str] = mapped_column(String(200))
    text: Mapped[str] = mapped_column(Text, default='')
    images: Mapped[list] = mapped_column(JSON)
    project_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    location_text: Mapped[str] = mapped_column(String(200), default='')
    hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    review_status: Mapped[str] = mapped_column(String(30), default='pending')
    review_reason: Mapped[str] = mapped_column(String(300), default='')


class Like(Base):
    __tablename__ = 'likes'
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), primary_key=True)
    post_id: Mapped[str] = mapped_column(ForeignKey('posts.id'), primary_key=True)


class Follow(Base):
    __tablename__ = 'follows'
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), primary_key=True)
    target_id: Mapped[str] = mapped_column(ForeignKey('users.id'), primary_key=True)


class Comment(Entity, Base):
    __tablename__ = 'comments'
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    post_id: Mapped[str] = mapped_column(ForeignKey('posts.id'), index=True)
    text: Mapped[str] = mapped_column(Text)
    deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    review_status: Mapped[str] = mapped_column(String(30), default='pending')
    review_reason: Mapped[str] = mapped_column(String(300), default='')


class AdminAccount(Base):
    __tablename__ = 'admin_accounts'
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default='owner')
    username: Mapped[str] = mapped_column(String(80), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    must_change: Mapped[bool] = mapped_column(Boolean, default=True)
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[str | None] = mapped_column(String(40), nullable=True)


class AdminSession(Base):
    __tablename__ = 'admin_sessions'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    admin_id: Mapped[str] = mapped_column(String(40))
    expires_at: Mapped[str] = mapped_column(String(40))
    verified_at: Mapped[str] = mapped_column(String(40))


class Feedback(Entity, Base):
    __tablename__ = 'feedback'
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    category: Mapped[str] = mapped_column(String(30))
    text: Mapped[str] = mapped_column(Text)
    asset_ids: Mapped[list] = mapped_column(JSON, default=list)
    task_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default='open')
    replies: Mapped[list] = mapped_column(JSON, default=list)


class Announcement(Entity, Base):
    __tablename__ = 'announcements'
    title: Mapped[str] = mapped_column(String(200))
    text: Mapped[str] = mapped_column(Text)
    user_ids: Mapped[list] = mapped_column(JSON, default=list)
    starts_at: Mapped[str] = mapped_column(String(40))
    ends_at: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(20), default='draft')


class PlatformControl(Base):
    __tablename__ = 'platform_controls'
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON, default=dict)


class Correction(Entity, Base):
    __tablename__ = 'species_corrections'
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    species_id: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(100))
    scientific_name: Mapped[str] = mapped_column(String(150))
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default='pending')


class ChatSession(Entity, Base):
    __tablename__ = 'chat_sessions'
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(200), default='问问自然记')
    summary: Mapped[str] = mapped_column(Text, default='')
    summary_until: Mapped[str | None] = mapped_column(String(40), nullable=True)
    deleted: Mapped[bool] = mapped_column(Boolean, default=False)


class ChatMessage(Entity, Base):
    __tablename__ = 'chat_messages'
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    task_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    role: Mapped[str] = mapped_column(String(20))
    text: Mapped[str] = mapped_column(Text, default='')
    asset_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default='complete')


class Notification(Entity, Base):
    __tablename__ = 'notifications'
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    actor_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    kind: Mapped[str] = mapped_column(String(30))
    target_type: Mapped[str] = mapped_column(String(30))
    target_id: Mapped[str] = mapped_column(String(64))
    summary: Mapped[str] = mapped_column(Text)
    read: Mapped[bool] = mapped_column(Boolean, default=False)


class Operation(Base):
    __tablename__ = 'operations'
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), primary_key=True)
    kind: Mapped[str] = mapped_column(String(30), primary_key=True)
    operation_id: Mapped[str] = mapped_column(String(150), primary_key=True)
    resource_id: Mapped[str] = mapped_column(String(64))


class Report(Entity, Base):
    __tablename__ = 'reports'
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    target_type: Mapped[str] = mapped_column(String(30))
    target_id: Mapped[str] = mapped_column(String(64))
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default='open')


class UserPhone(Base):
    __tablename__ = 'user_phones'
    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    phone_hash: Mapped[str] = mapped_column(String(64))
    masked_number: Mapped[str] = mapped_column(String(30))
    verified_at: Mapped[str] = mapped_column(String(40), default=now)


class WebCredential(Entity, Base):
    __tablename__ = 'web_credentials'
    username: Mapped[str] = mapped_column(String(80), unique=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), unique=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    must_change: Mapped[bool] = mapped_column(Boolean, default=True)
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[str | None] = mapped_column(String(40), nullable=True)


class WebSession(Base):
    __tablename__ = 'web_sessions'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    credential_id: Mapped[str] = mapped_column(ForeignKey('web_credentials.id'), index=True)
    expires_at: Mapped[str] = mapped_column(String(40), index=True)


class WebLoginAttempt(Base):
    __tablename__ = 'web_login_attempts'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[str | None] = mapped_column(String(40), nullable=True)
