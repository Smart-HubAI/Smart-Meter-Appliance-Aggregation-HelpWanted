from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, JSON, Index
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from database.postgres_config import Base

class Consumer_Master(Base):
    __tablename__ = "consumer_master"

    id = Column(Integer, primary_key=True, index=True)
    consumer_id = Column(String, unique=True, index=True, nullable=False)
    consumer_name = Column(String)
    name = Column(String, nullable=False)
    address = Column(String)
    meter_number = Column(String)
    tariff_category = Column(String, default='domestic')
    scenario = Column(String)
    zone = Column(String, index=True)
    consumer_type = Column(String, default='Residential')
    meter_interval = Column(Integer, default=15)
    outstanding_amount = Column(Float, default=0)
    days_overdue = Column(Integer, default=0)
    payment_status = Column(String, default='Current')
    risk_category = Column(String, default='Normal')
    segment = Column(String)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    readings = relationship("Smart_Meter_Readings", back_populates="consumer")
    features = relationship("Feature_Engineering", back_populates="consumer")
    appliance_predictions = relationship("Appliance_Predictions", back_populates="consumer")
    anomalies = relationship("Anomaly_Detection", back_populates="consumer")

class Smart_Meter_Readings(Base):
    __tablename__ = "smart_meter_readings"

    id = Column(Integer, primary_key=True, index=True)
    consumer_id = Column(String, ForeignKey("consumer_master.consumer_id"), index=True, nullable=False)
    meter_id = Column(String, index=True)
    timestamp = Column(DateTime, index=True, nullable=False)
    
    # Readings
    active_power_kw = Column(Float, nullable=False)
    active_energy_kwh = Column(Float, nullable=False)
    reactive_power_kvar = Column(Float)
    reactive_energy_kvarh = Column(Float)
    apparent_power_kva = Column(Float)
    power_factor = Column(Float)
    temperature = Column(Float)
    
    # Flags and status
    meter_event_flag = Column(String, index=True)
    relay_status = Column(String)
    tamper_flag = Column(String, index=True)
    
    # Metadata snapshot (normalized but kept for historical analytics if requested, though mostly fetched from consumer)
    consumer_category = Column(String, index=True)
    zone = Column(String, index=True)
    tariff_category = Column(String, index=True)
    meter_type = Column(String)
    smart_meter_interval = Column(Integer)
    sanctioned_load_kw = Column(Float)
    contract_demand_kw = Column(Float)
    connection_status = Column(String)

    # Relationships
    consumer = relationship("Consumer_Master", back_populates="readings")

    __table_args__ = (
        Index("idx_smr_consumer_ts", "consumer_id", "timestamp"),
    )

class Feature_Engineering(Base):
    __tablename__ = "feature_engineering"

    id = Column(Integer, primary_key=True, index=True)
    consumer_id = Column(String, ForeignKey("consumer_master.consumer_id"), index=True, nullable=False)
    date = Column(DateTime, index=True, nullable=False)
    daily_kwh = Column(Float)
    average_load = Column(Float)
    peak_load = Column(Float)
    load_factor = Column(Float)
    night_usage_ratio = Column(Float)
    power_factor_average = Column(Float)
    voltage_variance = Column(Float)
    consumption_deviation = Column(Float)

    consumer = relationship("Consumer_Master", back_populates="features")

    __table_args__ = (
        Index("idx_fe_consumer_date", "consumer_id", "date", unique=True),
    )

class Appliance_Predictions(Base):
    __tablename__ = "appliance_predictions"

    id = Column(Integer, primary_key=True, index=True)
    consumer_id = Column(String, ForeignKey("consumer_master.consumer_id"), index=True, nullable=False)
    timestamp = Column(DateTime, index=True, nullable=False)
    
    appliance_name = Column(String, nullable=False, index=True)
    predicted_energy_kwh = Column(Float)
    percentage_contribution = Column(Float)
    confidence = Column(Float)
    probability = Column(Float)
    model_used = Column(String)
    estimated_monthly_cost = Column(Float)
    reasoning_summary = Column(String)
    important_features = Column(JSON)
    status = Column(String)
    last_updated = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    consumer = relationship("Consumer_Master", back_populates="appliance_predictions")

    __table_args__ = (
        Index("idx_ap_consumer_ts", "consumer_id", "timestamp"),
    )

