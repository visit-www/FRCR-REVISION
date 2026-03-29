"""
Stripe Payment Routes — Checkout, Plan Changes, Webhooks
Uses Stripe Checkout Sessions (hosted) for PCI compliance.
Webhook is the single source of truth for subscription state changes.

Plan-change rules:
  Free → Standard/Elite:  Checkout Session (new subscription)
  Standard → Elite:       Subscription.modify + proration + billing_cycle_anchor='now'
  Elite → Standard:       cancel_at_period_end, auto-create Standard in webhook
  Any → Free:             cancel_at_period_end, downgrade in webhook
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

TIER_RANK = {'free': 0, 'standard': 1, 'elite': 2}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ensure_stripe_customer(user):
    """Return existing stripe_customer_id or create a new Stripe Customer.
    Validates existing ID still works (handles live/test mode mismatch)."""
    if user.stripe_customer_id:
        try:
            cust = stripe.Customer.retrieve(user.stripe_customer_id)
            if getattr(cust, 'deleted', False):
                raise stripe.InvalidRequestError('Customer deleted', param=None)
            return user.stripe_customer_id
        except (stripe.InvalidRequestError, stripe.StripeError):
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


def _get_active_subscription(customer_id):
    """Find the customer's active subscription. Returns (sub, item_id) or (None, None)."""
    subs = stripe.Subscription.list(customer=customer_id, status='active', limit=1)
    subs_data = _get(subs, 'data', [])
    if not subs_data:
        return None, None

    sub = subs_data[0]
    items_wrapper = _get(sub, 'items', {})
    items_data = _get(items_wrapper, 'data', [])
    if not items_data:
        return sub, None

    return sub, _get(items_data[0], 'id')


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@stripe_bp.route('/create-checkout-session', methods=['POST'])
@login_required
def create_checkout_session():
    """Create a Stripe Checkout Session — free users subscribing for the first time."""
    if not stripe.api_key:
        return jsonify({'error': 'Payments not configured'}), 503

    data = request.get_json(silent=True) or {}
    plan = data.get('plan', 'standard')
    price_id = PRICE_IDS.get(plan)
    if not price_id:
        return jsonify({'error': f'Unknown plan: {plan}'}), 400

    current_tier = getattr(current_user, 'subscription_tier', 'free') or 'free'
    if current_tier == plan:
        return jsonify({'error': f'You are already on the {plan.capitalize()} plan.'}), 400

    # Paid users must use change-plan flow
    if current_tier in ('standard', 'elite'):
        return jsonify({'error': 'Use plan change for existing subscribers', 'use_change': True}), 400

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


@stripe_bp.route('/change-plan', methods=['POST'])
@login_required
def change_plan():
    """Switch between plans. Upgrades are immediate (prorated). Downgrades/cancels happen at period end."""
    if not stripe.api_key:
        return jsonify({'error': 'Payments not configured'}), 503

    data = request.get_json(silent=True) or {}
    new_plan = data.get('plan', '')
    if new_plan not in TIER_RANK:
        return jsonify({'error': f'Unknown plan: {new_plan}'}), 400

    current_tier = getattr(current_user, 'subscription_tier', 'free') or 'free'
    if current_tier == new_plan:
        return jsonify({'error': f'You are already on the {new_plan.capitalize()} plan.'}), 400

    if current_tier not in ('standard', 'elite'):
        return jsonify({'error': 'No active subscription to change. Please subscribe first.'}), 400

    customer_id = current_user.stripe_customer_id
    if not customer_id:
        return jsonify({'error': 'No payment profile found'}), 400

    try:
        sub, sub_item_id = _get_active_subscription(customer_id)
        if not sub:
            return jsonify({'error': 'No active subscription found on Stripe'}), 404
        if not sub_item_id:
            return jsonify({'error': 'Subscription has no items'}), 500

        sub_id = _get(sub, 'id')
        current_rank = TIER_RANK.get(current_tier, 0)
        new_rank = TIER_RANK.get(new_plan, 0)

        # ── UPGRADE (Standard → Elite) ──
        if new_rank > current_rank:
            new_price_id = PRICE_IDS.get(new_plan)
            if not new_price_id:
                return jsonify({'error': f'Price not configured for {new_plan}'}), 500

            # If sub has cancel_at_period_end (pending downgrade), undo it first
            if _get(sub, 'cancel_at_period_end'):
                stripe.Subscription.modify(sub_id, cancel_at_period_end=False)

            # Modify subscription: immediate upgrade, new billing cycle starts today
            updated_sub = stripe.Subscription.modify(
                sub_id,
                items=[{
                    'id': sub_item_id,
                    'price': new_price_id,
                }],
                proration_behavior='create_prorations',
                billing_cycle_anchor='now',
            )

            # Immediate DB update for responsive UI (webhook will also fire)
            from access_control import upgrade_to_paid
            end_date = _subscription_end_from_event(updated_sub)
            upgrade_to_paid(current_user, end_date, new_plan)

            logger.info(f"User {current_user.id} upgraded {current_tier} → {new_plan} (prorated, new cycle)")
            return jsonify({'success': True, 'new_plan': new_plan, 'redirect': '/pricing?payment=success'})

        # ── DOWNGRADE (Elite → Standard or Any → Free) ──
        else:
            # Set cancel_at_period_end so current plan stays active until end of period
            stripe.Subscription.modify(sub_id, cancel_at_period_end=True)

            # Record the pending change in our DB
            end_date = _subscription_end_from_event(sub)
            current_user.pending_subscription_tier = new_plan
            current_user.pending_change_effective_date = end_date
            db.session.commit()

            effective_date = end_date.strftime('%d %b %Y')
            logger.info(f"User {current_user.id} scheduled downgrade {current_tier} → {new_plan} (effective {effective_date})")
            return jsonify({
                'success': True,
                'scheduled': True,
                'new_plan': new_plan,
                'effective_date': effective_date,
                'redirect': '/pricing?payment=scheduled',
            })

    except stripe.StripeError as e:
        logger.error(f"Stripe change-plan error for user {current_user.id}: {e}", exc_info=True)
        return jsonify({'error': f'Could not change plan: {str(e)}'}), 500


