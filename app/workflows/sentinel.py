import random
from render import Retry, TaskContext, Workflows

# Initialize the Render Workflows application
app = Workflows()

# Mock catalog of trademark-safe boutique hotels for hackathon compliance
HOTEL_CATALOG = {
    "HTL-NASH-01": {
        "name": "The Cumberland Boutique Hotel – Downtown Nashville",
        "nights": 4,
        "base_total_usd": 1180.00,
    },
    "HTL-MTL-02": {
        "name": "Le Vieux-Port Loft Suites – Old Montreal",
        "nights": 4,
        "base_total_usd": 1240.00,
    },
}


@app.task(
    retry=Retry(
        max_retries=3,
        wait_duration_ms=1000,
        backoff_scaling=1.5,
    )
)
def fetch_live_hotel_rate(
    ctx: TaskContext, hotel_id: str, simulate_drop: bool = False
) -> dict:
    """
    Task 1: Queries current hotel pricing (including taxes/fees).
    When a judge clicks 'Simulate Price Drop', applies a 20% flash discount.
    """
    hotel = HOTEL_CATALOG.get(hotel_id, HOTEL_CATALOG["HTL-NASH-01"])
    base_price = hotel["base_total_usd"]

    if simulate_drop:
        # Drop price by ~20% so it crosses below a $1,000 Vacation Bucket
        live_price = round(base_price * 0.8135, 2)  # e.g., $1,180 -> $960.00
    else:
        # Slight normal market fluctuation
        live_price = round(base_price + random.uniform(-10.0, 15.0), 2)

    return {
        "hotel_id": hotel_id,
        "hotel_name": hotel["name"],
        "nights": hotel["nights"],
        "previous_price": base_price,
        "live_price": live_price,
        "discount_applied": simulate_drop,
    }


@app.task
def build_crossover_alert(
    ctx: TaskContext,
    user_id: str,
    pricing: dict,
    bucket_balance: float,
) -> dict:
    """
    Task 2: Triggered ONLY when bucket_balance is greater than or equal to live_price.
    Prepares the crossover payload so the UI can render the PayPal Checkout button.
    """
    leftover = round(bucket_balance - pricing["live_price"], 2)
    return {
        "status": "READY_TO_BOOK",
        "user_id": user_id,
        "hotel_id": pricing["hotel_id"],
        "hotel_name": pricing["hotel_name"],
        "nights": pricing["nights"],
        "bookable_price": pricing["live_price"],
        "bucket_balance": bucket_balance,
        "leftover_balance": leftover,
        "alert_message": (
            f"Crossover Alert! {pricing['hotel_name']} ({pricing['nights']} nights) "
            f"just dropped from ${pricing['previous_price']:.2f} to "
            f"${pricing['live_price']:.2f}. Your ${bucket_balance:.2f} PayPal "
            f"Vacation Bucket covers 100% of this stay with ${leftover:.2f} to spare!"
        ),
    }


@app.task
async def evaluate_pinned_trip(
    ctx: TaskContext,
    user_id: str,
    hotel_id: str,
    bucket_balance: float,
    simulate_drop: bool = False,
) -> dict:
    """
    Parent Orchestrator Task: Chains rate fetching and crossover verification.
    """
    # Step 1: Run child task to fetch the latest hotel rate
    pricing = await ctx.run(fetch_live_hotel_rate, hotel_id, simulate_drop)

    # Step 2: Compare user's PayPal Vacation Bucket against the live rate
    if bucket_balance >= pricing["live_price"]:
        # Step 3: Chain the alert builder task if funds cover the trip
        return await ctx.run(
            build_crossover_alert, user_id, pricing, bucket_balance
        )

    shortfall = round(pricing["live_price"] - bucket_balance, 2)
    return {
        "status": "WATCHING",
        "user_id": user_id,
        "hotel_id": hotel_id,
        "hotel_name": pricing["hotel_name"],
        "live_price": pricing["live_price"],
        "bucket_balance": bucket_balance,
        "shortfall": shortfall,
        "alert_message": (
            f"Still watching {pricing['hotel_name']}: currently ${pricing['live_price']:.2f} "
            f"(${shortfall:.2f} away from your ${bucket_balance:.2f} bucket)."
        ),
    }


if __name__ == "__main__":
    # Required entry point for Render Workflows registration and execution
    app.start()
