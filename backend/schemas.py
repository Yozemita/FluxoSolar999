from datetime import datetime
from enum import Enum
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, str_strip_whitespace=True)


class Merchant(str, Enum):
    SHOPEE = "SHOPEE"
    SHEIN = "SHEIN"


HOSTS = {
    "SHOPEE": {"br.shp.ee", "shopee.com.br", "s.shopee.com.br", "shope.ee", "collshp.com"},
    "SHEIN": {"onelink.shein.com", "br.shein.com", "www.shein.com", "shein.com"},
}


def validate_url(value, merchant):
    try:
        u = urlsplit(value)
        valid = u.scheme == "https" and u.hostname in HOSTS[merchant] and not u.username and not u.password and u.port in (None, 443)
    except ValueError:
        valid = False
    if not valid:
        raise ValueError("Use um link HTTPS oficial do comerciante selecionado.")
    return value  # Preserve the original affiliate query byte-for-byte.


class ProductInput(Input):
    merchant: Merchant
    external_code: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=200)
    affiliate_url: str = Field(max_length=2048)
    storefront_url: str | None = Field(default=None, max_length=2048)

    @field_validator("affiliate_url", "storefront_url")
    @classmethod
    def official_url(cls, value, info):
        if value is None:
            return value
        merchant = info.data.get("merchant")
        if merchant is None:
            return value
        return validate_url(value, merchant.value)


class Login(Input):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=1024)


class Metric(Input):
    views: int = Field(default=0, ge=0, le=2_147_483_647)
    profile_visits: int = Field(default=0, ge=0, le=2_147_483_647)
    follows: int = Field(default=0, ge=0, le=2_147_483_647)
    clicks: int = Field(default=0, ge=0, le=2_147_483_647)
    conversions: int = Field(default=0, ge=0, le=2_147_483_647)
    shares: int = Field(default=0, ge=0, le=2_147_483_647)
    commission: float = Field(default=0, ge=0, le=1_000_000_000)
    spend: float = Field(default=0, ge=0, le=1_000_000_000)


class MetricImport(Metric):
    event_id: str = Field(min_length=1, max_length=190)
    product_id: int = Field(gt=0)

    @field_validator("event_id")
    @classmethod
    def reserved_id(cls, value):
        if value.startswith("manual:"):
            raise ValueError("O prefixo manual: é reservado para snapshots manuais.")
        return value


class CreativeInput(Input):
    product_id: int = Field(gt=0)


class CreativeUpdate(Input):
    title: str = Field(min_length=1, max_length=200)
    caption: str = Field(min_length=1, max_length=5000)
    prompt: str = Field(min_length=1, max_length=10000)
    media_key: str | None = Field(default=None, max_length=512)


class ScheduleInput(Input):
    creative_id: int = Field(gt=0)
    channel: Literal["pinterest", "tiktok", "instagram", "other"]
    scheduled_for: datetime

    @field_validator("scheduled_for")
    @classmethod
    def aware(cls, value):
        if value.tzinfo is None:
            raise ValueError("Informe a data com fuso horário.")
        return value


class AgentInput(Input):
    product_id: int | None = Field(default=None, gt=0)


class MediaInput(Input):
    content_type: Literal["image/jpeg", "image/png", "image/webp"]
