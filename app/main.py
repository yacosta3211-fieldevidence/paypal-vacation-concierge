import os
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from dotenv import load_dotenv
from google import genai
from google.genai import types
from render import RenderAsync

from app.paypal_service import create_vacation_order, capture_vacation_order
from workflows.sentinel import HOTEL_CATALOG

load_dotenv()

app = FastAPI(title="PayPal AI Vacation Concierge")

# In-memory demo store for fast Judge evaluation (swap with SQLite/Postgres if desired)
USER_STATE = {
    "demo_user": {
        "bucket_balance": 850.00,
        "goal_amount": 1200.00,
        "pinned_hotel_id": "HTL-NASH-01",
        "pinned_hotel_name": HOTEL_CATALOG["HTL-NASH-01"]["name"],
        "last_known_price": 1180.00,
        "booking_status": "WATCHING",  # WATCHING | READY_TO_BOOK | PAID_VIA_PAYPAL
        "last_workflow_run_id": None,
    }
}


class ChatRequest(BaseModel):
    message: str


class CreateOrderPayload(BaseModel):
    amount: float
    order_type: str  # "BUCKET_TOPUP" or "HOTEL_BOOKING"


class JudgeTriggerPayload(BaseModel):
    simulate_drop: bool = True


# Gemini Tool Definitions for Conversational Window Shopping
def get_vacation_bucket_status() -> dict:
    """Returns the user's current PayPal Vacation Bucket balance and pinned trip details."""
    return USER_STATE["demo_user"]


def search_and_pin_hotel(destination_keyword: str) -> dict:
    """Finds a boutique stay in Nashville or Montreal and pins it to the user's Vacation Bucket watcher."""
    key = "HTL-MTL-02" if "montreal" in destination_keyword.lower() else "HTL-NASH-01"
    hotel = HOTEL_CATALOG[key]
    USER_STATE["demo_user"]["pinned_hotel_id"] = key
    USER_STATE["demo_user"]["pinned_hotel_name"] = hotel["name"]
    USER_STATE["demo_user"]["last_known_price"] = hotel["base_total_usd"]
    USER_STATE["demo_user"]["booking_status"] = "WATCHING"
    return {
        "pinned_hotel_id": key,
        "hotel_name": hotel["name"],
        "nights": hotel["nights"],
        "current_price_usd": hotel["base_total_usd"],
        "user_bucket_balance_usd": USER_STATE["demo_user"]["bucket_balance"],
    }


@app.get("/api/state")
async def get_state():
    """Returns live bucket balance, pinned hotel state, and PayPal Sandbox Client ID."""
    return {
        "state": USER_STATE["demo_user"],
        "paypal_client_id": os.getenv("PAYPAL_CLIENT_ID", "sb"),
    }


@app.post("/api/chat")
async def chat_with_concierge(req: ChatRequest):
    """Conversational AI endpoint powered by Gemini 2.5 Flash + Function Calling."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="Missing GEMINI_API_KEY")

    client = genai.Client(api_key=api_key)
    system_instruction = (
        "You are the PayPal Vacation Concierge. Always check the user's live Vacation "
        "Bucket balance before recommending trips. Compare their exact balance against "
        "available stays in Nashville ($1,180 for 4 nights) or Montreal ($1,240 for 4 nights). "
        "If a trip costs more than their current bucket, offer to PIN it so the Render "
        "Workflow Dual-Trigger Sentinel can watch for a price drop or bucket top-up."
    )

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=req.message,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            tools=[get_vacation_bucket_status, search_and_pin_hotel],
            temperature=0.3,
        ),
    )
    return {"reply": response.text, "state": USER_STATE["demo_user"]}


@app.post("/api/judge/add-funds")
async def judge_instant_autosave():
    """Judge Demo Control #1: Instantly adds a $150 Auto-Save deposit to the bucket."""
    USER_STATE["demo_user"]["bucket_balance"] = round(
        USER_STATE["demo_user"]["bucket_balance"] + 150.00, 2
    )
    return {"state": USER_STATE["demo_user"]}


