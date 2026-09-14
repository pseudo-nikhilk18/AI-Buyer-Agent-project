from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.database import Base


class Product(Base):
    __tablename__ = "products"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    sku: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class FulfillmentNode(Base):
    __tablename__ = "fulfillment_nodes"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Supplier(Base):
    __tablename__ = "suppliers"
    __table_args__ = (
        CheckConstraint(
            "reliability_percent >= 0 AND reliability_percent <= 100",
            name="ck_supplier_reliability_range",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    reliability_percent: Mapped[int] = mapped_column(Integer, nullable=False)


class SupplierTerm(Base):
    __tablename__ = "supplier_terms"
    __table_args__ = (
        UniqueConstraint("supplier_id", "product_id", name="uq_supplier_term_product"),
        CheckConstraint("unit_cost_minor > 0", name="ck_supplier_term_cost_positive"),
        CheckConstraint("minimum_order_quantity > 0", name="ck_supplier_term_moq_positive"),
        CheckConstraint("case_pack_quantity > 0", name="ck_supplier_term_pack_positive"),
        CheckConstraint("lead_time_days >= 0", name="ck_supplier_term_lead_time_nonnegative"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    supplier_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=False
    )
    product_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )
    unit_cost_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    minimum_order_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    case_pack_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    lead_time_days: Mapped[int] = mapped_column(Integer, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    supplier: Mapped[Supplier] = relationship()
    product: Mapped[Product] = relationship()


class PurchasingPolicy(Base):
    __tablename__ = "purchasing_policies"
    __table_args__ = (
        CheckConstraint("review_period_days > 0", name="ck_policy_review_period_positive"),
        CheckConstraint("safety_stock_days >= 0", name="ck_policy_safety_days_nonnegative"),
        CheckConstraint("auto_spend_limit_minor >= 0", name="ck_policy_spend_nonnegative"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    review_period_days: Mapped[int] = mapped_column(Integer, nullable=False)
    safety_stock_days: Mapped[int] = mapped_column(Integer, nullable=False)
    inventory_freshness_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    forecast_freshness_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    supplier_freshness_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    constraint_freshness_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    auto_spend_limit_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)


class PurchasingCase(Base):
    __tablename__ = "purchasing_cases"
    __table_args__ = (
        CheckConstraint("recommended_quantity > 0", name="ck_case_recommendation_positive"),
        Index("ix_purchasing_cases_created_at", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    scenario_type: Mapped[str] = mapped_column(String(40), nullable=False)
    product_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )
    node_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("fulfillment_nodes.id", ondelete="RESTRICT"), nullable=False
    )
    supplier_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=False
    )
    policy_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("purchasing_policies.id", ondelete="RESTRICT"), nullable=False
    )
    recommended_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="ready")
    simulator_mode: Mapped[str] = mapped_column(String(40), nullable=False, default="normal")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    product: Mapped[Product] = relationship()
    node: Mapped[FulfillmentNode] = relationship()
    supplier: Mapped[Supplier] = relationship()
    policy: Mapped[PurchasingPolicy] = relationship()


class InventorySnapshot(Base):
    __tablename__ = "inventory_snapshots"
    __table_args__ = (
        CheckConstraint("on_hand_quantity >= 0", name="ck_inventory_on_hand_nonnegative"),
        CheckConstraint("reserved_quantity >= 0", name="ck_inventory_reserved_nonnegative"),
        CheckConstraint("damaged_quantity >= 0", name="ck_inventory_damaged_nonnegative"),
        Index("ix_inventory_case_observed", "case_id", "observed_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("purchasing_cases.id", ondelete="CASCADE"), nullable=False
    )
    on_hand_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    reserved_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    damaged_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SupplierAvailabilitySnapshot(Base):
    __tablename__ = "supplier_availability_snapshots"
    __table_args__ = (
        CheckConstraint(
            "available_quantity >= 0",
            name="ck_supplier_availability_nonnegative",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("purchasing_cases.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    available_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class DemandForecast(Base):
    __tablename__ = "demand_forecasts"
    __table_args__ = (
        UniqueConstraint("case_id", "demand_date", name="uq_forecast_case_date"),
        CheckConstraint("quantity >= 0", name="ck_forecast_quantity_nonnegative"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("purchasing_cases.id", ondelete="CASCADE"), nullable=False
    )
    demand_date: Mapped[date] = mapped_column(Date, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class BudgetSnapshot(Base):
    __tablename__ = "budget_snapshots"
    __table_args__ = (
        CheckConstraint("available_minor >= 0", name="ck_budget_available_nonnegative"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("purchasing_cases.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    available_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CapacitySnapshot(Base):
    __tablename__ = "capacity_snapshots"
    __table_args__ = (
        CheckConstraint("available_quantity >= 0", name="ck_capacity_available_nonnegative"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("purchasing_cases.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    available_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_purchase_order_quantity_positive"),
        UniqueConstraint("idempotency_key", name="uq_purchase_order_idempotency"),
        Index("ix_purchase_orders_case_status", "case_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("purchasing_cases.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("products.id"), nullable=False)
    node_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("fulfillment_nodes.id"), nullable=False
    )
    supplier_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("suppliers.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_cost_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    expected_delivery_date: Mapped[date] = mapped_column(Date, nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class AgentRun(Base):
    __tablename__ = "agent_runs"
    __table_args__ = (
        UniqueConstraint("thread_id", name="uq_agent_run_thread"),
        Index("ix_agent_runs_case_started", "case_id", "started_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("purchasing_cases.id", ondelete="CASCADE"), nullable=False
    )
    thread_id: Mapped[str] = mapped_column(String(64), nullable=False)
    mode: Mapped[str] = mapped_column(String(20), nullable=False)
    provider: Mapped[str | None] = mapped_column(String(30), nullable=True)
    model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    decision: Mapped[str | None] = mapped_column(String(30), nullable=True)
    authorization: Mapped[str | None] = mapped_column(String(30), nullable=True)
    proposed_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    proposed_spend_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason_codes: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    state_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class EvidenceRecord(Base):
    __tablename__ = "evidence_records"
    __table_args__ = (
        UniqueConstraint("run_id", "tool_name", name="uq_evidence_run_tool"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False
    )
    tool_name: Mapped[str] = mapped_column(String(80), nullable=False)
    payload: Mapped[dict | list] = mapped_column(JSONB, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_fresh: Mapped[bool] = mapped_column(Boolean, nullable=False)


class PolicyCheck(Base):
    __tablename__ = "policy_checks"
    __table_args__ = (
        UniqueConstraint("run_id", "code", name="uq_policy_check_run_code"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    detail: Mapped[str] = mapped_column(Text, nullable=False)
    actual: Mapped[dict | int | str | None] = mapped_column(JSONB, nullable=True)
    expected: Mapped[dict | int | str | None] = mapped_column(JSONB, nullable=True)


class ActionAttempt(Base):
    __tablename__ = "action_attempts"
    __table_args__ = (Index("ix_action_attempt_idempotency", "idempotency_key"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False
    )
    purchase_order_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("purchase_orders.id", ondelete="SET NULL"), nullable=True
    )
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)
    action_type: Mapped[str] = mapped_column(String(30), nullable=False)
    requested_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    actual_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    response_payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ValidationResult(Base):
    __tablename__ = "validation_results"
    __table_args__ = (UniqueConstraint("run_id", name="uq_validation_run"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    expected_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actual_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    detail: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
