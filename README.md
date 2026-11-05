# paypal-vacation-concierge
# PayPal AI Vacation Concierge (paypal-vacation-concierge)

**Official Repository:** https://github.com/yacosta3211-fieldevidence/paypal-vacation-concierge

> **PayPal Developer Platform + AI Hackathon Project** — An autonomous FinTech & travel concierge that links a **PayPal Sandbox Goal Bucket**, **Venmo Social Splits**, and **PayPal Honey Travel Cashback** with **Google Gemini 2.5 Flash Function Calling** and Sponsor Tools (**Postman**, **Render Workflows**, **APIMatic**, and **AG Grid Ledger**).

---

## 1. Executive Summary & Problem Solved

Travelers typically save for vacations in disconnected accounts while hotel prices fluctuate daily. **PayPal AI Vacation Concierge (Vacation Vault AI)** unifies goal-based savings and travel checkout into a single closed-loop agentic system:
1. **Window Shop & Pin with Gemini 2.5 Flash:** Travelers ask natural-language questions (e.g., *"Can I afford Montreal right now, or should I pin it?"*). Gemini invokes deterministic tools (`get_vacation_bucket_status` and `search_and_pin_hotel`) to inspect live PayPal bucket funds and pin boutique hotels.
2. **Co-Fund via PayPal Orders v2, Venmo & PayPal Honey:** Travelers top up their Vacation Bucket using PayPal Sandbox Orders v2 (`BUCKET_TOPUP`), invite co-travelers via **Venmo Split**, and redeem **PayPal Honey Gold Cashback**.
3. **Autonomous Dual-Trigger Crossover Sentinel (Render Workflows):** A background sentinel task (`evaluate_pinned_trip`) evaluates both **bucket balance increases** and **live hotel price drops**. The exact moment `bucket_balance >= live_hotel_price`, the trip status transitions from `WATCHING` to `READY_TO_BOOK`.
4. **1-Click PayPal Orders v2 Capture:** Travelers complete checkout directly from their funded bucket via `POST /v2/checkout/orders` and `POST /v2/checkout/orders/{id}/capture`.

---

## 2. PayPal Developer Platform & Sponsor Tool Integrations

| Service / Sponsor Tool | Category | Implementation Details |
| :--- | :--- | :--- |
| **PayPal Orders v2 API** | Core PayPal Platform | Full OAuth2 (`POST /v1/oauth2/token`), Order Creation (`POST /v2/checkout/orders` with `intent: "CAPTURE"`), and Order Capture (`POST /v2/checkout/orders/{id}/capture`) supporting both `BUCKET_TOPUP` and `HOTEL_BOOKING`. |
| **Venmo** | PayPal Ecosystem | Interactive **Venmo Co-Traveler Bucket Split** allowing companions (`@alex-traveler`) to push split contributions directly into the shared Vacation Bucket. |
| **PayPal Honey** | PayPal Ecosystem | **Honey Travel Gold Cashback** integration that applies boutique hotel cashback (`+$45.00`) toward the user's pinned stay gap. |
| **Google Gemini 2.5 Flash** | Core AI Model | Grounded with live `VacationState` telemetry and deterministic function calling (`get_vacation_bucket_status`, `search_and_pin_hotel`) across **Nashville (`HTL-NASH-01`)** and **Old Montreal (`HTL-MTL-02`)**. |
| **Postman** | Select Sponsor Tool | Built-in **Postman Sandbox Runner** inside the web app + 1-click downloadable **Postman Collection v2.1 (`PayPal_Vacation_Concierge.postman_collection.json`)**. |
| **Render** | Select Sponsor Tool | **Render Workflows** task (`vacation-sentinel/evaluate_pinned_trip`) triggered on bucket top-ups or hotel rate drops to detect affordability crossovers. |
| **APIMatic** | Select Sponsor Tool | PayPal Server SDK schema grounding for type-safe `OrdersCreate` and `OrdersCapture` payloads. |

---

## 3. Step-by-Step Judge Walkthrough (Zero API Keys Required)

1. **Test via Postman Sandbox Studio:** Open the **Postman Sandbox Runner** tab at the top of the app, select `POST /v2/checkout/orders`, and click **Send Request in Postman Sandbox**.
2. **Chat with Gemini 2.5 Flash Concierge:** Ask *"Can I afford Montreal right now, or should I pin it?"* to watch `search_and_pin_hotel("montreal")` pin **Hôtel William Gray ($1,240.00)**.
3. **Simulate Funding (Trigger #1):** Click **+#1: Instant +$150 Auto-Save** or **Simulate +$100 Venmo Split** to increase the PayPal Vacation Bucket balance.
4. **Fire Render Sentinel (Trigger #2):** Click **+#2: Trigger Render Sentinel** to simulate an 18.65% boutique hotel price drop and trigger the **`READY_TO_BOOK`** crossover alert.
5. **Capture PayPal Order v2:** Click **Book Hotel Now** and **Complete Capture** in the PayPal Orders v2 Checkout panel.