class Anomaly_Detection(Base):
    __tablename__ = "anomaly_detection"

    id = Column(Integer, primary_key=True, index=True)
    consumer_id = Column(String, ForeignKey("consumer_master.consumer_id"), index=True, nullable=False)
    detected_at = Column(DateTime, index=True, nullable=False)
    anomaly_type = Column(String, nullable=False, index=True)
    reason = Column(String)
    severity = Column(String)
    details_json = Column(JSON)
    resolved = Column(Boolean, default=False)
    is_ground_truth = Column(Boolean, default=False) # Distinguish between ground truth and detected

    consumer = relationship("Consumer_Master", back_populates="anomalies")

    __table_args__ = (
        Index("idx_ad_consumer_date", "consumer_id", "detected_at"),
    )

class Billing(Base):
    __tablename__ = "billing"

    id = Column(Integer, primary_key=True, index=True)
    consumer_id = Column(String, ForeignKey("consumer_master.consumer_id"), index=True, nullable=False)
    billing_month = Column(String, index=True, nullable=False) # e.g. '2026-06'
    total_kwh = Column(Float)
    energy_charge = Column(Float)
    fixed_charge = Column(Float)
    fac_charge = Column(Float)
    electricity_duty = Column(Float)
    tod_rebate = Column(Float)
    peak_surcharge = Column(Float)
    final_bill = Column(Float)
    details_json = Column(JSON)
    computed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("idx_bill_consumer_month", "consumer_id", "billing_month", unique=True),
    )

class Tariff(Base):
    __tablename__ = "tariff"

    id = Column(Integer, primary_key=True, index=True)
    tariff_category = Column(String, unique=True, index=True, nullable=False)
    billing_type = Column(String) # 'slab', 'tod', 'flat'
    fixed_charge = Column(Float)
    rate = Column(Float)
    slabs_json = Column(JSON)
    tod_json = Column(JSON)
    fac_per_unit = Column(Float)
    electricity_duty_pct = Column(Float)

class Carbon_Emission(Base):
    __tablename__ = "carbon_emission"

    id = Column(Integer, primary_key=True, index=True)
    consumer_id = Column(String, ForeignKey("consumer_master.consumer_id"), index=True, nullable=False)
    month = Column(String, index=True, nullable=False)
    carbon_kg = Column(Float)
    trees_needed = Column(Integer)
    vehicle_km_equiv = Column(Float)
    computed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("idx_ce_consumer_month", "consumer_id", "month", unique=True),
    )

class Model_Validation(Base):
    __tablename__ = "model_validation"

    id = Column(Integer, primary_key=True, index=True)
    model_name = Column(String, nullable=False, index=True)
    task = Column(String, nullable=False, index=True)
    metric_name = Column(String, nullable=False)
    metric_value = Column(Float)
    samples = Column(Integer)
    details_json = Column(JSON)
    trained_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False, default='consumer')
    consumer_id = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_login = Column(DateTime)

class Audit_Log(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, index=True)
    role = Column(String)
    action = Column(String, nullable=False)
    page_accessed = Column(String)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

class Analytics(Base):
    # To support caching metrics that used to go in the old 'analytics' table
    __tablename__ = "analytics"

    id = Column(Integer, primary_key=True, index=True)
    consumer_id = Column(String, index=True, nullable=False)
    metric_name = Column(String, nullable=False)
    metric_value = Column(Float)
    metric_json = Column(JSON)
    computed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("idx_analytics_consumer_metric", "consumer_id", "metric_name", unique=True),
    )

class Investigation(Base):
    __tablename__ = "investigations"

    id = Column(Integer, primary_key=True, index=True)
    consumer_id = Column(String, ForeignKey("consumer_master.consumer_id"), unique=True, index=True, nullable=False)
    status = Column(String, default="Open", nullable=False)
    assigned_to = Column(String)
    last_updated = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    remarks = Column(String)

    consumer = relationship("Consumer_Master")

class Investigation_History(Base):
    __tablename__ = "investigation_history"

    id = Column(Integer, primary_key=True, index=True)
    consumer_id = Column(String, ForeignKey("consumer_master.consumer_id"), index=True, nullable=False)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    previous_status = Column(String)
    new_status = Column(String, nullable=False)
    changed_by = Column(String)
    remarks = Column(String)

    consumer = relationship("Consumer_Master")
