"""
Stripe Payment Routes — Checkout, Customer Portal, Webhooks
Uses Stripe Checkout Sessions (hosted) for PCI compliance.
Webhook is the single source of truth for subscription state changes.
"""

import os
import logging
import stripe
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, redirect
from flask_login import login_required, current_user
from models import db, User

logger = logging.getLogger(__name__)

stripe_bp = Blueprint('stripe', __name__, url_prefix='/stripe')

# ---------------------------------------------------------------------------
# Config — read once at import; Stripe library uses module-level api_key
# ---------------------------------------------------------------------------
stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')
STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY', '')
STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET', '')

PRICE_IDS = {
    'standard': os.environ.get('STRIPE_STANDARD_PRICE_ID', ''),
    'elite':    os.environ.get('STRIPE_ELITE_PRICE_ID', ''),
}

BASE_URL = os.environ.get('BASE_URL', 'https://www.radinsights.xyz')


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ensure_stripe_customer(user):
    """Return existing stripe_customer_id or create a new Stripe Customer.
    Validates existing ID still works (handles live/test mode mismatch)."""
    if user.stripe_customer_id:
        try:
            stripe.Customer.retrieve(user.stripe_customer_id)
            return user.stripe_customer_id
        except stripe.InvalidRequestError:
            # Customer ID from different mode (live vs test) — clear and re-create
            logger.warning(f"Stripe customer {user.stripe_customer_id} invalid, re-creating for user {user.id}")
            user.stripe_customer_id = None
            db.session.commit()

    try:
        customer = stripe.Customer.create(
            email=user.email,
            name=user.full_name or user.email,
            metadata={'user_id': str(user.id)},
        )
        user.stripe_customer_id = customer.id
        db.session.commit()
        logger.info(f"Created Stripe customer {customer.id} for user {user.id}")
        return customer.id
    except Exception as e:
        logger.error(f"Failed to create Stripe customer for user {user.id}: {e}")
        return None


