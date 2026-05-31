from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


ItemCategory = Literal[
    "LP",
    "CD",
    "CASSETTE",
    "8TRACK",
    "DIGITAL",
    "REEL_TO_REEL",
    "T_SHIRT",
    "POSTER",
    "LIGHT_STICK",
    "HAT",
    "BAG",
    "CUP",
    "OTHER",
]

SizeGroup = Literal["STD", "BOOK", "LP", "LP10", "LP7", "OVERSIZE", "CASSETTE", "8TRACK", "REEL_TO_REEL", "GOODS"]
ItemStatus = Literal["IN_COLLECTION", "LOANED", "SOLD", "LOST", "ARCHIVED"]
SignatureType = Literal["NONE", "IN_PERSON", "PURCHASE_INCLUDED", "UNKNOWN"]
ReviewStatus = Literal["AUTO_APPROVED", "NEEDS_REVIEW", "APPROVED", "REJECTED"]
AssetType = Literal["AUDIO", "IMAGE", "DOCUMENT", "VIDEO"]
LinkType = Literal["FULL_ALBUM", "TRACK", "SCAN", "REFERENCE", "PROOF"]
ExternalSourceCode = Literal["DISCOGS", "MANIADB", "ALADIN"]
AlbumMasterSource = Literal["AUTO", "DISCOGS", "MANIADB"]
AlbumMasterBoundSource = Literal["DISCOGS", "MANIADB", "MANUAL"]
MetadataSearchSource = Literal["AUTO", "DISCOGS", "ALADIN", "MANIADB", "MUSICBRAINZ"]
MetadataSyncSource = Literal["ALL", "DISCOGS", "MANIADB", "ALADIN"]
DomainCode = Literal["KOREA", "JAPAN", "GREATER_CHINA", "WESTERN", "OTHER_ASIA", "WORLD", "WORLD_OTHER", "UNKNOWN"]
ReleaseType = Literal["ALBUM", "EP", "SINGLE"]
ClassificationOptionGroup = Literal["SUBTYPE", "SOUNDTRACK"]
MusicCategory = Literal["LP", "CD", "CASSETTE", "8TRACK", "DIGITAL", "REEL_TO_REEL"]
SourceLinkState = Literal["ANY", "MISSING", "LINKED"]
AuthRole = Literal["ADMIN", "OPERATOR", "VIEWER"]
CustomerTrackRequestStatus = Literal["REQUESTED", "PLAYING", "RETURNED", "CANCELLED"]
PurchaseImportVendor = Literal["SAILMUSIC", "AMAZON", "EBAY", "ALADIN", "YES24", "OTHER"]
PurchaseImportSourceType = Literal["EMAIL_HTML", "EMAIL_TEXT", "FILE_UPLOAD", "MANUAL"]
PurchaseImportStatus = Literal["PENDING", "CREATED", "IGNORED"]
CabinetSortPolicy = Literal["ARTIST_RELEASE_TITLE", "LABEL_ID", "TITLE_RELEASE"]
BackupScope = Literal["DB", "FULL"]
GoodsCategory = Literal["POSTER", "T_SHIRT", "LIGHT_STICK", "HAT", "BAG", "CUP", "OTHER"]
GoodsStatus = Literal["ACTIVE", "ARCHIVED"]
GoodsLinkedState = Literal["ANY", "LINKED", "UNLINKED"]
GoodsCollectibleRelationState = Literal["ANY", "LINKED", "UNLINKED"]
GoodsCollectibleRelationType = Literal["SERIES", "VARIANT", "SET_MEMBER", "RELATED", "PROMO_FOR"]


class BarcodeIngestRequest(BaseModel):
    barcode: str = Field(min_length=3, max_length=64)
    category: ItemCategory | None = None
    source: MetadataSearchSource = "AUTO"
    limit: int = Field(default=5, ge=1, le=20)


class MetadataCandidate(BaseModel):
    source: str
    external_id: str
    title: str
    artist_or_brand: str | None = None
    release_year: int | None = None
    released_date: str | None = None
    country: str | None = None
    format_name: str | None = None
    barcode: str | None = None
    catalog_no: str | None = None
    label_name: str | None = None
    cover_image_url: str | None = None
    track_list: list[str] = Field(default_factory=list)
    media_type: str | None = None
    release_type: ReleaseType | None = None
    domain_code: DomainCode | None = None
    genres: list[str] = Field(default_factory=list)
    styles: list[str] = Field(default_factory=list)
    styles: list[str] = Field(default_factory=list)
    disc_count: int | None = None
    speed_rpm: int | None = None
    disc_type: str | None = None
    has_obi: bool | None = None
    runout_matrix: list[str] = Field(default_factory=list)
    pressing_country: str | None = None
    source_notes: str | None = None
    credits: list[str] = Field(default_factory=list)
    identifier_items: list[dict[str, Any]] = Field(default_factory=list)
    image_items: list[dict[str, Any]] = Field(default_factory=list)
    company_items: list[dict[str, Any]] = Field(default_factory=list)
    series: list[str] = Field(default_factory=list)
    format_items: list[dict[str, Any]] = Field(default_factory=list)
    track_items: list[dict[str, Any]] = Field(default_factory=list)
    label_items: list[dict[str, Any]] = Field(default_factory=list)
    is_owned: bool = False
    owned_count: int = 0
    confidence: float
    raw: dict[str, Any] = Field(default_factory=dict)


class BarcodeIngestResponse(BaseModel):
    query_type: Literal["barcode"] = "barcode"
    query: str
    candidates: list[MetadataCandidate]


class BarcodePlacementRecommendationRequest(BaseModel):
    category: ItemCategory
    size_group: SizeGroup | None = None
    domain_code: DomainCode | None = None
    format_name: str | None = None
    artist_or_brand: str | None = None
    title: str | None = None
    release_year: int | None = Field(default=None, ge=1900, le=2100)
    barcode: str | None = None
    source: Literal["DISCOGS", "MANIADB", "ALADIN", "AUTO"] | None = None
    package_hint: str | None = None
    thickness_mm: int | None = Field(default=None, ge=1)


class BarcodePlacementRecommendationItem(BaseModel):
    rank: int = Field(ge=1)
    storage_slot_id: int
    slot_code: str
    cabinet_name: str | None = None
    column_code: str | None = None
    cell_code: str | None = None
    slot_display_name: str
    free_thickness_mm: int = Field(ge=0)
    used_thickness_mm: int = Field(ge=0)
    capacity_mm: int = Field(ge=0)
    occupancy_percent: int = Field(ge=0)


class BarcodePlacementRecommendationResponse(BaseModel):
    available: bool = False
    recommendations: list[BarcodePlacementRecommendationItem] = Field(default_factory=list)
    fallback_message: str | None = None


class QueryIngestRequest(BaseModel):
    category: ItemCategory | None = None
    source: MetadataSearchSource = "AUTO"
    query: str | None = None
    artist_or_brand: str | None = None
    title: str | None = None
    catalog_no: str | None = None
    runout: str | None = None
    label_name: str | None = None
    release_year: int | None = Field(default=None, ge=1900, le=2100)
    country: str | None = Field(default=None, min_length=2, max_length=2)
    limit: int = Field(default=5, ge=1, le=20)


class QueryIngestResponse(BaseModel):
    query_type: Literal["query"] = "query"
    query: str
    candidates: list[MetadataCandidate]


class GoodsItemAlbumMasterMapping(BaseModel):
    album_master_id: int
    title: str
    artist_or_brand: str | None = None


class GoodsItemBase(BaseModel):
    category: GoodsCategory
    goods_name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    quantity: int = Field(default=1, ge=1, le=9999)
    size_group: SizeGroup = "GOODS"
    storage_slot_id: int | None = Field(default=None, ge=1)
    status: GoodsStatus = "ACTIVE"
    domain_code: DomainCode | None = None
    memory_note: str | None = None
    image_urls: list[str] = Field(default_factory=list)
    primary_image_url: str | None = None
    poster_storage_spec: str | None = None
    tshirt_size: str | None = None
    cup_material: str | None = None
    hat_size: str | None = None

    @field_validator("image_urls", mode="before")
    @classmethod
    def _normalize_goods_image_urls(cls, value: Any) -> list[str]:
        if value in (None, "", []):
            return []
        if isinstance(value, str):
            return [line.strip() for line in value.splitlines() if line.strip()]
        if isinstance(value, list):
            return [str(item or "").strip() for item in value if str(item or "").strip()]
        return []