@stripe_bp.route('/preview-change', methods=['POST'])
@login_required
def preview_change():
    """Preview cost/timing for a plan change before user confirms."""
    if not stripe.api_key:
        return jsonify({'error': 'Payments not configured'}), 503

    data = request.get_json(silent=True) or {}
    new_plan = data.get('plan', '')
    if new_plan not in TIER_RANK:
        return jsonify({'error': f'Unknown plan: {new_plan}'}), 400

    current_tier = getattr(current_user, 'subscription_tier', 'free') or 'free'
    if current_tier not in ('standard', 'elite'):
        return jsonify({'error': 'No active subscription'}), 400

    customer_id = current_user.stripe_customer_id
    if not customer_id:
        return jsonify({'error': 'No payment profile found'}), 400

    try:
        sub, sub_item_id = _get_active_subscription(customer_id)
        if not sub:
            return jsonify({'error': 'No active subscription found'}), 404

        current_rank = TIER_RANK.get(current_tier, 0)
        new_rank = TIER_RANK.get(new_plan, 0)

        if new_rank > current_rank:
            # UPGRADE preview — get prorated invoice
            new_price_id = PRICE_IDS.get(new_plan)
            if not new_price_id:
                return jsonify({'error': f'Price not configured for {new_plan}'}), 500

            upcoming = stripe.Invoice.upcoming(
                customer=customer_id,
                subscription=_get(sub, 'id'),
                subscription_items=[{
                    'id': sub_item_id,
                    'price': new_price_id,
                }],
                subscription_proration_behavior='create_prorations',
                subscription_billing_cycle_anchor='now',
            )

            amount_due = _get(upcoming, 'amount_due', 0) / 100  # pence → pounds
            return jsonify({
                'direction': 'upgrade',
                'amount_due': f'{amount_due:.2f}',
                'currency': _get(upcoming, 'currency', 'gbp').upper(),
                'new_plan': new_plan,
            })

        else:
            # DOWNGRADE/CANCEL preview — just show effective date
            end_date = _subscription_end_from_event(sub)
            return jsonify({
                'direction': 'downgrade',
                'effective_date': end_date.strftime('%d %b %Y'),
                'current_plan': current_tier,
                'new_plan': new_plan,
            })

    except stripe.StripeError as e:
        logger.error(f"Preview change error for user {current_user.id}: {e}", exc_info=True)
        return jsonify({'error': f'Could not preview: {str(e)}'}), 500


