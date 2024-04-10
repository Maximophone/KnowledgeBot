import yaml
import os
import whisper
import torch
import json

with open("secrets.yml", "r") as f:
    secrets = yaml.safe_load(f)

if torch.cuda.is_available():
    print("Computing on GPU")
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model = whisper.load_model("small", device=device)

for fname in os.listdir("data/Recorder"):
    if f"{fname}.json" in os.listdir("output"):
        # already transcribed, we skip it
        continue
    print(fname, flush=True)
    result = model.transcribe(f"data/Recorder/{fname}")
    with open(f"output/{fname}.json", "w") as f:
        json.dump(result, f)
