#!/usr/bin/env python
"""Train all ML pipelines. Usage: python train_all_models.py"""

import sys
sys.path.insert(0, ".")

from utils.data_loader import load_simulation_to_database
from ml.feature_engineering import build_feature_store


def main():
    print("=== Training models (data already generated) ===")
    from utils.data_loader import load_simulation_to_database
    load_simulation_to_database(force=False)
    build_feature_store()
    print("=== Disaggregation ===")
    import train_disaggregation_model
    train_disaggregation_model.train_all()
    print("=== Anomaly ===")
    import train_anomaly_model
    train_anomaly_model.train_all()
    print("=== Bill ===")
    import train_bill_model
    train_bill_model.train_all()
    print("=== Done ===")


if __name__ == "__main__":
    main()
