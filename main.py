import time
import uuid
import base64

from fastapi import FastAPI, Header, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

TOTAL_ORDERS = 49
RATE_LIMIT = 17
WINDOW = 10

# Stores idempotency key -> order
orders_created = {}

# Stores client_id -> timestamps
rate_limit_store = {}


class Order(BaseModel):
    item: str = "product"
    quantity: int = 1


@app.middleware("http")
async def rate_limit(request, call_next):
    client = request.headers.get("X-Client-Id", "default")

    now = time.time()

    timestamps = rate_limit_store.setdefault(client, [])

    timestamps[:] = [t for t in timestamps if now - t < WINDOW]

    if len(timestamps) >= RATE_LIMIT:
        response = Response(status_code=429)
        response.headers["Retry-After"] = "10"
        return response

    timestamps.append(now)

    return await call_next(request)


@app.post("/orders", status_code=201)
def create_order(
    order: Order,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
):
    if idempotency_key in orders_created:
        return orders_created[idempotency_key]

    order_id = str(uuid.uuid4())

    data = {
        "id": order_id,
        "item": order.item,
        "quantity": order.quantity,
    }

    orders_created[idempotency_key] = data

    return data


@app.get("/orders")
def list_orders(limit: int = 10, cursor: str | None = None):
    start = 1

    if cursor:
        start = int(base64.b64decode(cursor).decode())

    end = min(start + limit - 1, TOTAL_ORDERS)

    items = [
        {
            "id": i
        }
        for i in range(start, end + 1)
    ]

    next_cursor = None

    if end < TOTAL_ORDERS:
        next_cursor = base64.b64encode(
            str(end + 1).encode()
        ).decode()

    return {
        "items": items,
        "next_cursor": next_cursor,
    }
