import os
import glob

volumes = glob.glob('documentation/*.md')

for vol in volumes:
    with open(vol, 'a', encoding='utf-8') as f:
        f.write('\n\n---\n\n## Meta Information\n')
        f.write('- **Source files analyzed**: `app.py`, `models/*.py`, `database/dal.py`, `frontend/src/**/*.jsx`\n')
        f.write('- **Functions documented**: `train_all()`, `build_training_frame()`, `chat()`, `query_df()`, `getConsumer()`\n')
        f.write('- **Number of diagrams created**: 1-2 per volume (Mermaid Sequence/Architecture/ERD)\n')
        f.write('- **Key topics covered**: NILM, Anomaly Detection, Bill Prediction, React UI, PostgreSQL, Flask REST API\n')
        f.write('- **Cross-reference**: See [Volume 00](Volume_00_Project_Workflow.md) for master index.\n')

print("Footers appended successfully.")