class GoodsItemCreateRequest(GoodsItemBase):
    album_master_ids: list[int] = Field(default_factory=list)
    artist_names: list[str] = Field(default_factory=list)
    label_names: list[str] = Field(default_factory=list)
    linked_owned_item_id: int | None = Field(default=None, ge=1)


class GoodsItemUpdateRequest(BaseModel):
    category: GoodsCategory | None = None
    goods_name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    quantity: int | None = Field(default=None, ge=1, le=9999)
    size_group: SizeGroup | None = None
    storage_slot_id: int | None = Field(default=None, ge=1)
    status: GoodsStatus | None = None
    domain_code: DomainCode | None = None
    memory_note: str | None = None
    image_urls: list[str] | None = None
    primary_image_url: str | None = None
    poster_storage_spec: str | None = None
    tshirt_size: str | None = None
    cup_material: str | None = None
    hat_size: str | None = None
    linked_owned_item_id: int | None = Field(default=None, ge=1)


class GoodsItemMappingUpdateRequest(BaseModel):
    album_master_ids: list[int] = Field(default_factory=list)
    artist_names: list[str] = Field(default_factory=list)
    label_names: list[str] = Field(default_factory=list)


class GoodsItemCollectibleRelation(BaseModel):
    relation_type: GoodsCollectibleRelationType
    direction: Literal["OUTGOING"] = "OUTGOING"
    linked_goods_item_id: int = Field(ge=1)
    linked_goods_name: str
    linked_category: GoodsCategory | None = None
    note: str | None = None
    display_order: int = 0


class GoodsItemRelationUpdateItem(BaseModel):
    relation_type: GoodsCollectibleRelationType
    linked_goods_item_id: int = Field(ge=1)
    note: str | None = None
    display_order: int | None = None


class GoodsItemRelationUpdateRequest(BaseModel):
    relations: list[GoodsItemRelationUpdateItem] = Field(default_factory=list)


class GoodsItemResponse(GoodsItemBase):
    id: int
    slot_code: str | None = None
    slot_display_name: str | None = None
    linked_owned_item_id: int | None = None
    album_master_mappings: list[GoodsItemAlbumMasterMapping] = Field(default_factory=list)
    artist_mappings: list[str] = Field(default_factory=list)
    label_mappings: list[str] = Field(default_factory=list)
    collectible_relations: list[GoodsItemCollectibleRelation] = Field(default_factory=list)
    collectible_relation_count: int = 0
    relation_badges: list[GoodsCollectibleRelationType] = Field(default_factory=list)
    collectible_relation_preview: list[GoodsItemCollectibleRelation] = Field(default_factory=list)
    created_at: str
    updated_at: str


class GoodsItemSearchResponse(BaseModel):
    total_count: int
    items: list[GoodsItemResponse] = Field(default_factory=list)


class OwnedItemSourceReplaceChoice(BaseModel):
    owned_item_id: int = Field(ge=1)
    candidate: MetadataCandidate


class OwnedItemSourceReplaceBulkRequest(BaseModel):
    items: list[OwnedItemSourceReplaceChoice] = Field(default_factory=list)


class OwnedItemSourceReplaceResult(BaseModel):
    owned_item_id: int
    label_id: str | None = None
    updated: bool = False
    source_code: ExternalSourceCode | None = None
    source_external_id: str | None = None
    linked_album_master_id: int | None = None
    notices: list[str] = Field(default_factory=list)
    error: str | None = None


class OwnedItemSourceReplaceBulkResponse(BaseModel):
    requested_count: int
    updated_count: int
    failed_count: int
    results: list[OwnedItemSourceReplaceResult] = Field(default_factory=list)


class OwnedItemBulkUpdateRequest(BaseModel):
    owned_item_ids: list[int] = Field(default_factory=list)
    status: ItemStatus | None = None
    domain_code: DomainCode | None = None
    release_type: ReleaseType | None = None
    is_second_hand: bool | None = None
    purchase_source: str | None = None
    append_memory_note: str | None = None
    preferred_storage_size_group: SizeGroup | None = None


class OwnedItemBulkUpdateResponse(BaseModel):
    requested_count: int
    updated_count: int
    updated_item_ids: list[int] = Field(default_factory=list)


class OperatorCatalogSearchItem(BaseModel):
    owned_item_id: int
    label_id: str
    category: ItemCategory
    format_name: str | None = None
    item_title: str | None = None
    artist_or_brand: str | None = None
    released_date: str | None = None
    pressing_country: str | None = None
    label_name: str | None = None
    catalog_no: str | None = None
    barcode: str | None = None
    format_items: list[dict[str, Any]] = Field(default_factory=list)
    runout_sample: str | None = None
    cover_image_url: str | None = None
    signature_type: SignatureType
    status: ItemStatus
    current_slot_code: str | None = None
    current_slot_display_name: str | None = None
    current_cabinet_name: str | None = None
    current_column_code: str | None = None
    current_cell_code: str | None = None
    previous_slot_code: str | None = None
    previous_slot_display_name: str | None = None
    created_at: str | None = None
    track_matches: list[str] = Field(default_factory=list)
    matched_track_count: int = 0
    track_items: list[dict[str, Any]] = Field(default_factory=list)
    track_list: list[str] = Field(default_factory=list)
    # 도메인 정보 (수정 UI 지원)
    album_master_id: int | None = None         # album_master.id (도메인 수정 API 호출용)
    effective_domain_code: str | None = None   # 실제 표시 도메인 (item 우선, 없으면 master)
    master_domain_code: str | None = None      # album_master.domain_code (자동 추정값)
    override_domain_code: str | None = None    # 수동 확정 여부 (not null → 확정)
    sort_artist_name: str | None = None        # album_master.sort_artist_name (교정 UI 표시)


class OperatorCatalogSearchResponse(BaseModel):
    query: str
    total_count: int
    items: list[OperatorCatalogSearchItem] = Field(default_factory=list)


class ArtistContextRequest(BaseModel):
    artist_name: str = Field(min_length=1, max_length=4000)
    category: str | None = None
    locale: str | None = Field(default=None, max_length=16)


class ArtistContextLink(BaseModel):
    label: str
    url: str


class ArtistContextResponse(BaseModel):
    available: bool = False
    artist_name: str
    summary: str | None = None
    summary_original: str | None = None
    image_url: str | None = None
    country: str | None = None
    active_years: str | None = None
    genres: list[str] = Field(default_factory=list)
    styles: list[str] = Field(default_factory=list)
    links: list[ArtistContextLink] = Field(default_factory=list)


class OpsHomeRecentItem(BaseModel):
    owned_item_id: int
    label_id: str
    category: ItemCategory
    format_name: str | None = None
    format_items: list[dict[str, Any]] = Field(default_factory=list)
    item_title: str | None = None
    artist_or_brand: str | None = None
    released_date: str | None = None
    pressing_country: str | None = None
    label_name: str | None = None
    catalog_no: str | None = None
    barcode: str | None = None
    runout_sample: str | None = None
    cover_image_url: str | None = None
    current_slot_code: str | None = None
    current_slot_display_name: str | None = None
    current_cabinet_name: str | None = None
    current_column_code: str | None = None
    current_cell_code: str | None = None
    previous_slot_code: str | None = None
    previous_slot_display_name: str | None = None
    created_at: str
    acquisition_date: str | None = None


class OpsHomeRecentSectionsResponse(BaseModel):
    recent_moved_items: list[OpsHomeRecentItem] = Field(default_factory=list)
    recent_registered_items: list[OpsHomeRecentItem] = Field(default_factory=list)
    recent_moved_total_count: int = 0
    recent_registered_total_count: int = 0


class OpsHomeFeedResponse(BaseModel):
    kind: str
    page: int
    limit: int
    total_count: int = 0
    items: list[OpsHomeRecentItem] = Field(default_factory=list)


class OfficeClimateResponse(BaseModel):
    available: bool = False
    source: str = "home_assistant"
    location_label: str = "상주 사무실"
    description: str = ""
    temperature_c: float | None = None
    humidity_percent: float | None = None
    comfort_label: str | None = None
    temperature_high_c: float | None = None
    temperature_low_c: float | None = None
    weather_code: int | None = None
    is_day: bool | None = None
    updated_at: str | None = None


