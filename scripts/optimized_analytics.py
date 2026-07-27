from flask import jsonify
from models import db, ZoneAnalytics, ConsumerRiskScore, ConsumerPredictions

def get_admin_dashboard_metrics():
    """
    Reads precomputed data from cache tables.
    Target: < 1s response time.
    """
    # 1. Fetch Zone aggregated data
    zones = ZoneAnalytics.query.all()
    
    # 2. Fetch High Risk Priority Queue
    # Already sorted by index in DB
    priority_queue = ConsumerRiskScore.query.order_by(
        ConsumerRiskScore.risk_score.desc()
    ).limit(10).all()

    return {
        "summary": {
            "total_consumption": sum(z.total_consumption for z in zones),
            "anomalies": sum(z.anomaly_count for z in zones),
            "peak_demand": max((z.peak_demand for z in zones), default=0)
        },
        "zones": [z.to_dict() for z in zones],
        "priority_queue": [p.to_dict() for p in priority_queue]
    }

def get_appliance_data(consumer_id):
    """
    Retrieves cached ML disaggregation for a specific consumer.
    No ML models (Random Forest/XGBoost) are run here.
    """
    prediction = ConsumerPredictions.query.filter_by(consumer_id=consumer_id).first()
    if not prediction:
        # Return empty structure if not yet processed by background worker
        return {"ac_percent": 0, "miscellaneous_percent": 0} 
    
    return prediction.to_dict()