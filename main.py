import time, uuid
from fastapi import FastAPI, Request, Header, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import Optional

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

TOTAL_ORDERS = 43
RATE_LIMIT   = 19
WINDOW_SECS  = 10

# Storage
idempotency_store: dict = {}   # key -> order dict
rate_buckets: dict      = {}   # client_id -> [timestamps]

def make_order(order_id: int):
    return {"id": str(order_id), "name": f"Order #{order_id}", "status": "created"}

@app.post("/orders", status_code=201)
async def create_order(
    request: Request,
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    x_client_id: Optional[str] = Header(default=None),
):
    # Rate limit check
    if x_client_id:
        now = time.time()
        bucket = rate_buckets.setdefault(x_client_id, [])
        bucket[:] = [t for t in bucket if now - t < WINDOW_SECS]
        if len(bucket) >= RATE_LIMIT:
            return JSONResponse(
                status_code=429,
                headers={"Retry-After": str(WINDOW_SECS)},
                content={"detail": "Rate limit exceeded"},
            )
        bucket.append(now)

    if idempotency_key and idempotency_key in idempotency_store:
        return JSONResponse(status_code=201, content=idempotency_store[idempotency_key])

    new_id = len(idempotency_store) + 1000
    order  = make_order(new_id)
    if idempotency_key:
        idempotency_store[idempotency_key] = order
    return JSONResponse(status_code=201, content=order)

@app.get("/orders")
async def list_orders(
    request: Request,
    limit: int = 10,
    cursor: Optional[str] = None,
    x_client_id: Optional[str] = Header(default=None),
):
    # Rate limit check
    if x_client_id:
        now = time.time()
        bucket = rate_buckets.setdefault(x_client_id, [])
        bucket[:] = [t for t in bucket if now - t < WINDOW_SECS]
        if len(bucket) >= RATE_LIMIT:
            return JSONResponse(
                status_code=429,
                headers={"Retry-After": str(WINDOW_SECS)},
                content={"detail": "Rate limit exceeded"},
            )
        bucket.append(now)

    all_ids = list(range(1, TOTAL_ORDERS + 1))
    start   = int(cursor) if cursor else 0
    page    = all_ids[start: start + limit]
    next_cursor = str(start + limit) if (start + limit) < TOTAL_ORDERS else None
    items   = [{"id": i, "name": f"Order #{i}"} for i in page]
    return {"items": items, "next_cursor": next_cursor}