class CustomerTrackRequestCreate(BaseModel):
    requested_track: str = Field(min_length=1, max_length=300)
    owned_item_id: int | None = Field(default=None, ge=1)
    matched_track_title: str | None = None
    matched_track_no: int | None = Field(default=None, ge=1)
    customer_note: str | None = None


class CustomerTrackRequestUpdate(BaseModel):
    status: CustomerTrackRequestStatus | None = None
    response_note: str | None = None
    playback_deck: str | None = None


class CustomerTrackRequestItem(BaseModel):
    id: int
    requested_track: str
    matched_track_title: str | None = None
    matched_track_no: int | None = None
    owned_item_id: int | None = None
    label_id: str | None = None
    category: ItemCategory | None = None
    item_title: str | None = None
    artist_or_brand: str | None = None
    cover_image_url: str | None = None
    status: CustomerTrackRequestStatus
    customer_note: str | None = None
    response_note: str | None = None
    requested_by: str | None = None
    handled_by: str | None = None
    created_at: str
    updated_at: str
    handled_at: str | None = None
    current_slot_code_snapshot: str | None = None
    current_slot_display_snapshot: str | None = None
    previous_slot_code_snapshot: str | None = None
    previous_slot_display_snapshot: str | None = None
    current_live_slot_code: str | None = None
    current_live_slot_display_name: str | None = None
    weather_temp_c: float | None = None
    weather_description: str | None = None
    weather_code: int | None = None
    season: str | None = None
    playback_deck: str | None = None
    played_at: str | None = None
    returned_at: str | None = None


class CustomerTrackRequestListResponse(BaseModel):
    total_count: int
    items: list[CustomerTrackRequestItem] = Field(default_factory=list)


class RoonStatusResponse(BaseModel):
    connected: bool
    core_name: str
    active_zone: str
    volume: int
    now_playing_request_id: int | None = None


class AuthAccountItem(BaseModel):
    username: str
    role: AuthRole
    source: Literal["SYSTEM", "MANAGED"]
    is_active: bool = True
    editable: bool = False
    created_at: str | None = None
    updated_at: str | None = None


class AuthAccountCreateRequest(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=4, max_length=200)
    role: AuthRole = "OPERATOR"


class AuthAccountUpdateRequest(BaseModel):
    password: str | None = Field(default=None, min_length=4, max_length=200)
    role: AuthRole | None = None
    is_active: bool | None = None


class AuthAccountListResponse(BaseModel):
    total_count: int
    items: list[AuthAccountItem] = Field(default_factory=list)


class PurchaseImportPreviewRequest(BaseModel):
    raw_content: str | None = None
    raw_content_base64: str | None = None
    source_filename: str | None = None
    vendor_code: PurchaseImportVendor = "OTHER"
    email_from: str | None = None
    email_subject: str | None = None
    purchase_date: str | None = None


class PurchaseImportPreviewItem(BaseModel):
    row_no: int = Field(ge=1)
    artist_name: str | None = None
    item_name: str = Field(min_length=1, max_length=400)
    media_format: str | None = None
    quantity: int = Field(default=1, ge=1)
    unit_price: float | None = None
    line_total: float | None = None
    currency_code: str | None = Field(default="KRW", min_length=3, max_length=3)
    purchase_date: str | None = None
    raw_line: str | None = None
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class PurchaseImportPreviewResponse(BaseModel):
    vendor_code: PurchaseImportVendor
    total_count: int
    items: list[PurchaseImportPreviewItem] = Field(default_factory=list)


class PurchaseImportSaveRequest(BaseModel):
    vendor_code: PurchaseImportVendor = "OTHER"
    source_type: PurchaseImportSourceType = "EMAIL_HTML"
    source_ref: str | None = None
    email_from: str | None = None
    email_subject: str | None = None
    purchase_date: str | None = None
    items: list[PurchaseImportPreviewItem] = Field(default_factory=list)


class PurchaseImportSaveResponse(BaseModel):
    created_count: int
    created_ids: list[int] = Field(default_factory=list)


class PurchaseImportWebhookRequest(BaseModel):
    raw_content: str = Field(min_length=1)
    vendor_code: PurchaseImportVendor = "OTHER"
    source_type: PurchaseImportSourceType = "EMAIL_HTML"
    source_ref: str | None = None
    email_from: str | None = None
    email_subject: str | None = None
    purchase_date: str | None = None


class PurchaseImportQueueItem(BaseModel):
    id: int
    vendor_code: PurchaseImportVendor
    source_type: PurchaseImportSourceType
    source_ref: str | None = None
    email_from: str | None = None
    email_subject: str | None = None
    artist_name: str | None = None
    item_name: str
    media_format: str | None = None
    quantity: int
    unit_price: float | None = None
    line_total: float | None = None
    currency_code: str | None = None
    purchase_date: str | None = None
    seller_name: str | None = None
    item_url: str | None = None
    image_url: str | None = None
    raw_line: str | None = None
    raw_payload: dict[str, Any] = Field(default_factory=dict)
    queue_status: PurchaseImportStatus
    linked_owned_item_id: int | None = None
    created_at: str
    updated_at: str


class PurchaseImportListResponse(BaseModel):
    total_count: int
    items: list[PurchaseImportQueueItem] = Field(default_factory=list)


class PurchaseImportCandidateSearchResponse(BaseModel):
    queue_item: PurchaseImportQueueItem
    query: str
    candidates: list[MetadataCandidate] = Field(default_factory=list)


class PurchaseImportCandidateCreateRequest(BaseModel):
    candidate: MetadataCandidate


class PurchaseImportCreateResponse(BaseModel):
    queue_item: PurchaseImportQueueItem
    owned_item_id: int
    label_id: str
    linked_album_master_id: int | None = None
    notices: list[str] = Field(default_factory=list)


class AlbumMasterSearchRequest(BaseModel):
    source: AlbumMasterSource = "AUTO"
    query: str = Field(min_length=1, max_length=200)
    artist_or_brand: str | None = None
    title: str | None = None
    limit: int = Field(default=10, ge=1, le=50)


class AlbumMasterCandidate(BaseModel):
    source: AlbumMasterBoundSource
    master_external_id: str
    title: str
    artist_or_brand: str | None = None
    release_year: int | None = None
    label_name: str | None = None
    catalog_no: str | None = None
    barcode: str | None = None
    cover_image_url: str | None = None
    variant_count: int | None = None
    confidence: float = 0.0
    raw: dict[str, Any] = Field(default_factory=dict)


class AlbumMasterSearchResponse(BaseModel):
    query: str
    candidates: list[AlbumMasterCandidate]


class AlbumMasterVariantItem(BaseModel):
    source: AlbumMasterBoundSource
    external_id: str
    title: str
    artist_or_brand: str | None = None
    release_year: int | None = None
    released_date: str | None = None
    country: str | None = None
    format_name: str | None = None
    media_type: str | None = None
    release_type: ReleaseType | None = None
    domain_code: DomainCode | None = None
    genres: list[str] = Field(default_factory=list)
    styles: list[str] = Field(default_factory=list)
    styles: list[str] = Field(default_factory=list)
    label_name: str | None = None
    catalog_no: str | None = None
    barcode: str | None = None
    cover_image_url: str | None = None
    track_list: list[str] = Field(default_factory=list)
    disc_count: int | None = None
    speed_rpm: int | None = None
    disc_type: str | None = None
    has_obi: bool | None = None
    runout_matrix: list[str] = Field(default_factory=list)
    pressing_country: str | None = None
    source_notes: str | None = None
    credits: list[str] = Field(default_factory=list)
    identifier_items: list[dict[str, Any]] = Field(default_factory=list)
    image_items: list[dict[str, Any]] = Field(default_factory=list)
    company_items: list[dict[str, Any]] = Field(default_factory=list)
    series: list[str] = Field(default_factory=list)
    format_items: list[dict[str, Any]] = Field(default_factory=list)
    track_items: list[dict[str, Any]] = Field(default_factory=list)
    label_items: list[dict[str, Any]] = Field(default_factory=list)
    is_owned: bool = False
    owned_count: int = 0
    raw: dict[str, Any] = Field(default_factory=dict)