def _get(obj, key, default=None):
    """Get a value from a dict or Stripe object (SDK v8+ uses attribute access)."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _subscription_end_from_event(subscription_obj):
    """Extract subscription end date from a Stripe subscription object."""
    ts = _get(subscription_obj, 'current_period_end')
    if ts:
        return datetime.utcfromtimestamp(ts)
    return datetime.utcnow() + timedelta(days=30)


def _tier_from_subscription(subscription_obj):
    """Determine our tier name from Stripe subscription items."""
    items_wrapper = _get(subscription_obj, 'items', {})
    items_data = _get(items_wrapper, 'data', [])
    if not items_data:
        return 'standard'
    first_item = items_data[0]
    price_obj = _get(first_item, 'price', {})
    price_id = _get(price_obj, 'id', '')
    if price_id == PRICE_IDS.get('elite'):
        return 'elite'
    return 'standard'


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@stripe_bp.route('/create-checkout-session', methods=['POST'])
@login_required
def create_checkout_session():
    """Create a Stripe Checkout Session and return the URL."""
    if not stripe.api_key:
        return jsonify({'error': 'Payments not configured'}), 503

    data = request.get_json(silent=True) or {}
    plan = data.get('plan', 'standard')
    price_id = PRICE_IDS.get(plan)
    if not price_id:
        return jsonify({'error': f'Unknown plan: {plan}'}), 400

    try:
        customer_id = _ensure_stripe_customer(current_user)
    except Exception as e:
        logger.error(f"Stripe ensure_customer error: {e}", exc_info=True)
        return jsonify({'error': f'Customer error: {str(e)}'}), 500

    if not customer_id:
        return jsonify({'error': 'Could not create payment profile'}), 500

    try:
        session = stripe.checkout.Session.create(
            customer=customer_id,
            mode='subscription',
            line_items=[{'price': price_id, 'quantity': 1}],
            success_url=f'{BASE_URL}/stripe/success?session_id={{CHECKOUT_SESSION_ID}}',
            cancel_url=f'{BASE_URL}/stripe/cancel',
            metadata={'user_id': str(current_user.id), 'plan': plan},
            allow_promotion_codes=True,
        )
        return jsonify({'checkout_url': session.url})
    except Exception as e:
        logger.error(f"Stripe checkout error: {e}", exc_info=True)
        return jsonify({'error': f'Checkout error: {str(e)}'}), 500


@stripe_bp.route('/success')
@login_required
def checkout_success():
    """Post-checkout redirect. Actual upgrade happens via webhook."""
    return redirect('/pricing?payment=success')


@stripe_bp.route('/cancel')
@login_required
def checkout_cancel():
    """User cancelled checkout."""
    return redirect('/pricing?payment=cancelled')


@stripe_bp.route('/create-portal-session', methods=['POST'])
@login_required
def create_portal_session():
    """Create a Stripe Customer Portal session for subscription management."""
    if not stripe.api_key:
        return jsonify({'error': 'Payments not configured'}), 503

    if not current_user.stripe_customer_id:
        return jsonify({'error': 'No active subscription found', 'redirect': '/#pricing-section'}), 404

    try:
        session = stripe.billing_portal.Session.create(
            customer=current_user.stripe_customer_id,
            return_url=f'{BASE_URL}/auth/profile',
        )
        return jsonify({'portal_url': session.url})
    except stripe.StripeError as e:
        logger.error(f"Stripe portal error: {e}")
        return jsonify({'error': 'Could not open subscription management'}), 500


# ---------------------------------------------------------------------------
# Webhook — single source of truth for subscription state
# ---------------------------------------------------------------------------

@stripe_bp.route('/webhook', methods=['POST'])
def stripe_webhook():
    """Handle Stripe webhook events. No auth — verified by signature."""
    payload = request.get_data()
    sig_header = request.headers.get('Stripe-Signature', '')

    if not STRIPE_WEBHOOK_SECRET:
        logger.error("STRIPE_WEBHOOK_SECRET not configured")
        return jsonify({'error': 'Webhook not configured'}), 503

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except ValueError:
        logger.warning("Invalid webhook payload")
        return jsonify({'error': 'Invalid payload'}), 400
    except stripe.SignatureVerificationError:
        logger.warning("Invalid webhook signature")
        return jsonify({'error': 'Invalid signature'}), 400

    event_type = event['type']
    data_obj = event['data']['object']

    logger.info(f"Stripe webhook: {event_type}")

    try:
        if event_type == 'checkout.session.completed':
            _handle_checkout_completed(data_obj)
        elif event_type == 'customer.subscription.updated':
            _handle_subscription_updated(data_obj)
        elif event_type == 'customer.subscription.deleted':
            _handle_subscription_deleted(data_obj)
        elif event_type == 'invoice.payment_failed':
            _handle_payment_failed(data_obj)
    except Exception as e:
        logger.error(f"Webhook handler error for {event_type}: {e}", exc_info=True)
        # Return 200 so Stripe doesn't retry — include error detail for debugging
        return jsonify({'status': 'error logged', 'error': str(e)}), 200

    return jsonify({'status': 'ok'}), 200


# ---------------------------------------------------------------------------
# Webhook Handlers (idempotent)
# ---------------------------------------------------------------------------

def _find_user_by_customer_id(customer_id):
    """Look up user by stripe_customer_id."""
    if not customer_id:
        return None
    return User.query.filter_by(stripe_customer_id=customer_id).first()


def _handle_checkout_completed(session_obj):
    """checkout.session.completed — first successful payment."""
    from access_control import upgrade_to_paid

    customer_id = _get(session_obj, 'customer')
    user = _find_user_by_customer_id(customer_id)

    if not user:
        # Try metadata fallback
        metadata = _get(session_obj, 'metadata', {})
        user_id = _get(metadata, 'user_id')
        if user_id:
            user = db.session.get(User, int(user_id))
            if user and not user.stripe_customer_id:
                user.stripe_customer_id = customer_id
                db.session.commit()

    if not user:
        logger.error(f"checkout.session.completed: no user for customer {customer_id}")
        return

    # Retrieve the subscription to get period end and tier
    sub_id = _get(session_obj, 'subscription')
    if sub_id:
        sub = stripe.Subscription.retrieve(sub_id)
        end_date = _subscription_end_from_event(sub)
        tier = _tier_from_subscription(sub)
    else:
        end_date = datetime.utcnow() + timedelta(days=30)
        metadata = _get(session_obj, 'metadata', {})
        tier = _get(metadata, 'plan', 'standard')

    upgrade_to_paid(user, end_date, tier)
    logger.info(f"User {user.id} upgraded to {tier} via checkout (ends {end_date})")


def _handle_subscription_updated(sub_obj):
    """customer.subscription.updated — renewal, plan change, or going past_due."""
    from access_control import upgrade_to_paid
    from models import PaymentStatus

    customer_id = _get(sub_obj, 'customer')
    user = _find_user_by_customer_id(customer_id)
    if not user:
        logger.warning(f"subscription.updated: no user for customer {customer_id}")
        return

    status = _get(sub_obj, 'status')

    if status == 'active':
        end_date = _subscription_end_from_event(sub_obj)
        tier = _tier_from_subscription(sub_obj)
        upgrade_to_paid(user, end_date, tier)
        logger.info(f"User {user.id} subscription renewed/changed to {tier} (ends {end_date})")

    elif status == 'past_due':
        user.payment_status = PaymentStatus.PAST_DUE
        db.session.commit()
        logger.info(f"User {user.id} subscription past_due")


def _handle_subscription_deleted(sub_obj):
    """customer.subscription.deleted — subscription cancelled/expired."""
    from access_control import downgrade_to_free

    customer_id = _get(sub_obj, 'customer')
    user = _find_user_by_customer_id(customer_id)
    if not user:
        logger.warning(f"subscription.deleted: no user for customer {customer_id}")
        return

    downgrade_to_free(user)
    logger.info(f"User {user.id} downgraded to free (subscription deleted)")


def _handle_payment_failed(invoice_obj):
    """invoice.payment_failed — mark payment as past due."""
    from models import PaymentStatus

    customer_id = _get(invoice_obj, 'customer')
    user = _find_user_by_customer_id(customer_id)
    if not user:
        logger.warning(f"invoice.payment_failed: no user for customer {customer_id}")
        return

    user.payment_status = PaymentStatus.PAST_DUE
    db.session.commit()
    logger.info(f"User {user.id} payment failed — marked past_due")
