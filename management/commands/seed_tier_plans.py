"""
Seed airpay tier plans — CN-94 v1.0 locked pricing grid (3 Jul 2026, founder-
confirmed 5 Jul against the CN-94/95 source session; supersedes the CN-007
launch-seed placeholder grid below).

Idempotent seed script — safe to run repeatedly. Creates/updates the Razorpay
PaymentGateway and the AirPlan rows for each Jeevit tier so Subscriptions can
reference a concrete plan.

CN-94 §1 grid (model v1.22, ladder-ruling annotated):
Tier                     | 1-month | 5-month | 9-month | Save (5mo/9mo)
-------------------------|---------|---------|---------|----------------
Companion                | ₹599    | ₹549    | ₹499    | ₹250 / ₹900
Guardian                 | ₹1,899  | ₹1,799  | ₹1,699  | ₹500 / ₹1,800
Weight & Metabolic Care  | ₹8,999  | ₹8,699  | ₹8,499  | ₹1,500 / ₹4,500

Gate scope (CN-94 §1, supersedes CN-043 §2.3): Companion + Guardian 5/9-month
plans sellable AT SIGNUP. WMC 5/9-month plans open only after the first month
(dose-settling window) — that gate is enforced at the confirmation-bubble/
tier-activation layer, not here; this command only seeds the price catalogue.

SAFETY — price is NOT snapshotted onto Subscriptions at signup. Subscriptions.
create_order() reads self.plan.price LIVE on every call, so update_or_create-ing
an EXISTING plan_id's price would silently change what an already-subscribed
member is charged on their NEXT order/renewal. Before overwriting a plan_id
whose price is changing, this command checks for Subscriptions rows already
referencing it; if any exist, that plan_id's price is left untouched and
reported, requiring --reprice-active-plans (explicit, no default) to force it.
New tiers/durations that don't exist yet (e.g. the 5-month rows) always seed
normally — nothing can be "active" on a plan_id that doesn't exist yet.

Usage:
    python manage.py seed_tier_plans
    python manage.py seed_tier_plans --gateway razorpay
    python manage.py seed_tier_plans --dry-run
    python manage.py seed_tier_plans --reprice-active-plans   # explicit override
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
        599.0,
        "monthly",
        True,
        False,
        {"phase": None, "commitment_months": 1, "monthly_effective_paise": 59900, "total_paise": 59900},
    ),
    (
        "companion_5month",
        "Companion (5-month)",
        "companion",
        549.0,
        "5_month",
        True,
        False,
        {"phase": None, "commitment_months": 5, "monthly_effective_paise": 54900, "total_paise": 274500,
         "save_vs_monthly_paise": 25000},
    ),
    (
        "companion_9month",
        "Companion (9-month)",
        "companion",
        499.0,
        "9_month",
        True,
        False,
        {"phase": None, "commitment_months": 9, "monthly_effective_paise": 49900, "total_paise": 449100,
         "save_vs_monthly_paise": 90000},
    ),
    (
        "guardian_monthly",
        "Guardian",
        "guardian",
        1899.0,
        "monthly",
        True,
        False,
        {"phase": None, "commitment_months": 1, "monthly_effective_paise": 189900, "total_paise": 189900},
    ),
    (
        "guardian_5month",
        "Guardian (5-month)",
        "guardian",
        1799.0,
        "5_month",
        True,
        False,
        {"phase": None, "commitment_months": 5, "monthly_effective_paise": 179900, "total_paise": 899500,
         "save_vs_monthly_paise": 50000},
    ),
    (
        "guardian_9month",
        "Guardian (9-month)",
        "guardian",
        1699.0,
        "9_month",
        True,
        False,
        {"phase": None, "commitment_months": 9, "monthly_effective_paise": 169900, "total_paise": 1529100,
         "save_vs_monthly_paise": 180000},
    ),
    (
        "medical_monthly",
        "Weight & Metabolic Care",
        "medical",
        8999.0,
        "monthly",
        True,
        False,
        {"phase": None, "commitment_months": 1, "monthly_effective_paise": 899900, "total_paise": 899900},
    ),
    (
        "medical_5month",
        "Weight & Metabolic Care (5-month)",
        "medical",
        8699.0,
        "5_month",
        True,
        False,
        # CN-94 §1 — WMC 5/9-month plans open only after the member's first month
        # (dose-settling window). Gate enforced at confirmation/activation layer,
        # not here — this flag documents the rule for anything reading metadata.
        {"phase": None, "commitment_months": 5, "monthly_effective_paise": 869900, "total_paise": 4349500,
         "save_vs_monthly_paise": 150000, "gated_to_month_2": True},
    ),
    (
        "medical_9month",
        "Weight & Metabolic Care (9-month)",
        "medical",
        8499.0,
        "9_month",
        True,
        False,
        {"phase": None, "commitment_months": 9, "monthly_effective_paise": 849900, "total_paise": 7649100,
         "save_vs_monthly_paise": 450000, "gated_to_month_2": True},
    ),
]

SEED_NOTE = "CN-94 v1.0 locked grid (3 Jul 2026)"
SEED_SOURCE = "cn94_v1_0_seed"

# Plan_ids from the superseded CN-007 launch seed. Pruned automatically (same
# behavior as the prior seed's stale-row pruning), UNLESS a Subscriptions row
# still references one — that row is left in place and reported instead of
# silently orphaning a real subscriber's plan FK.
_SUPERSEDED_PLAN_IDS = {
    "medical_active_3m", "medical_active_9m", "medical_maintenance_monthly",
}


class Command(BaseCommand):
    help = "Seed airpay tier plans (CN-94 v1.0 locked pricing grid). Idempotent."

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
        parser.add_argument(
            "--reprice-active-plans",
            action="store_true",
            help=(
                "Force-overwrite the price on a plan_id that already has "
                "Subscriptions referencing it. DANGEROUS: price is read live "
                "at every order/renewal (not snapshotted), so this changes "
                "what an existing subscriber is charged next. Omit unless "
                "you've confirmed this is the intended outcome for those "
                "specific subscribers."
            ),
        )

    def handle(self, *args, **options):
        from airpay.models import AirPlan, PaymentGateway, Subscriptions

        gateway_name = options["gateway"]
        dry_run = options["dry_run"]
        force_reprice = options["reprice_active_plans"]

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
                if not gateway.is_active and not dry_run:
                    gateway.is_active = True
                    gateway.save(update_fields=["is_active"])
                self.stdout.write(f"= PaymentGateway '{gateway_name}' exists")

            created_n = updated_n = skipped_n = 0
            for (
                plan_id, name, tier_level, price, billing_cycle, is_active, is_addon, metadata,
            ) in TIER_PLANS:
                existing = AirPlan.objects.filter(plan_id=plan_id).first()
                price_changing = existing is not None and existing.price != price

                if price_changing and not force_reprice:
                    active_subs = Subscriptions.objects.filter(
                        plan=existing,
                    ).exclude(status__in=("cancelled", "expired"))
                    sub_count = active_subs.count()
                    if sub_count:
                        skipped_n += 1
                        self.stdout.write(self.style.ERROR(
                            f"  ! SKIPPED {plan_id}: {sub_count} subscription(s) reference "
                            f"the current ₹{existing.price:.0f} price — price is read LIVE "
                            f"at every order/renewal (not snapshotted), so overwriting it "
                            f"here would reprice them. Re-run with --reprice-active-plans "
                            f"only after confirming that's intended for these subscribers."
                        ))
                        continue

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
                    "metadata": {**metadata, "source": SEED_SOURCE, "note": SEED_NOTE},
                }

                if dry_run:
                    verb = "update" if existing else "create"
                    warn = " [PRICE CHANGE — has active subs]" if (
                        price_changing and Subscriptions.objects.filter(plan=existing).exists()
                    ) else ""
                    self.stdout.write(
                        f"  would {verb}: {plan_id} ({tier_level}) ₹{price:.0f}/{billing_cycle}{warn}"
                    )
                    continue

                _, created = AirPlan.objects.update_or_create(
                    plan_id=plan_id, defaults=defaults,
                )
                if created:
                    created_n += 1
                    self.stdout.write(self.style.SUCCESS(
                        f"  + {plan_id} ({tier_level}) ₹{price:.0f}/{billing_cycle}"
                    ))
                else:
                    updated_n += 1
                    self.stdout.write(
                        f"  = {plan_id} ({tier_level}) ₹{price:.0f}/{billing_cycle}"
                    )

            # Prune superseded CN-007 seed rows — same safety rule: never orphan
            # a real subscriber's plan FK, report and skip instead.
            pruned_n = 0
            for stale_id in _SUPERSEDED_PLAN_IDS:
                stale_plan = AirPlan.objects.filter(plan_id=stale_id).first()
                if not stale_plan:
                    continue
                refs = Subscriptions.objects.filter(plan=stale_plan).exclude(
                    status__in=("cancelled", "expired"),
                )
                if refs.exists():
                    self.stdout.write(self.style.ERROR(
                        f"  ! NOT PRUNED {stale_id}: {refs.count()} subscription(s) still "
                        f"reference this superseded plan. Leaving in place."
                    ))
                    continue
                if dry_run:
                    self.stdout.write(self.style.WARNING(f"  would prune: {stale_id}"))
                    continue
                stale_plan.delete()
                pruned_n += 1
                self.stdout.write(self.style.WARNING(f"  - pruned {stale_id}"))

            if dry_run:
                transaction.set_rollback(True)
                self.stdout.write(self.style.WARNING("\nDry run complete — rolled back."))
                return

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone. {created_n} created, {updated_n} updated, {skipped_n} skipped "
                f"(active subs, needs --reprice-active-plans), {pruned_n} pruned, "
                f"{len(TIER_PLANS)} total tier plans on '{gateway_name}'."
            )
        )
