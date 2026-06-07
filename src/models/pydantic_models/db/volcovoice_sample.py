from datetime import datetime
from typing import Optional

from sqlalchemy import Column, Text, UniqueConstraint
from sqlmodel import Field, SQLModel


class VolcovoiceSample(SQLModel, table=True):
    __tablename__ = "volcovoice_sample"
    __table_args__ = (
        UniqueConstraint("voice_character", "txt_hash", name="uq_volcovoice_sample_voice_hash"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    voice_character: str = Field(index=True, max_length=255, description="Display name of the sampled voice")
    age_type: Optional[str] = Field(default=None, index=True, max_length=255, description="Age group: 儿童, 少年/少女, 青年, 中年, 老年")
    sex: Optional[int] = Field(default=None, index=True, description="Gender: 1 for male, 0 for female")
    voice_model_type: Optional[str] = Field(default=None, index=True, max_length=255, description="Voice model family: big or small")
    voice_code: str = Field(max_length=255, description="Underlying volcovoice code")
    txt_content: str = Field(sa_column=Column(Text), description="Text synthesized for sampling")
    txt_hash: str = Field(index=True, max_length=64, description="SHA256 of txt_content for deduplication")
    local_file_path: Optional[str] = Field(default=None, sa_column=Column(Text), description="Downloaded local sample path")
    full_voice: Optional[str] = Field(default=None, sa_column=Column(Text), description="OBS url of the sampled full voice")
    response_json: Optional[str] = Field(default=None, sa_column=Column(Text), description="Raw volcovoice response json")
    debug_json_url: Optional[str] = Field(default=None, sa_column=Column(Text), description="Debug json url returned by volcovoice service")
    is_enabled: bool = Field(default=True, index=True, description="Whether the voice character is active/enabled")
    note: Optional[str] = Field(default=None, sa_column=Column(Text), description="Optional description or grouping note")
    priority: int = Field(default=0, index=True, description="Sorting priority, higher = higher ranking")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

