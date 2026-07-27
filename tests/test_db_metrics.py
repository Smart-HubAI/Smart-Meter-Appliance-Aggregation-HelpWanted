from database.dal import get_model_metrics

metrics = get_model_metrics("disaggregation")
for m in metrics:
    print(m)
