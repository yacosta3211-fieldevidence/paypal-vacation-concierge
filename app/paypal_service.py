import os
from dotenv import load_dotenv
from paypalserversdk.configuration import Environment
from paypalserversdk.http.auth.o_auth_2 import ClientCredentialsAuthCredentials
from paypalserversdk.paypal_serversdk_client import PaypalServersdkClient
from paypalserversdk.models.order_request import OrderRequest
from paypalserversdk.models.checkout_payment_intent import CheckoutPaymentIntent
from paypalserversdk.models.purchase_unit_request import PurchaseUnitRequest
from paypalserversdk.models.amount_with_breakdown import AmountWithBreakdown
from paypalserversdk.models.amount_breakdown import AmountBreakdown
from paypalserversdk.models.money import Money
from paypalserversdk.models.item import Item
from paypalserversdk.models.item_category import ItemCategory
from paypalserversdk.api_helper import ApiHelper

load_dotenv()


def get_paypal_client() -> PaypalServersdkClient:
    """Initializes the PayPal Sandbox client using OAuth 2.0 Client Credentials."""
    return PaypalServersdkClient(
        client_credentials_auth_credentials=ClientCredentialsAuthCredentials(
            o_auth_client_id=os.getenv("PAYPAL_CLIENT_ID", ""),
            o_auth_client_secret=os.getenv("PAYPAL_CLIENT_SECRET", ""),
        ),
        environment=Environment.SANDBOX,
    )


def create_vacation_order(
    amount_usd: float,
    description: str,
    custom_id: str,
    is_hotel_booking: bool = False,
) -> dict:
    """
    Creates a PayPal Orders v2 order grounded by APIMatic's PayPal Server SDK models.
    Used for both:
      1. Funding the Vacation Goal Bucket (is_hotel_booking=False)
      2. Paying for the Pinned Hotel upon a Crossover Alert (is_hotel_booking=True)
    """
    client = get_paypal_client()
    orders_controller = client.orders

    if is_hotel_booking:
        # Split into 88% base room rate and 12% taxes for a realistic itemized checkout
        item_total = round(amount_usd * 0.88, 2)
        tax_total = round(amount_usd - item_total, 2)

        amount_obj = AmountWithBreakdown(
            currency_code="USD",
            value=f"{amount_usd:.2f}",
            breakdown=AmountBreakdown(
                item_total=Money(currency_code="USD", value=f"{item_total:.2f}"),
                tax_total=Money(currency_code="USD", value=f"{tax_total:.2f}"),
            ),
        )
        items = [
            Item(
                name=description[:120],
                quantity="1",
                category=ItemCategory.DIGITAL_GOODS,
                unit_amount=Money(currency_code="USD", value=f"{item_total:.2f}"),
            )
        ]
    else:
        amount_obj = AmountWithBreakdown(
            currency_code="USD",
            value=f"{amount_usd:.2f}",
        )
        items = None

    order_body = OrderRequest(
        intent=CheckoutPaymentIntent.CAPTURE,
        purchase_units=[
            PurchaseUnitRequest(
                reference_id=custom_id,
                custom_id=custom_id,
                description=description[:127],
                amount=amount_obj,
                items=items,
            )
        ],
    )

    response = orders_controller.create_order({"body": order_body})
    return ApiHelper.json_deserialize(ApiHelper.json_serialize(response.body))


def capture_vacation_order(order_id: str) -> dict:
    """Captures an approved PayPal Sandbox Order v2 by ID."""
    client = get_paypal_client()
    response = client.orders.capture_order({"id": order_id})
    return ApiHelper.json_deserialize(ApiHelper.json_serialize(response.body))