@stripe_bp.route('/cancel-pending-change', methods=['POST'])
@login_required
def cancel_pending_change():
    """Undo a scheduled downgrade/cancellation — keep current plan."""
    if not stripe.api_key:
        return jsonify({'error': 'Payments not configured'}), 503

    if not current_user.pending_subscription_tier:
        return jsonify({'error': 'No pending plan change to cancel'}), 400

    customer_id = current_user.stripe_customer_id
    if not customer_id:
        return jsonify({'error': 'No payment profile found'}), 400

    try:
        sub, _ = _get_active_subscription(customer_id)
        if not sub:
            return jsonify({'error': 'No active subscription found'}), 404

        # Undo cancel_at_period_end
        if _get(sub, 'cancel_at_period_end'):
            stripe.Subscription.modify(_get(sub, 'id'), cancel_at_period_end=False)

        # Clear pending fields
        current_user.pending_subscription_tier = None
        current_user.pending_change_effective_date = None
        db.session.commit()

        logger.info(f"User {current_user.id} cancelled pending plan change, keeping {current_user.subscription_tier}")
        return jsonify({'success': True, 'current_plan': current_user.subscription_tier})

    except stripe.StripeError as e:
        logger.error(f"Cancel pending change error for user {current_user.id}: {e}", exc_info=True)
        return jsonify({'error': f'Could not cancel: {str(e)}'}), 500


@stripe_bp.route('/create-portal-session', methods=['POST'])
@login_required
def create_portal_session():
    """Create a Stripe Customer Portal session for billing/payment method management."""
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
    """customer.subscription.updated — renewal, plan change, or going past_due.

    Key logic:
    - If cancel_at_period_end=True AND status='active': subscription is winding down.
      DON'T change the tier yet. Set pending fields if not already set (handles Stripe Portal cancellations).
    - If cancel_at_period_end=False AND status='active': normal active subscription.
      Apply upgrade_to_paid and clear any pending fields.
    """
    from access_control import upgrade_to_paid
    from models import PaymentStatus

    customer_id = _get(sub_obj, 'customer')
    user = _find_user_by_customer_id(customer_id)
    if not user:
        logger.warning(f"subscription.updated: no user for customer {customer_id}")
        return

    status = _get(sub_obj, 'status')
    cancel_at_period_end = _get(sub_obj, 'cancel_at_period_end', False)

    if status == 'active':
        if cancel_at_period_end:
            # Subscription is scheduled to cancel — keep current tier active
            # Set pending fields if not already set (e.g. Stripe Portal cancellation)
            if not user.pending_subscription_tier:
                end_date = _subscription_end_from_event(sub_obj)
                user.pending_subscription_tier = 'free'
                user.pending_change_effective_date = end_date
                db.session.commit()
                logger.info(f"User {user.id} subscription cancel_at_period_end detected, pending free on {end_date}")
        else:
            # Normal active subscription — apply tier
            end_date = _subscription_end_from_event(sub_obj)
            tier = _tier_from_subscription(sub_obj)
            upgrade_to_paid(user, end_date, tier)
            logger.info(f"User {user.id} subscription renewed/changed to {tier} (ends {end_date})")

    elif status == 'past_due':
        user.payment_status = PaymentStatus.PAST_DUE
        db.session.commit()
        logger.info(f"User {user.id} subscription past_due")


def _handle_subscription_deleted(sub_obj):
    """customer.subscription.deleted — subscription cancelled/expired.

    Check pending_subscription_tier:
    - 'standard': auto-create a new Standard subscription, upgrade user
    - 'free' or None: downgrade to free
    """
    from access_control import downgrade_to_free, upgrade_to_paid

    customer_id = _get(sub_obj, 'customer')
    user = _find_user_by_customer_id(customer_id)
    if not user:
        logger.warning(f"subscription.deleted: no user for customer {customer_id}")
        return

    pending_tier = user.pending_subscription_tier

    # Elite → Standard: auto-create a Standard subscription
    if pending_tier == 'standard':
        standard_price_id = PRICE_IDS.get('standard')
        if standard_price_id:
            try:
                new_sub = stripe.Subscription.create(
                    customer=customer_id,
                    items=[{'price': standard_price_id}],
                    metadata={'user_id': str(user.id), 'auto_downgrade': 'elite_to_standard'},
                )
                end_date = _subscription_end_from_event(new_sub)
                upgrade_to_paid(user, end_date, 'standard')
                logger.info(f"User {user.id} auto-created Standard sub after Elite expiry (ends {end_date})")
                return
            except stripe.StripeError as e:
                logger.error(f"Failed to auto-create Standard sub for user {user.id}: {e}")
                # Fall through to downgrade_to_free as safety net

    # Check if customer still has other active subscriptions (safety check)
    try:
        active_subs = stripe.Subscription.list(customer=customer_id, status='active', limit=1)
        subs_data = _get(active_subs, 'data', [])
        if subs_data:
            logger.info(f"subscription.deleted for user {user.id} but other active subs exist — skipping downgrade")
            return
    except Exception as e:
        logger.warning(f"Could not check active subs for user {user.id}: {e}")

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