@app.post("/api/judge/trigger-sentinel")
async def trigger_render_workflow_sentinel(payload: JudgeTriggerPayload):
    """
    Judge Demo Control #2: Triggers the Render Workflows 'evaluate_pinned_trip' task
    and waits for the chained result. Falls back cleanly for local offline testing.
    """
    user = USER_STATE["demo_user"]
    workflow_slug = os.getenv("RENDER_WORKFLOW_SLUG", "vacation-sentinel")
    task_identifier = f"{workflow_slug}/evaluate_pinned_trip"

    if os.getenv("RENDER_API_KEY"):
        # Trigger live durable task chain on Render Workflows
        render_client = RenderAsync()
        task_run = await render_client.workflows.run_task(
            task_identifier,
            [
                "demo_user",
                user["pinned_hotel_id"],
                user["bucket_balance"],
                payload.simulate_drop,
            ],
        )
        result = task_run.results[0] if isinstance(task_run.results, list) else task_run.results
        user["last_workflow_run_id"] = task_run.id
    else:
        # Local development fallback if RENDER_API_KEY is not set yet
        hotel = HOTEL_CATALOG[user["pinned_hotel_id"]]
        new_price = round(hotel["base_total_usd"] * 0.8135, 2) if payload.simulate_drop else hotel["base_total_usd"]
        if user["bucket_balance"] >= new_price:
            result = {
                "status": "READY_TO_BOOK",
                "bookable_price": new_price,
                "alert_message": (
                    f"Crossover Alert! {hotel['name']} dropped to ${new_price:.2f}. "
                    f"Your ${user['bucket_balance']:.2f} PayPal Vacation Bucket covers it 100%!"
                ),
            }
        else:
            result = {
                "status": "WATCHING",
                "live_price": new_price,
                "alert_message": f"Current rate is ${new_price:.2f}. Keep saving!",
            }

    # Update state from workflow output
    if result.get("status") == "READY_TO_BOOK":
        user["last_known_price"] = result["bookable_price"]
        user["booking_status"] = "READY_TO_BOOK"

    return {"workflow_result": result, "state": user}


@app.post("/api/paypal/create-order")
async def api_create_paypal_order(payload: CreateOrderPayload):
    """Creates an APIMatic-grounded PayPal Order v2 for Bucket Top-Up or Hotel Checkout."""
    user = USER_STATE["demo_user"]
    is_booking = payload.order_type == "HOTEL_BOOKING"
    desc = (
        f"4-Night Stay: {user['pinned_hotel_name']}"
        if is_booking
        else "PayPal Vacation Goal Bucket Deposit"
    )
    order = create_vacation_order(
        amount_usd=payload.amount,
        description=desc,
        custom_id=payload.order_type,
        is_hotel_booking=is_booking,
    )
    return order


@app.post("/api/paypal/capture-order/{order_id}")
async def api_capture_paypal_order(order_id: str, order_type: str = "HOTEL_BOOKING"):
    """Captures the approved PayPal Sandbox Order and updates the Vacation Bucket."""
    capture_data = capture_vacation_order(order_id)
    user = USER_STATE["demo_user"]

    # Extract captured dollar value from PayPal response
    try:
        captured_val = float(
            capture_data["purchase_units"][0]["payments"]["captures"][0]["amount"]["value"]
        )
    except (KeyError, IndexError, ValueError):
        captured_val = user["last_known_price"] if order_type == "HOTEL_BOOKING" else 150.00

    if order_type == "BUCKET_TOPUP":
        user["bucket_balance"] = round(user["bucket_balance"] + captured_val, 2)
    else:
        user["bucket_balance"] = max(0.0, round(user["bucket_balance"] - captured_val, 2))
        user["booking_status"] = "PAID_VIA_PAYPAL"

    return {"capture": capture_data, "state": user}
    app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/")
async def serve_dashboard():
    """Serves the split-screen Vacation Concierge UI and Judge Controls."""
    return FileResponse("app/static/index.html")