class AlbumMasterVariantsResponse(BaseModel):
    source: AlbumMasterBoundSource
    master_external_id: str
    items: list[AlbumMasterVariantItem]
    page: int = 1
    page_size: int = 30
    total_count: int | None = None
    has_next: bool = False
    filtered: bool = False
    filter_catalog_no: str | None = None
    filter_barcode: str | None = None
    truncated: bool = False


class AlbumMasterBindRequest(BaseModel):
    source: AlbumMasterBoundSource
    master_external_id: str = Field(min_length=1, max_length=128)
    title: str = Field(min_length=1, max_length=400)
    artist_or_brand: str | None = None
    release_year: int | None = Field(default=None, ge=1900, le=2100)
    raw: dict[str, Any] = Field(default_factory=dict)
    owned_item_ids: list[int] = Field(default_factory=list)
    replace_existing: bool = True


class AlbumMasterBindResponse(BaseModel):
    album_master_id: int
    linked_count: int


class AlbumMasterDeleteResponse(BaseModel):
    album_master_id: int
    deleted: bool
    cascade_items: bool = False
    removed_member_links: int = 0
    deleted_owned_item_count: int = 0


class AlbumMasterDuplicateItem(BaseModel):
    album_master_id: int
    source_code: AlbumMasterBoundSource
    source_master_id: str
    title: str
    artist_or_brand: str | None = None
    release_year: int | None = None
    member_count: int = 0
    updated_at: str | None = None


class AlbumMasterDuplicateCheckResponse(BaseModel):
    album_master_id: int
    duplicate_count: int
    suggested_target_album_master_id: int | None = None
    duplicates: list[AlbumMasterDuplicateItem] = Field(default_factory=list)


class AlbumMasterMergeRequest(BaseModel):
    target_album_master_id: int = Field(ge=1)


class AlbumMasterMergeResponse(BaseModel):
    source_album_master_id: int
    target_album_master_id: int
    moved_member_count: int = 0
    target_member_count: int = 0
    merge_history_id: int | None = None
    merged: bool = True


class AlbumMasterMergeHistoryItem(BaseModel):
    id: int
    source_album_master_id: int
    target_album_master_id: int
    source_code: str | None = None
    source_master_id: str | None = None
    source_title: str | None = None
    source_artist_or_brand: str | None = None
    target_title: str | None = None
    target_artist_or_brand: str | None = None
    moved_member_count: int = 0
    target_member_count: int = 0
    source_owned_item_ids: list[int] = Field(default_factory=list)
    overlap_owned_item_ids: list[int] = Field(default_factory=list)
    merged_by: str | None = None
    created_at: str | None = None
    rolled_back_at: str | None = None
    rolled_back_by: str | None = None
    rollback_available: bool = False
    rollback_blocked_reason: str | None = None


class AlbumMasterMergeRollbackResponse(BaseModel):
    merge_history_id: int
    source_album_master_id: int
    target_album_master_id: int
    restored_member_count: int = 0
    rolled_back: bool = True


class OwnedItemAutoMasterResponse(BaseModel):
    owned_item_id: int
    album_master_id: int
    source_code: AlbumMasterBoundSource
    source_master_id: str
    title: str
    linked_count: int
    notices: list[str] = Field(default_factory=list)


class AlbumMasterImportVariantsRequest(BaseModel):
    source: Literal["DISCOGS", "MANIADB"]
    master_external_id: str = Field(min_length=1, max_length=128)
    title: str | None = None
    artist_or_brand: str | None = None
    release_year: int | None = Field(default=None, ge=1900, le=2100)
    raw: dict[str, Any] = Field(default_factory=dict)
    linked_album_master_id: int | None = None
    selected_variant_external_ids: list[str] = Field(default_factory=list)
    quantity: int = Field(default=1, ge=1)
    is_second_hand: bool = True
    domain_code: DomainCode | None = None
    release_type: ReleaseType | None = None
    purchase_source: str | None = None
    memory_note: str | None = None
    local_image_items: list[dict[str, Any]] = Field(default_factory=list)
    subtype_option_ids: list[int] = Field(default_factory=list)
    soundtrack_option_ids: list[int] = Field(default_factory=list)
    skip_if_owned: bool = True


class AlbumMasterImportCreatedItem(BaseModel):
    external_id: str
    owned_item_id: int
    label_id: str
    category: ItemCategory
    format_name: str | None = None
    title: str


class AlbumMasterImportSkippedItem(BaseModel):
    external_id: str
    reason: str
    owned_count: int = 0


class AlbumMasterImportVariantsResponse(BaseModel):
    album_master_id: int
    source: AlbumMasterBoundSource
    master_external_id: str
    created_count: int
    skipped_count: int
    linked_count: int
    created_items: list[AlbumMasterImportCreatedItem] = Field(default_factory=list)
    skipped_items: list[AlbumMasterImportSkippedItem] = Field(default_factory=list)
    notices: list[str] = Field(default_factory=list)

class AlbumMasterLocationAction(BaseModel):
    owned_item_id: int
    storage_slot_id: int | None = None
    slot_code: str | None = None
    cabinet_name: str | None = None
    column_code: str | None = None
    cell_code: str | None = None
    location_display_name: str
    item_label: str | None = None


class AlbumMasterMemberPreviewItem(BaseModel):
    owned_item_id: int
    storage_slot_id: int | None = None
    label_id: str | None = None
    source_code: str | None = None
    source_external_id: str | None = None
    item_title: str | None = None
    artist_or_brand: str | None = None
    cover_image_url: str | None = None
    created_at: str | None = None
    released_date: str | None = None
    master_release_year: int | None = None
    pressing_country: str | None = None
    label_name: str | None = None
    catalog_no: str | None = None
    barcode: str | None = None
    format_name: str | None = None
    format_items: list[dict[str, Any]] = Field(default_factory=list)
    runout_sample: str | None = None
    current_slot_display_name: str | None = None
    current_slot_code: str | None = None
    current_cabinet_name: str | None = None
    current_column_code: str | None = None
    current_cell_code: str | None = None


class AlbumMasterListItem(BaseModel):
    id: int
    source_code: AlbumMasterBoundSource
    source_master_id: str
    title: str
    artist_or_brand: str | None = None
    sort_artist_name: str | None = None
    domain_code: DomainCode | None = None
    release_year: int | None = None
    member_count: int
    cover_image_url: str | None = None
    has_audio: bool = False
    audio_asset_count: int = 0
    member_preview: list[str] = Field(default_factory=list)
    member_items_preview: list[AlbumMasterMemberPreviewItem] = Field(default_factory=list)
    member_location_preview: list[str] = Field(default_factory=list)
    member_location_actions: list[AlbumMasterLocationAction] = Field(default_factory=list)
    first_member_storage_slot_id: int | None = None
    first_member_slot_code: str | None = None
    first_member_cabinet_name: str | None = None
    first_member_column_code: str | None = None
    first_member_cell_code: str | None = None
    matched_track_preview: list[str] = Field(default_factory=list)
    genres: list[str] = Field(default_factory=list)
    styles: list[str] = Field(default_factory=list)
    spotify_album_id: str | None = None
    spotify_album_uri: str | None = None
    spotify_matched_at: str | None = None
    spotify_image_url: str | None = None
    updated_at: str


class AlbumMasterMemberItem(BaseModel):
    owned_item_id: int
    category: ItemCategory
    item_name_override: str | None = None
    quantity: int
    status: ItemStatus
    format_name: str | None = None


class CsvIngestResponse(BaseModel):
    batch_id: int
    total_count: int
    matched_count: int
    review_count: int
    failed_count: int


