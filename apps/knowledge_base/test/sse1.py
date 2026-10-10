import asyncio
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

app=FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)
async def event_generator():
    for i in range(5):
        yield f"data: 这是第{i+1}条测试消息\n\n"
        await asyncio.sleep(1)
    yield f"data: [END]\n\n"
    # 结束标识，不然会无限循环
@app.get("/simple_stream")
async def simple_stream():
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
    )
if __name__ == "__main__":
    import uvicorn
    # 开发期临时脚本：端口避开生产端口（8000/8001/8002/8004）
    uvicorn.run(app, host="127.0.0.1", port=18001)