import json
import os
from pathlib import Path
from natural_rag.dataset import RAGDataset

DATASET_NAME = os.environ.get('DATASET_NAME', 'chegeka')
ANSWERS_DIR = Path(os.environ.get('ANSWERS_DIR', f'generated/fast_graphrag_{DATASET_NAME}/answers'))
ANSWERS_JSON_FILE = os.environ.get('ANSWERS_JSON_FILE', f'{DATASET_NAME}_answers.json')

dataset = RAGDataset.load_auto(f'datasets/{DATASET_NAME}')

answers_json = []
for q_idx, question in enumerate(dataset.questions):
    answer_path = ANSWERS_DIR / f'{q_idx}.txt'
    if answer_path.exists():
        answers_json.append({
            "question": question.text,
            "rag_answer": answer_path.read_text()
        })
    else:
        print(f"Warning: answer for question {q_idx} not found")

json_path = ANSWERS_DIR / ANSWERS_JSON_FILE
json_path.write_text(json.dumps(answers_json, ensure_ascii=False, indent=2))
print(f"Saved {len(answers_json)} answers to {json_path}")