class MusicDetailCreate(BaseModel):
    format_name: str | None = None
    is_promotional_not_for_sale: bool = False
    artist_or_brand: str | None = None
    release_year: int | None = Field(default=None, ge=1900, le=2100)
    released_date: str | None = None
    barcode: str | None = None
    label_name: str | None = None
    catalog_no: str | None = None
    cover_image_url: str | None = None
    track_list: list[str] = Field(default_factory=list)
    media_type: str | None = None
    genres: list[str] = Field(default_factory=list)
    styles: list[str] = Field(default_factory=list)
    styles: list[str] = Field(default_factory=list)
    cover_condition: str | None = None
    disc_condition: str | None = None
    media_condition: str | None = None
    sleeve_condition: str | None = None
    disc_count: int | None = Field(default=None, ge=1)
    speed_rpm: int | None = None
    disc_type: str | None = None
    package_contents: str | None = None
    is_limited_edition: bool | None = None
    edition_number: str | None = None
    has_obi: bool | None = None
    runout_matrix: list[str] = Field(default_factory=list)
    pressing_country: str | None = None
    source_notes: str | None = None
    credits: list[str] = Field(default_factory=list)
    identifier_items: list[dict[str, Any]] = Field(default_factory=list)
    image_items: list[dict[str, Any]] = Field(default_factory=list)
    company_items: list[dict[str, Any]] = Field(default_factory=list)
    series: list[str] = Field(default_factory=list)
    format_items: list[dict[str, Any]] = Field(default_factory=list)
    track_items: list[dict[str, Any]] = Field(default_factory=list)
    label_items: list[dict[str, Any]] = Field(default_factory=list)

    @field_validator("disc_count", mode="before")
    @classmethod
    def _normalize_disc_count(cls, value: Any) -> Any:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        try:
            parsed = int(text)
        except (TypeError, ValueError):
            return value
        return parsed if parsed > 0 else None


class GoodsDetailCreate(BaseModel):
    image_urls: list[str] = Field(default_factory=list)
    primary_image_url: str | None = None
    poster_storage_spec: str | None = None
    tshirt_size: str | None = None
    cup_material: str | None = None
    hat_size: str | None = None


class OwnedItemRelationItem(BaseModel):
    relation_type: str
    target_kind: str
    target_ref: str
    display_order: int | None = None
    note: str | None = None


class OwnedItemRelationSaveRequest(BaseModel):
    relations: list[OwnedItemRelationItem] = Field(default_factory=list)


class OwnedItemCreate(BaseModel):
    category: ItemCategory
    size_group: SizeGroup
    preferred_storage_size_group: SizeGroup | None = None
    auto_location_recommendation: bool = True
    quantity: int = Field(default=1, ge=1)
    is_second_hand: bool = True
    status: ItemStatus = "IN_COLLECTION"
    signature_type: SignatureType = "NONE"
    source_code: ExternalSourceCode | None = None
    source_external_id: str | None = None
    domain_code: DomainCode | None = None
    release_type: ReleaseType | None = None

    master_item_id: int | None = None
    linked_album_master_id: int | None = None
    linked_artist_name: str | None = None
    copy_group_key: str | None = None
    item_name_override: str | None = None
    condition_grade: str | None = None
    signed_by: str | None = None
    signed_at: str | None = None
    acquisition_date: str | None = None
    purchase_price: float | None = None
    currency_code: str | None = Field(default=None, min_length=3, max_length=3)
    purchase_source: str | None = None
    memory_note: str | None = None
    display_rank: int | None = None
    storage_slot_id: int | None = None
    thickness_mm: int | None = Field(default=None, ge=0)
    notes: str | None = None
    local_image_items: list[dict[str, Any]] = Field(default_factory=list)
    subtype_option_ids: list[int] = Field(default_factory=list)
    soundtrack_option_ids: list[int] = Field(default_factory=list)

    music_detail: MusicDetailCreate | None = None
    goods_detail: GoodsDetailCreate | None = None


class OwnedItemCreateResponse(BaseModel):
    owned_item_id: int
    label_id: str
    linked_album_master_id: int | None = None
    notices: list[str] = Field(default_factory=list)


class OwnedItemListItem(BaseModel):
    id: int
    label_id: str
    category: ItemCategory
    size_group: SizeGroup
    preferred_storage_size_group: SizeGroup
    item_name_override: str | None = None
    quantity: int
    status: ItemStatus
    display_rank: int | None = None
    order_key: str | None = None
    storage_slot_id: int | None = None
    slot_code: str | None = None
    is_second_hand: bool
    signature_type: SignatureType
    source_code: ExternalSourceCode | None = None
    source_external_id: str | None = None
    linked_album_master_id: int | None = None
    linked_artist_name: str | None = None
    copy_group_key: str | None = None
    domain_code: DomainCode | None = None
    release_type: ReleaseType | None = None
    purchase_price: float | None = None
    currency_code: str | None = None
    purchase_source: str | None = None
    memory_note: str | None = None
    created_at: str
    format_name: str | None = None
    artist_or_brand: str | None = None
    release_year: int | None = None
    released_date: str | None = None
    master_title: str | None = None
    master_artist_or_brand: str | None = None
    master_sort_artist_name: str | None = None
    master_release_year: int | None = None
    barcode: str | None = None
    label_name: str | None = None
    catalog_no: str | None = None
    cover_image_url: str | None = None
    goods_primary_image_url: str | None = None
    track_list: list[str] = Field(default_factory=list)
    genres: list[str] = Field(default_factory=list)
    styles: list[str] = Field(default_factory=list)
    cover_condition: str | None = None
    disc_condition: str | None = None
    is_promotional_not_for_sale: bool | None = None
    has_audio: bool = False
    audio_asset_count: int = 0
    local_image_items: list[dict[str, Any]] = Field(default_factory=list)
    subtype_option_ids: list[int] = Field(default_factory=list)
    subtype_labels: list[str] = Field(default_factory=list)
    soundtrack_option_ids: list[int] = Field(default_factory=list)
    soundtrack_labels: list[str] = Field(default_factory=list)
    previous_slot_code: str | None = None
    previous_slot_display_name: str | None = None
    last_slot_event_at: str | None = None
    recently_moved_to_current_slot: bool = False


class CollectionCategoryCount(BaseModel):
    category: ItemCategory
    count: int


class CollectionStatusCount(BaseModel):
    status: ItemStatus
    count: int


class CollectionValueCount(BaseModel):
    value: str
    count: int


class CollectionSlotCount(BaseModel):
    slot_code: str
    cabinet_name: str | None = None
    cabinet_domain_code: DomainCode | None = None
    cabinet_group_name: str | None = None
    cabinet_group_order: int | None = None
    column_code: str | None = None
    cell_code: str | None = None
    display_name: str | None = None
    allowed_size_group: str | None = None
    is_overflow_zone: bool = False
    count: int
    recent_in_count: int = 0
    recent_out_count: int = 0
    capacity_mm: int = 0
    used_thickness_mm: int = 0
    free_thickness_mm: int = 0
    occupancy_ratio: float = 0.0
    occupancy_percent: int = 0
    first_item_artist_or_brand: str | None = None
    first_item_title: str | None = None
    first_item_release_year: int | None = None


class CollectionMovementItem(BaseModel):
    id: int
    owned_item_id: int
    label_id: str
    category: ItemCategory
    item_title: str | None = None
    artist_or_brand: str | None = None
    cover_image_url: str | None = None
    movement_kind: Literal["INITIAL_ASSIGN", "ASSIGN", "MOVE", "UNASSIGN", "CABINET_DELETE"]
    from_slot_code: str | None = None
    from_display_name: str | None = None
    to_slot_code: str | None = None
    to_display_name: str | None = None
    note: str | None = None
    created_at: str


class CollectionDomainCategoryCount(BaseModel):
    domain: str
    category: str
    count: int


class CollectionSourceDomainCount(BaseModel):
    source: str
    domain: str
    count: int


class CollectionSourceCategoryCount(BaseModel):
    source: str
    category: str
    count: int

class CollectionArtistCount(BaseModel):
    artist: str
    count: int


class CollectionLabelCount(BaseModel):
    label: str
    count: int


class CollectionGenreCount(BaseModel):
    genre: str
    count: int


class CollectionDecadeCount(BaseModel):
    decade: int
    count: int


class CollectionMonthCount(BaseModel):
    month: str
    count: int


class CollectionCurrencySpend(BaseModel):
    currency_code: str
    items: int
    total_spend: int


class CollectionDomainSpend(BaseModel):
    domain: str
    items: int
    avg_price: int
    total_spend: int


class CollectionMonthSpend(BaseModel):
    month: str
    items: int
    total_spend: int


class CollectionMediaConditionCount(BaseModel):
    condition: str
    count: int


class CollectionSyncSourceCount(BaseModel):
    source_code: str
    count: int

class CollectionDomainDecadeCount(BaseModel):
    domain: str
    decade: int
    count: int


class CollectionGenreDomainCount(BaseModel):
    domain: str
    genre: str
    count: int


