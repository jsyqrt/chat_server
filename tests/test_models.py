"""
Tests for the Appointment state machine.

Validates all stage transitions defined in AppointmentOps:
  Created → Confirmed → Paied → Delivered → Commented → Finished
  Commented → Disputed → DisputeHandled → Finished
  Created/Confirmed/Paied → Canceled
"""

import time
import uuid

import pytest

from zchat.db import db
from zchat.models import (
    Appointment,
    AppointmentOps,
    AppointmentStage,
    Balance,
    BalanceCNY,
    BalanceOps,
    Expert,
    ExpertOps,
    Newbie,
    NewbieOps,
    User,
    UserOps,
    SYSTEM_ACCOUNT,
    PLATFORM_DISCOUNT,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_user(app, phone="13800000001", nickname="test-user"):
    """Create and persist a User, returning the user id."""
    ops = UserOps(session=db.session)
    user_id = ops.get_or_create_user(phone_number=phone)
    ops.update_nickname(id=user_id, nickname=nickname)
    return user_id


def _create_appointment(app, expert_id, newbie_id, timestamp=None):
    """Create an Appointment in the Created stage, returning the appointment id."""
    if timestamp is None:
        timestamp = time.time() + 3600  # 1 hour in the future
    ops = AppointmentOps(session=db.session)
    apt_id = ops.create_appointment(
        type=0,  # basic
        expert=expert_id,
        newbie=newbie_id,
        timestamp=timestamp,
    )
    return apt_id


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestAppointmentStateMachine:
    """Happy-path transitions through the full state machine."""

    def _pay_happy_path(self, app, apt_id, newbie_id, expert_id):
        """Pay for an appointment (Confirmed → Paied)."""
        with app.app_context():
            ops = AppointmentOps(session=db.session)
            # Ensure user has balance
            balance_ops = BalanceOps(session=db.session)
            balance_ops.deposit(
                user=newbie_id, amount=2000, order_id=f"dep-{uuid.uuid4()}"
            )
            succeed = ops.newbie_pay(
                id=apt_id, newbie_id=newbie_id, price=500, order_id=f"order-{uuid.uuid4()}"
            )
            assert succeed, "Payment should succeed"
            apt = ops.get_appointment(apt_id)
            assert apt.stage == AppointmentStage.Paied.value
            return apt

    def test_created_to_confirmed_to_paid_to_delivered_to_commented_to_finished(
        self, app
    ):
        """Full happy-path: Created → Confirmed → Paied → Delivered → Commented → Finished."""
        with app.app_context():
            # Arrange
            expert_id = _create_user(app, "13800000001", "expert")
            newbie_id = _create_user(app, "13800000002", "newbie")
            apt_id = _create_appointment(app, expert_id, newbie_id)

            ops = AppointmentOps(session=db.session)

            # 1. Created (initial state)
            apt = ops.get_appointment(apt_id)
            assert apt.stage == AppointmentStage.Created.value

            # 2. Created → Confirmed (expert confirms)
            succeed = ops.expert_confirm(id=apt_id, expert_id=expert_id)
            assert succeed
            apt = ops.get_appointment(apt_id)
            assert apt.stage == AppointmentStage.Confirmed.value
            assert apt.confirmTimestamp is not None

            # 3. Confirmed → Paied (newbie pays)
            # Inject balance first
            balance_ops = BalanceOps(session=db.session)
            balance_ops.deposit(
                user=newbie_id, amount=2000, order_id=f"dep-{uuid.uuid4()}"
            )
            succeed = ops.newbie_pay(
                id=apt_id, newbie_id=newbie_id, price=500, order_id=f"order-{uuid.uuid4()}"
            )
            assert succeed
            apt = ops.get_appointment(apt_id)
            assert apt.stage == AppointmentStage.Paied.value
            assert apt.paymentPrice == 500

            # 4. Paied → Delivered (platform delivers the recording)
            succeed = ops.platform_deliver(
                id=apt_id, record_id="rec-001"
            )
            assert succeed
            apt = ops.get_appointment(apt_id)
            assert apt.stage == AppointmentStage.Delivered.value
            assert apt.appointmentMeetingRecordId == "rec-001"

            # 5. Delivered → Commented (newbie leaves a review)
            succeed = ops.newbie_comment(
                id=apt_id, newbie_id=newbie_id, content="Great session!", rating=5.0
            )
            assert succeed
            apt = ops.get_appointment(apt_id)
            assert apt.stage == AppointmentStage.Commented.value
            assert apt.commentContent == "Great session!"
            assert apt.commentRating == 5.0

            # 6. Commented → Finished (platform completes it)
            succeed = ops.platform_finish_it(id=apt_id)
            assert succeed
            apt = ops.get_appointment(apt_id)
            assert apt.stage == AppointmentStage.Finished.value
            assert apt.finishTimestamp is not None

    def test_created_to_confirmed_to_paid_to_canceled(self, app):
        """Newbie can cancel a paid appointment before the scheduled time and get refunded."""
        with app.app_context():
            expert_id = _create_user(app, "13800000010", "expert")
            newbie_id = _create_user(app, "13800000011", "newbie")
            apt_id = _create_appointment(app, expert_id, newbie_id, time.time() + 7200)

            ops = AppointmentOps(session=db.session)

            # Confirm
            ops.expert_confirm(id=apt_id, expert_id=expert_id)

            # Pay
            balance_ops = BalanceOps(session=db.session)
            balance_ops.deposit(
                user=newbie_id, amount=2000, order_id=f"dep-{uuid.uuid4()}"
            )
            ops.newbie_pay(
                id=apt_id, newbie_id=newbie_id, price=500, order_id=f"order-{uuid.uuid4()}"
            )

            # Cancel (should succeed because appointment is in the future)
            succeed = ops.newbie_cancel(id=apt_id, newbie_id=newbie_id)
            assert succeed
            apt = ops.get_appointment(apt_id)
            assert apt.stage == AppointmentStage.Canceled.value
            assert apt.finishTimestamp is not None

    def test_created_to_canceled(self, app):
        """Newbie can cancel before any confirmation."""
        with app.app_context():
            expert_id = _create_user(app, "13800000020", "expert")
            newbie_id = _create_user(app, "13800000021", "newbie")
            apt_id = _create_appointment(app, expert_id, newbie_id, time.time() + 7200)

            ops = AppointmentOps(session=db.session)
            succeed = ops.newbie_cancel(id=apt_id, newbie_id=newbie_id)
            assert succeed
            apt = ops.get_appointment(apt_id)
            assert apt.stage == AppointmentStage.Canceled.value

    def test_invalid_transition_returns_false(self, app):
        """Confirming an already-confirmed appointment returns False."""
        with app.app_context():
            expert_id = _create_user(app, "13800000030", "expert")
            newbie_id = _create_user(app, "13800000031", "newbie")
            apt_id = _create_appointment(app, expert_id, newbie_id)

            ops = AppointmentOps(session=db.session)

            # First confirm works
            assert ops.expert_confirm(id=apt_id, expert_id=expert_id)

            # Second confirm should fail
            assert not ops.expert_confirm(id=apt_id, expert_id=expert_id)

    def test_unauthorized_user_cannot_confirm(self, app):
        """A user who is not the expert cannot confirm the appointment."""
        with app.app_context():
            expert_id = _create_user(app, "13800000040", "expert")
            newbie_id = _create_user(app, "13800000041", "newbie")
            imposter_id = _create_user(app, "13800000042", "imposter")
            apt_id = _create_appointment(app, expert_id, newbie_id)

            ops = AppointmentOps(session=db.session)
            succeed = ops.expert_confirm(id=apt_id, expert_id=imposter_id)
            assert not succeed, "Imposter should not be able to confirm"

    def test_unauthorized_user_cannot_pay(self, app):
        """A user who is not the newbie cannot pay."""
        with app.app_context():
            expert_id = _create_user(app, "13800000050", "expert")
            newbie_id = _create_user(app, "13800000051", "newbie")
            imposter_id = _create_user(app, "13800000052", "imposter")
            apt_id = _create_appointment(app, expert_id, newbie_id)

            ops = AppointmentOps(session=db.session)
            ops.expert_confirm(id=apt_id, expert_id=expert_id)

            succeed = ops.newbie_pay(
                id=apt_id, newbie_id=imposter_id, price=500, order_id="order-001"
            )
            assert not succeed, "Imposter should not be able to pay"

    def test_cancel_after_appointment_time_fails(self, app):
        """Cancelling after the scheduled time should fail."""
        with app.app_context():
            expert_id = _create_user(app, "13800000060", "expert")
            newbie_id = _create_user(app, "13800000061", "newbie")
            past_time = time.time() - 3600  # 1 hour ago
            apt_id = _create_appointment(app, expert_id, newbie_id, past_time)

            ops = AppointmentOps(session=db.session)
            succeed = ops.newbie_cancel(id=apt_id, newbie_id=newbie_id)
            assert not succeed, "Should not be able to cancel after appointment time"


class TestAppointmentDisputeFlow:
    """Dispute handling: Commented → Disputed → DisputeHandled → Finished."""

    def _setup_to_commented(self, app):
        """Create an appointment and advance it to Commented stage."""
        expert_id = _create_user(app, "13800000100", "expert-d")
        newbie_id = _create_user(app, "13800000101", "newbie-d")
        apt_id = _create_appointment(app, expert_id, newbie_id)

        ops = AppointmentOps(session=db.session)
        ops.expert_confirm(id=apt_id, expert_id=expert_id)

        balance_ops = BalanceOps(session=db.session)
        balance_ops.deposit(
            user=newbie_id, amount=2000, order_id=f"dep-{uuid.uuid4()}"
        )
        ops.newbie_pay(
            id=apt_id, newbie_id=newbie_id, price=500, order_id=f"order-{uuid.uuid4()}"
        )
        ops.platform_deliver(id=apt_id, record_id="rec-d-001")
        ops.newbie_comment(
            id=apt_id, newbie_id=newbie_id, content="Not satisfied", rating=2.0
        )
        return apt_id, expert_id, newbie_id, ops

    def test_dispute_full_flow_agree_with_newbie(self, app):
        """Commented → Disputed → DisputeHandled (agree) → Finished (refund)."""
        with app.app_context():
            apt_id, expert_id, newbie_id, ops = self._setup_to_commented(app)

            # Newbie disputes
            succeed = ops.newbie_dispute(
                id=apt_id, newbie_id=newbie_id, content="Service was poor"
            )
            assert succeed
            apt = ops.get_appointment(apt_id)
            assert apt.stage == AppointmentStage.Disputed.value
            assert apt.disputeContent == "Service was poor"

            # Platform handles: agree with newbie → refund
            succeed = ops.platform_handle_dispute(
                id=apt_id, agree=True, content="Refund issued"
            )
            assert succeed
            apt = ops.get_appointment(apt_id)
            assert apt.stage == AppointmentStage.DisputeHandled.value
            assert apt.disputeHandleAgree == 1

            # Finish (refund path)
            succeed = ops.platform_finish_it(id=apt_id)
            assert succeed
            apt = ops.get_appointment(apt_id)
            assert apt.stage == AppointmentStage.Finished.value

    def test_dispute_full_flow_deny_with_newbie(self, app):
        """Commented → Disputed → DisputeHandled (deny) → Finished (pay expert)."""
        with app.app_context():
            apt_id, expert_id, newbie_id, ops = self._setup_to_commented(app)

            # Newbie disputes
            ops.newbie_dispute(
                id=apt_id, newbie_id=newbie_id, content="Not happy"
            )

            # Platform handles: deny dispute → pay expert
            ops.platform_handle_dispute(
                id=apt_id, agree=False, content="Service was delivered as agreed"
            )
            apt = ops.get_appointment(apt_id)
            assert apt.disputeHandleAgree == 0

            # Finish (unlock expert payment path)
            succeed = ops.platform_finish_it(id=apt_id)
            assert succeed
            apt = ops.get_appointment(apt_id)
            assert apt.stage == AppointmentStage.Finished.value


class TestUserOperations:
    """User creation, retrieval, and updates."""

    def test_get_or_create_user(self, app):
        """A new phone number creates a user; the same phone returns the existing user."""
        with app.app_context():
            ops = UserOps(session=db.session)
            uid1 = ops.get_or_create_user(phone_number="13900000001")
            uid2 = ops.get_or_create_user(phone_number="13900000001")
            assert uid1 == uid2, "Same phone should return same user_id"
            assert uid1 is not None

    def test_update_nickname(self, app):
        """Updating a user's nickname persists the change."""
        with app.app_context():
            ops = UserOps(session=db.session)
            uid = ops.get_or_create_user(phone_number="13900000002")
            assert ops.update_nickname(id=uid, nickname="NewName")
            user = ops.get_one(id=uid)
            assert user.nickname == "NewName"

    def test_get_all_users(self, app):
        """get_all returns list of user dicts."""
        with app.app_context():
            ops = UserOps(session=db.session)
            ops.get_or_create_user(phone_number="13900000003")
            ops.get_or_create_user(phone_number="13900000004")
            all_users = ops.get_all()
            assert len(all_users) >= 2


class TestBalanceOperations:
    """Balance deposit, transfer, and withdrawal."""

    def test_deposit_and_balance(self, app):
        """Depositing funds increases the user's balance."""
        with app.app_context():
            ops = UserOps(session=db.session)
            uid = ops.get_or_create_user(phone_number="13900001000")

            balance_ops = BalanceOps(session=db.session)
            succeed = balance_ops.deposit(
                user=uid, amount=1000, order_id="dep-test-001"
            )
            assert succeed

            bal = balance_ops.balance_of(user_id=uid)
            assert bal["balance"] == 1000

    def test_withdraw(self, app):
        """Withdrawing reduces balance."""
        with app.app_context():
            ops = UserOps(session=db.session)
            uid = ops.get_or_create_user(phone_number="13900001001")

            balance_ops = BalanceOps(session=db.session)
            balance_ops.deposit(user=uid, amount=1000, order_id="dep-test-002")
            succeed = balance_ops.withdraw(
                user=uid, amount=300, order_id="wd-test-001"
            )
            assert succeed

            bal = balance_ops.balance_of(user_id=uid)
            assert bal["balance"] == pytest.approx(700)

    def test_transfer_between_users(self, app):
        """Transfer moves balance with platform discount."""
        with app.app_context():
            ops = UserOps(session=db.session)
            from_uid = ops.get_or_create_user(phone_number="13900001002")
            to_uid = ops.get_or_create_user(phone_number="13900001003")

            balance_ops = BalanceOps(session=db.session)
            balance_ops.deposit(user=from_uid, amount=1000, order_id="dep-test-003")

            succeed = balance_ops.transfer(
                from_user=from_uid,
                to_user=to_uid,
                amount=500,
                order_id="tx-test-001",
            )
            assert succeed

            from_bal = balance_ops.balance_of(user_id=from_uid)
            to_bal = balance_ops.balance_of(user_id=to_uid)

            assert from_bal["balance"] == pytest.approx(500)
            assert to_bal["balance_locking"] == pytest.approx(500 * PLATFORM_DISCOUNT)
