"""
Seed airpay tier plans (CN-007 launch pricing matrix).

Idempotent seed script — safe to run repeatedly. Creates/updates the Razorpay
PaymentGateway and the AirPlan rows for each Jeevit tier so Subscriptions can
reference a concrete plan.

Pricing mirrors apps/marketplace/migrations/0004_cn007_seed_pricing_plans.py
(the canonical CN-007 pricing source). The marketplace.PricingPlan table holds
the authoritative price matrix; AirPlan is the gateway-facing plan the payment
flow binds to. Both are kept in sync here.

Tier         | Phase       | Term     | Monthly effective | Total
-------------|-------------|----------|-------------------|----------
Companion    | —           | monthly  | ₹499              | ₹499/mo
Guardian     | —           | monthly  | ₹1,999            | ₹1,999/mo
Medical      | active      | 3-month  | ₹7,777            | ₹23,331
Medical      | active      | 9-month  | ₹6,666            | ₹59,994
Medical      | maintenance | monthly  | ₹4,444            | ₹4,444/mo
Alumni       | —           | monthly  | ₹0 (placeholder)  | inactive

AirPlan.billing_cycle only supports monthly/yearly, so multi-month medical
commitments are stored as monthly with the term encoded in metadata.

Usage:
    python manage.py seed_tier_plans
    python manage.py seed_tier_plans --gateway razorpay
    python manage.py seed_tier_plans --dry-run
"""

from django.core.management.base import BaseCommand
from django.db import transaction


# (plan_id, name, tier_level, price_rupees, billing_cycle, is_active, is_addon, metadata)
# plan_id is the stable natural key used for update_or_create.
TIER_PLANS = [
    (
        "companion_monthly",
        "Companion",
        "companion",
        499.0,
        "monthly",
        True,
        False,
        {
            "phase": None,
            "term": "monthly",
            "monthly_effective_paise": 49900,
            "total_paise": 49900,
        },
    ),
    (
        "guardian_monthly",
        "Guardian",
        "guardian",
        1999.0,
        "monthly",
        True,
        False,
        {
            "phase": None,
            "term": "monthly",
            "monthly_effective_paise": 199900,
            "total_paise": 199900,
        },
    ),
    (
        "medical_active_3m",
        "Medical (3-month)",
        "medical",
        7777.0,
        "monthly",
        True,
        False,
        {
            "phase": "active",
            "term": "3_month",
            "commitment_months": 3,
            "monthly_effective_paise": 777700,
            "total_paise": 2333100,
        },
    ),
    (
        "medical_active_9m",
        "Medical (9-month)",
        "medical",
        6666.0,
        "monthly",
        True,
        False,
        {
            "phase": "active",
            "term": "9_month",
            "commitment_months": 9,
            "monthly_effective_paise": 666600,
            "total_paise": 5999400,
        },
    ),
    (
        "medical_maintenance_monthly",
        "Medical Maintenance",
        "medical",
        4444.0,
        "monthly",
        True,
        False,
        {
            "phase": "maintenance",
            "term": "monthly",
            "monthly_effective_paise": 444400,
            "total_paise": 444400,
        },
    ),
    (
        "alumni_monthly",
        "Alumni",
        "alumni",
        0.0,
        "monthly",
        False,  # placeholder — not launched, no validated price
        False,
        {
            "phase": None,
            "term": "monthly",
            "placeholder": True,
        },
    ),
]

SEED_NOTE = "CN-007 launch seed — placeholder pending commercial validation"


class Command(BaseCommand):
    help = "Seed airpay tier plans (CN-007 launch pricing matrix). Idempotent."

    def add_arguments(self, parser):
        parser.add_argument(
            "--gateway",
            default="razorpay",
            choices=["razorpay", "stripe"],
            help="Payment gateway to attach plans to (default: razorpay).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would change without writing to the database.",
        )

    def handle(self, *args, **options):
        # Import inside handle so the command loads even if app registry order shifts.
        from airpay.models import AirPlan, PaymentGateway

        gateway_name = options["gateway"]
        dry_run = options["dry_run"]

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no database writes.\n"))

        with transaction.atomic():
            gateway, gw_created = PaymentGateway.objects.get_or_create(
                name=gateway_name,
                defaults={"is_active": True},
            )
            if gw_created:
                self.stdout.write(
                    self.style.SUCCESS(f"+ PaymentGateway '{gateway_name}' created")
                )
            else:
                # Ensure the gateway is active so checkout works.
                if not gateway.is_active and not dry_run:
                    gateway.is_active = True
                    gateway.save(update_fields=["is_active"])
                self.stdout.write(f"= PaymentGateway '{gateway_name}' exists")

            created_n = updated_n = 0
            for (
                plan_id,
                name,
                tier_level,
                price,
                billing_cycle,
                is_active,
                is_addon,
                metadata,
            ) in TIER_PLANS:
                defaults = {
                    "name": name,
                    "tier_level": tier_level,
                    "price": price,
                    "currency": "INR",
                    "billing_cycle": billing_cycle,
                    "is_active": is_active,
                    "is_addon": is_addon,
                    "gateway": gateway,
                    "description": f"{name} tier — {SEED_NOTE}",
                    "metadata": {**metadata, "source": "cn007_seed", "note": SEED_NOTE},
                }

                if dry_run:
                    exists = AirPlan.objects.filter(plan_id=plan_id).exists()
                    verb = "update" if exists else "create"
                    self.stdout.write(
                        f"  would {verb}: {plan_id} ({tier_level}) ₹{price:.0f}/{billing_cycle}"
                    )
                    continue

                _, created = AirPlan.objects.update_or_create(
                    plan_id=plan_id,
                    defaults=defaults,
                )
                if created:
                    created_n += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  + {plan_id} ({tier_level}) ₹{price:.0f}/{billing_cycle}"
                        )
                    )
                else:
                    updated_n += 1
                    self.stdout.write(
                        f"  = {plan_id} ({tier_level}) ₹{price:.0f}/{billing_cycle}"
                    )

            if dry_run:
                transaction.set_rollback(True)
                self.stdout.write(self.style.WARNING("\nDry run complete — rolled back."))
                return

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone. {created_n} created, {updated_n} updated, "
                f"{len(TIER_PLANS)} total tier plans on '{gateway_name}'."
            )
        )