class CollectionFormatDomainCount(BaseModel):
    format: str
    domain: str
    count: int


class CollectionPressingDomainCount(BaseModel):
    pressing_country: str
    domain: str
    count: int


class CollectionArtistDecadeSpan(BaseModel):
    artist: str
    min_decade: int
    max_decade: int
    total: int


class CollectionLabelCountryCount(BaseModel):
    label: str
    pressing_country: str
    count: int


class CollectionSourceCompleteness(BaseModel):
    source: str
    total: int
    master_linked: int
    cover_present: int
    genre_present: int
    catalog_present: int
    format_present: int


class CollectionSignDomainCount(BaseModel):
    domain: str
    signature_type: str
    count: int

class CollectionSlotMoveCount(BaseModel):
    slot_code: str
    movement_kind: str
    count: int


class CollectionPurchaseFlowItem(BaseModel):
    source: str
    currency: str
    domain: str
    items: int
    total_spend: int


class CollectionDashboardResponse(BaseModel):
    total_items: int
    in_collection_items: int
    music_items: int
    goods_items: int
    signed_items: int
    direct_signed_items: int = 0
    purchase_signed_items: int = 0
    second_hand_items: int
    audio_mapped_items: int
    registered_last_30_days: int
    registered_last_7_days: int = 0
    registered_today: int = 0
    slotted_in_collection_items: int
    unslotted_in_collection_items: int
    source_unlinked_items: int
    master_unlinked_items: int
    cover_missing_items: int
    loaned_items: int = 0
    sold_items: int = 0
    lost_items: int = 0
    genre_missing_items: int = 0
    media_missing_items: int = 0
    catalog_missing_items: int = 0
    limited_items: int = 0
    new_items: int = 0
    promo_items: int = 0
    other_condition_items: int = 0
    multi_disc_items: int = 0
    obi_items: int = 0
    import_queue_size: int = 0
    by_artist: list[CollectionArtistCount] = Field(default_factory=list)
    by_label: list[CollectionLabelCount] = Field(default_factory=list)
    by_genre: list[CollectionGenreCount] = Field(default_factory=list)
    by_release_decade: list[CollectionDecadeCount] = Field(default_factory=list)
    by_registration_month: list[CollectionMonthCount] = Field(default_factory=list)
    by_currency_spend: list[CollectionCurrencySpend] = Field(default_factory=list)
    by_domain_spend: list[CollectionDomainSpend] = Field(default_factory=list)
    by_month_spend: list[CollectionMonthSpend] = Field(default_factory=list)
    by_media_condition: list[CollectionMediaConditionCount] = Field(default_factory=list)
    sync_sources: list[CollectionSyncSourceCount] = Field(default_factory=list)
    by_domain_decade: list[CollectionDomainDecadeCount] = Field(default_factory=list)
    by_genre_domain: list[CollectionGenreDomainCount] = Field(default_factory=list)
    by_format_domain: list[CollectionFormatDomainCount] = Field(default_factory=list)
    by_pressing_domain: list[CollectionPressingDomainCount] = Field(default_factory=list)
    by_artist_decade: list[CollectionArtistDecadeSpan] = Field(default_factory=list)
    by_label_country: list[CollectionLabelCountryCount] = Field(default_factory=list)
    by_source_completeness: list[CollectionSourceCompleteness] = Field(default_factory=list)
    by_sign_domain: list[CollectionSignDomainCount] = Field(default_factory=list)
    by_slot_moves: list[CollectionSlotMoveCount] = Field(default_factory=list)
    by_recent_reg_domain_decade: list[CollectionDomainDecadeCount] = Field(default_factory=list)
    by_recent_reg_domain: list[CollectionValueCount] = Field(default_factory=list)
    by_purchase_flow: list[CollectionPurchaseFlowItem] = Field(default_factory=list)
    by_pressing_country: list[CollectionValueCount] = Field(default_factory=list)
    by_category: list[CollectionCategoryCount] = Field(default_factory=list)
    by_status: list[CollectionStatusCount] = Field(default_factory=list)
    by_domain: list[CollectionValueCount] = Field(default_factory=list)
    by_domain_category: list[CollectionDomainCategoryCount] = Field(default_factory=list)
    by_release_type: list[CollectionValueCount] = Field(default_factory=list)
    by_size_group: list[CollectionValueCount] = Field(default_factory=list)
    by_source: list[CollectionValueCount] = Field(default_factory=list)
    by_source_domain: list[CollectionSourceDomainCount] = Field(default_factory=list)
    by_source_category: list[CollectionSourceCategoryCount] = Field(default_factory=list)
    movement_window_days: int = 1
    recent_move_total: int = 0
    recent_moves: list[CollectionMovementItem] = Field(default_factory=list)
    by_slot: list[CollectionSlotCount] = Field(default_factory=list)


class SlotUpdateRequest(BaseModel):
    storage_slot_id: int | None = None


class SlotUpdateResponse(BaseModel):
    owned_item_id: int
    storage_slot_id: int | None = None


class OwnedItemLocationRecommendationRequest(BaseModel):
    owned_item_ids: list[int] = Field(default_factory=list)


class OwnedItemLocationRecommendationCandidateSlot(BaseModel):
    storage_slot_id: int | None = None
    slot_code: str | None = None
    display_name: str | None = None
    cabinet_name: str | None = None
    column_code: str | None = None
    cell_code: str | None = None


class OwnedItemLocationRecommendationItem(BaseModel):
    owned_item_id: int
    recommended_storage_slot_id: int | None = None
    slot_code: str | None = None
    display_name: str | None = None
    cabinet_name: str | None = None
    column_code: str | None = None
    cell_code: str | None = None
    candidate_slots: list[OwnedItemLocationRecommendationCandidateSlot] = Field(default_factory=list)
    anchor_owned_item_id: int | None = None
    anchor_position: Literal["BEFORE", "AFTER"] | None = None
    used_fallback_slot: bool = False
    reason: str | None = None


class OrderMoveRequest(BaseModel):
    target_owned_item_id: int = Field(ge=1)
    position: Literal["BEFORE", "AFTER"]


class OrderMoveResponse(BaseModel):
    owned_item_id: int
    target_owned_item_id: int
    position: Literal["BEFORE", "AFTER"]
    order_key: str


class SlotOrderMoveResponse(BaseModel):
    storage_slot_id: int
    owned_item_id: int
    target_owned_item_id: int
    position: Literal["BEFORE", "AFTER"]
    display_rank: int


class OwnedAlbumShelfWindowResponse(BaseModel):
    center_owned_item_id: int
    previous_owned_item_id: int | None = None
    next_owned_item_id: int | None = None
    items: list[OwnedItemListItem]


class RelatedAlbumVersionsResponse(BaseModel):
    owned_item_id: int
    relation_type: Literal["ALBUM_MASTER_BIND", "SOURCE_MASTER", "NONE"]
    source: AlbumMasterBoundSource | None = None
    master_external_id: str | None = None
    album_master_id: int | None = None
    title: str | None = None
    artist_or_brand: str | None = None
    sort_artist_name: str | None = None
    release_year: int | None = None
    domain_code: DomainCode | None = None
    source_release_year: int | None = None
    source_domain_code: DomainCode | None = None
    override_release_year: int | None = None
    override_domain_code: DomainCode | None = None
    override_note: str | None = None
    has_manual_correction: bool = False
    items: list[OwnedItemListItem] = Field(default_factory=list)


class AlbumMasterSortArtistUpdateRequest(BaseModel):
    sort_artist_name: str | None = None


class AlbumMasterSortArtistUpdateResponse(BaseModel):
    album_master_id: int
    sort_artist_name: str | None = None


class AlbumMasterCorrectionUpdateRequest(BaseModel):
    release_year: int | None = Field(default=None, ge=1900, le=2100)
    domain_code: DomainCode | None = None
    override_note: str | None = None
    override_title: str | None = None
    override_artist_or_brand: str | None = None


class AlbumMasterCorrectionUpdateResponse(BaseModel):
    album_master_id: int
    release_year: int | None = None
    domain_code: DomainCode | None = None
    source_release_year: int | None = None
    source_domain_code: DomainCode | None = None
    override_release_year: int | None = None
    override_domain_code: DomainCode | None = None
    override_note: str | None = None
    override_title: str | None = None
    override_artist_or_brand: str | None = None
    has_manual_correction: bool = False


