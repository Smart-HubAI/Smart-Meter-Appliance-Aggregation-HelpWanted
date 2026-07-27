from database.dal import query_df
df = query_df("SELECT * FROM model_validation")
print(df)
