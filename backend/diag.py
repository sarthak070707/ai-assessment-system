"""Diagnose the Groq connection directly, bypassing the app."""
import os, sys
sys.path.insert(0, ".")
from app.config import get_settings   # loads .env
from app import llm

print(f"key present : {llm.is_configured()}")
print(f"model       : {llm.model_name()}")
if not llm.is_configured():
    print("\n-> No GROQ_API_KEY reaching the app. Check backend/.env exists and is named exactly '.env'.")
    raise SystemExit

SAMPLE = """Section A - Answer any two.

1 (a)  Describe an approach that finds two numbers summing to a target in linear time.   (8)

2      Which of the following is true of a binary search tree?
       i.   Inorder traversal yields sorted output
       ii.  Lookup is always O(log n)

ANSWER KEY
2 - i only
"""
try:
    questions = llm.extract(SAMPLE, timeout=60)
    print(f"\nSUCCESS - extracted {len(questions)} questions")
    for q in questions:
        print(f"  {q['kind']:<12} {q['max_score']} marks  key={q['correct_option']}  {q['prompt'][:56]}")
except llm.LLMUnavailable as exc:
    print(f"\nFAILED - {exc}")