class OwnedItemDetailResponse(BaseModel):
    id: int
    label_id: str
    master_item_id: int | None = None
    category: ItemCategory
    item_name_override: str | None = None
    quantity: int
    is_second_hand: bool
    size_group: SizeGroup
    preferred_storage_size_group: SizeGroup
    status: ItemStatus
    condition_grade: str | None = None
    signature_type: SignatureType
    source_code: ExternalSourceCode | None = None
    source_external_id: str | None = None
    linked_album_master_id: int | None = None
    linked_artist_name: str | None = None
    copy_group_key: str | None = None
    domain_code: DomainCode | None = None
    release_type: ReleaseType | None = None
    purchase_price: float | None = None
    currency_code: str | None = None
    purchase_source: str | None = None
    memory_note: str | None = None
    display_rank: int | None = None
    order_key: str | None = None
    storage_slot_id: int | None = None
    slot_code: str | None = None
    thickness_mm: int | None = None
    notes: str | None = None
    created_at: str
    updated_at: str | None = None
    music_detail: MusicDetailCreate | None = None
    goods_detail: GoodsDetailCreate | None = None
    has_audio: bool = False
    audio_asset_count: int = 0
    local_image_items: list[dict[str, Any]] = Field(default_factory=list)
    subtype_option_ids: list[int] = Field(default_factory=list)
    subtype_labels: list[str] = Field(default_factory=list)
    soundtrack_option_ids: list[int] = Field(default_factory=list)
    soundtrack_labels: list[str] = Field(default_factory=list)


class ClassificationOptionItem(BaseModel):
    id: int
    option_group: ClassificationOptionGroup
    label: str
    sort_order: int
    is_active: bool


class ClassificationOptionCreate(BaseModel):
    option_group: ClassificationOptionGroup
    label: str = Field(min_length=1, max_length=120)
    sort_order: int = 100


class OwnedItemDeleteResponse(BaseModel):
    owned_item_id: int
    deleted: bool


class OwnedItemDuplicateRequest(BaseModel):
    count: int = Field(default=1, ge=1, le=100)


class OwnedItemDuplicateResponse(BaseModel):
    source_owned_item_id: int
    copy_group_key: str
    created_ids: list[int] = Field(default_factory=list)
    notices: list[str] = Field(default_factory=list)


class DigitalLinkCreate(BaseModel):
    asset_type: AssetType
    file_path: str
    link_type: LinkType

    file_hash: str | None = None
    file_size_bytes: int | None = Field(default=None, ge=0)
    duration_sec: int | None = Field(default=None, ge=0)
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    track_no: int | None = Field(default=None, ge=1)
    note: str | None = None


class DigitalLinkCreateResponse(BaseModel):
    owned_item_id: int
    digital_asset_id: int
    link_id: int


class AudioDirectoryMappingCreateRequest(BaseModel):
    directory_path: str = Field(min_length=1)
    replace_existing: bool = True
    note: str | None = None


class AudioDirectoryMappingCreateResponse(BaseModel):
    owned_item_id: int
    directory_path: str
    digital_asset_id: int
    link_id: int
    replaced_existing_links: int = 0


class AudioDirectoryMappingItem(BaseModel):
    link_id: int
    digital_asset_id: int
    directory_path: str
    note: str | None = None
    created_at: str
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class AudioDirectoryMappingListResponse(BaseModel):
    owned_item_id: int
    mapping_count: int
    mappings: list[AudioDirectoryMappingItem] = Field(default_factory=list)


class AudioDirectoryFileItem(BaseModel):
    file_path: str
    relative_path: str
    file_size_bytes: int | None = Field(default=None, ge=0)


class AudioDirectoryFileListResponse(BaseModel):
    owned_item_id: int
    directory_path: str
    recursive: bool
    file_count: int
    returned_count: int
    truncated: bool = False
    files: list[AudioDirectoryFileItem] = Field(default_factory=list)


class TrackMappingCreateRequest(BaseModel):
    track_no: int = Field(ge=1)
    file_path: str
    note: str | None = None
    file_hash: str | None = None
    file_size_bytes: int | None = Field(default=None, ge=0)
    duration_sec: int | None = Field(default=None, ge=0)
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class TrackMappingCreateResponse(BaseModel):
    owned_item_id: int
    track_no: int
    digital_asset_id: int
    link_id: int


class TrackMappingBulkFromDirRequest(BaseModel):
    directory_path: str = Field(min_length=1)
    recursive: bool = False
    replace_existing: bool = True
    extensions: list[str] = Field(
        default_factory=lambda: [
            "flac",
            "mp3",
            "m4a",
            "wav",
            "aac",
            "ogg",
            "opus",
            "aiff",
            "ape",
            "alac",
            "wma",
        ]
    )


class TrackMappingBulkMappedItem(BaseModel):
    track_no: int
    track_entry: str
    file_path: str | None = None


class TrackMappingBulkFromDirResponse(BaseModel):
    owned_item_id: int
    track_count: int
    candidate_file_count: int
    candidate_files: list[str] = Field(default_factory=list)
    mapped_count: int
    unmapped_track_count: int
    replaced_existing_links: int = 0
    mappings: list[TrackMappingBulkMappedItem] = Field(default_factory=list)


class TrackMappedAssetItem(BaseModel):
    link_id: int
    digital_asset_id: int
    file_path: str
    duration_sec: int | None = None
    note: str | None = None
    created_at: str


class TrackMappingItem(BaseModel):
    track_no: int
    track_entry: str
    assets: list[TrackMappedAssetItem]


class TrackMappingListResponse(BaseModel):
    owned_item_id: int
    track_count: int
    mappings: list[TrackMappingItem]


class TrackMappingManualAssignItem(BaseModel):
    track_no: int = Field(ge=1)
    file_path: str | None = None


class TrackMappingManualAssignRequest(BaseModel):
    replace_existing: bool = True
    allow_duplicate_files: bool = False
    assignments: list[TrackMappingManualAssignItem] = Field(default_factory=list)


class TrackMappingManualAssignResponse(BaseModel):
    owned_item_id: int
    track_count: int
    mapped_count: int
    unmapped_track_count: int
    replaced_existing_links: int = 0
    mappings: list[TrackMappingBulkMappedItem] = Field(default_factory=list)


class DirectoryPickerRequest(BaseModel):
    initial_path: str | None = None
    title: str | None = None


class DirectoryPickerResponse(BaseModel):
    directory_path: str | None = None
    cancelled: bool = False


class UiImageUploadResponse(BaseModel):
    url: str
    file_name: str
    file_size_bytes: int = Field(ge=0)
    content_type: str | None = None


class MetadataSyncRunRequest(BaseModel):
    source: MetadataSyncSource = "ALL"
    only_missing: bool = True
    limit: int = Field(default=300, ge=1, le=5000)
    inter_item_delay_sec: float = Field(default=1.5, ge=0.0, le=60.0)
    supplement_discogs: bool = True
    include_item_results: bool = False


class MetadataSyncItemResult(BaseModel):
    owned_item_id: int
    source_code: str
    source_external_id: str
    status: Literal["UPDATED", "SKIPPED", "FAILED"]
    updated_fields: list[str] = Field(default_factory=list)
    reason: str | None = None
    display_name: str | None = None
    artist_or_brand: str | None = None
    catalog_no: str | None = None


class MetadataSyncRunResponse(BaseModel):
    started_at: str
    completed_at: str
    source: MetadataSyncSource
    only_missing: bool
    limit: int
    processed_count: int
    updated_count: int
    skipped_count: int
    failed_count: int
    item_results: list[MetadataSyncItemResult] = Field(default_factory=list)


class MetadataSyncStatusResponse(BaseModel):
    auto_enabled: bool
    interval_minutes: int
    batch_limit: int
    running: bool
    in_progress_items: list[MetadataSyncItemResult] = []  # live feed while running
    last_result: MetadataSyncRunResponse | None = None
    last_error: str | None = None


class AutoBackupSettingsResponse(BaseModel):
    enabled: bool
    interval_minutes: int = Field(ge=0, le=10080)
    backup_dir: str
    backup_scope: BackupScope = "DB"
    include_env_file: bool = False
    daily_schedule: str | None = None
    weekly_schedule: str | None = None
    last_backup_at: str | None = None
    last_backup_path: str | None = None
    last_error: str | None = None


