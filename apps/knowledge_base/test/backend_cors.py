from fastapi import FastAPI
import uvicorn
from starlette.middleware.cors import CORSMiddleware
app=FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
@app.get("/api/data")
async def get_data():
    return {"message":"这是后端数据","status":"success"}
if __name__=="__main__":
    # 开发期临时脚本：端口避开生产端口（8000/8001/8002/8004）
    uvicorn.run(app, host="127.0.0.1", port=18001)