from fastapi import FastAPI
import tf_prop_model 

app = FastAPI()

@app.post("/run-analytics/{game_id}")
async def run_daily_logic(game_id: str):
    # This is the math engine calling your 12 filters
    results = tf_prop_model.predict(game_id)
    
    # This sends the answer back to your web app
    return {"status": "success", "data": results}