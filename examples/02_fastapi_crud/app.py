from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Optional

app = FastAPI(title="Saleha Task API", version="1.0.0")

class Task(BaseModel):
    id: Optional[int] = None
    title: str
    completed: bool = False

db: Dict[int, Task] = {}
counter = 1

@app.post("/tasks", response_model=Task)
def create_task(task: Task):
    global counter
    task.id = counter
    db[counter] = task
    counter += 1
    return task

@app.get("/tasks", response_model=List[Task])
def list_tasks():
    return list(db.values())

@app.get("/tasks/{task_id}", response_model=Task)
def get_task(task_id: int):
    if task_id not in db:
        raise HTTPException(status_code=404, detail="Task not found")
    return db[task_id]

@app.delete("/tasks/{task_id}")
def delete_task(task_id: int):
    if task_id not in db:
        raise HTTPException(status_code=404, detail="Task not found")
    del db[task_id]
    return {"ok": True}