class AutoBackupSettingsUpdateRequest(BaseModel):
    enabled: bool = False
    interval_minutes: int = Field(default=0, ge=0, le=10080)
    backup_dir: str = Field(min_length=1, max_length=2000)
    backup_scope: BackupScope = "DB"
    include_env_file: bool = False


class MetadataProviderSettingsResponse(BaseModel):
    discogs_token_configured: bool = False
    aladin_ttb_key_configured: bool = False
    deepl_auth_key_configured: bool = False
    discogs_user_agent: str
    musicbrainz_user_agent: str
    aladin_base_url: str
    maniadb_base_url: str
    deepl_base_url: str


class MetadataProviderSettingsUpdateRequest(BaseModel):
    discogs_token: str | None = Field(default=None, max_length=4000)
    aladin_ttb_key: str | None = Field(default=None, max_length=4000)
    deepl_auth_key: str | None = Field(default=None, max_length=4000)
    discogs_user_agent: str | None = Field(default=None, max_length=4000)
    musicbrainz_user_agent: str | None = Field(default=None, max_length=4000)
    aladin_base_url: str | None = Field(default=None, max_length=4000)
    maniadb_base_url: str | None = Field(default=None, max_length=4000)
    deepl_base_url: str | None = Field(default=None, max_length=4000)


class MetadataProviderConnectionTestResponse(BaseModel):
    ok: bool = False
    configured: bool = False
    translated_text: str | None = None
    detail: str | None = None


class DatabaseRestoreResponse(BaseModel):
    restored: bool = True
    restored_filename: str
    restored_bytes: int = Field(ge=0)
    backup_path: str | None = None


class DiscogsIdentityResponse(BaseModel):
    username: str
    resource_url: str | None = None


class DiscogsOwnedSyncResponse(BaseModel):
    owned_item_id: int
    source_external_id: str
    username: str
    synced: bool = True


class OpsCollectorInfoResponse(BaseModel):
    available: bool = False
    owned_item_id: int
    source_code: str | None
    source_external_id: str | None
    release_title: str | None = None
    artist_or_brand: str | None = None
    country: str | None = None
    pressing_country: str | None = None
    label_name: str | None = None
    catalog_no: str | None = None
    barcode: str | None = None
    formats: list[str] = Field(default_factory=list)
    format_items: list[dict[str, Any]] = Field(default_factory=list)
    disc_count: int | None = None
    speed_rpm: int | None = None
    runout_sample: str | None = None
    other_versions_count: int = 0
    external_links: list[str] = Field(default_factory=list)
    fallback_reason: str | None = None
    fallback_message: str | None = None


class ReviewQueueItem(BaseModel):
    id: int
    batch_id: int
    row_no: int | None = None
    category: str | None = None
    payload: dict[str, Any]
    candidate: dict[str, Any] | None = None
    confidence_score: float
    review_status: ReviewStatus
    review_note: str | None = None
    created_at: str
    reviewed_at: str | None = None
    reviewed_by: str | None = None


class StorageSlotItem(BaseModel):
    id: int
    slot_code: str
    cabinet_name: str | None = None
    cabinet_domain_code: DomainCode | None = None
    cabinet_group_name: str | None = None
    cabinet_group_order: int | None = Field(default=None, ge=1)
    column_code: str | None = None
    cell_code: str | None = None
    display_name: str | None = None
    allowed_size_group: str
    cabinet_sort_policy: CabinetSortPolicy = "ARTIST_RELEASE_TITLE"
    max_thickness_mm: int | None = Field(default=None, ge=0)
    is_overflow_zone: bool


class CabinetCameraItem(BaseModel):
    id: int
    cabinet_name: str | None = None
    camera_name: str
    description: str | None = None
    onvif_device_url: str | None = None
    snapshot_url: str | None = None
    stream_url: str | None = None
    notes: str | None = None
    is_active: bool = True
    has_credentials: bool = False
    created_at: str | None = None
    updated_at: str | None = None


class CabinetCameraUpsertRequest(BaseModel):
    camera_id: int | None = Field(default=None, ge=1)
    cabinet_name: str | None = Field(default=None, max_length=80)
    camera_name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    onvif_device_url: str | None = Field(default=None, max_length=1000)
    snapshot_url: str | None = Field(default=None, max_length=1000)
    stream_url: str | None = Field(default=None, max_length=1000)
    username: str | None = Field(default=None, max_length=200)
    password: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=1000)
    is_active: bool = True


class CabinetCameraDeleteResponse(BaseModel):
    camera_id: int
    cabinet_name: str
    deleted: bool


class CabinetCameraDiscoveryItem(BaseModel):
    endpoint_reference: str | None = None
    camera_name: str | None = None
    host: str | None = None
    onvif_device_url: str | None = None
    scopes: list[str] = Field(default_factory=list)
    types: list[str] = Field(default_factory=list)


class CabinetCameraConnectionTestRequest(BaseModel):
    camera_id: int | None = Field(default=None, ge=1)
    onvif_device_url: str = Field(min_length=1, max_length=1000)
    username: str | None = Field(default=None, max_length=200)
    password: str | None = Field(default=None, max_length=500)


class CabinetCameraConnectionTestResponse(BaseModel):
    device_service_url: str
    media_service_url: str | None = None
    profile_token: str | None = None
    snapshot_url: str | None = None
    stream_url: str | None = None
    manufacturer: str | None = None
    model: str | None = None
    firmware_version: str | None = None
    serial_number: str | None = None
    hardware_id: str | None = None


class StorageSlotUpsertRequest(BaseModel):
    slot_id: int | None = Field(default=None, ge=1)
    cabinet_name: str = Field(min_length=1, max_length=80)
    column_code: str | None = Field(default=None, max_length=40)
    cell_code: str | None = Field(default=None, max_length=40)
    cabinet_domain_code: DomainCode | None = None
    allowed_size_group: SizeGroup
    cabinet_sort_policy: CabinetSortPolicy = "ARTIST_RELEASE_TITLE"
    max_thickness_mm: int | None = Field(default=None, ge=0)
    is_overflow_zone: bool = False


class StorageCabinetRegisterRequest(BaseModel):
    cabinet_name: str = Field(min_length=1, max_length=80)
    cabinet_domain_code: DomainCode | None = None
    cabinet_group_name: str | None = Field(default=None, max_length=80)
    cabinet_group_order: int | None = Field(default=None, ge=1, le=999)
    floor_count: int = Field(ge=1, le=99)
    cell_count: int = Field(ge=1, le=999)
    floor_start: int = Field(default=1, ge=1, le=999)
    cell_start: int = Field(default=1, ge=1, le=999)
    allowed_size_group: SizeGroup
    cabinet_sort_policy: CabinetSortPolicy = "ARTIST_RELEASE_TITLE"
    max_thickness_mm: int | None = Field(default=None, ge=0)


class StorageCabinetRegisterResponse(BaseModel):
    cabinet_name: str
    cabinet_domain_code: DomainCode | None = None
    cabinet_group_name: str | None = None
    cabinet_group_order: int | None = None
    floor_count: int
    cell_count: int
    cabinet_sort_policy: CabinetSortPolicy = "ARTIST_RELEASE_TITLE"
    max_thickness_mm: int = 0
    created_count: int
    updated_count: int
    total_slot_count: int


class StorageCabinetDeleteResponse(BaseModel):
    cabinet_name: str
    deleted_slot_count: int
    unassigned_item_count: int

# ── Placement Hints ──────────────────────────────────────────────

class OpsPlacementHintRequest(BaseModel):
    owned_item_id: int = Field(ge=1)


class OpsPlacementHintRecommendation(BaseModel):
    rank: int = Field(ge=1)
    storage_slot_id: int = Field(ge=1)
    slot_code: str
    slot_display_name: str
    reason_code: str
    reason_message: str


class OpsPlacementHintResponse(BaseModel):
    available: bool = False
    recommendations: list[OpsPlacementHintRecommendation] = Field(default_factory=list)
    fallback_reason: str | None = None
    fallback_message: str | None = None


# ── Product Groups ───────────────────────────────────────────────

class ProductGroupCreateRequest(BaseModel):
    group_type: Literal["SERIES", "CAMPAIGN"] = "SERIES"
    group_name: str = Field(min_length=1, max_length=120)
    description: str | None = None
