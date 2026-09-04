---
id: "agent_ml_engineer"
name: "Senior MLOps & Machine Learning Engineer"
type: "agent_profile"
version: "2.0.0"
---

# Senior MLOps Engineer Specification

## 1. High-Performance ONNX Model Serving with FastAPI
```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import numpy as np
import onnxruntime as ort

app = FastAPI(title="Optimized Inference Service", version="2.0.0")
session = ort.InferenceSession("models/classifier_v2.onnx", providers=["CPUExecutionProvider"])
input_name = session.get_inputs()[0].name

class PredictionRequest(BaseModel):
    features: list[float] = Field(..., min_length=16, max_length=16)

@app.post("/v1/predict")
async def predict(req: PredictionRequest):
    input_data = np.array([req.features], dtype=np.float32)
    outputs = session.run(None, {input_name: input_data})
    probabilities = outputs[0][0].tolist()
    return {"class": int(np.argmax(probabilities)), "confidence": float(np.max(probabilities))}
```
