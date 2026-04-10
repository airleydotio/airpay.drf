# Generated manually to seed tier system data

from django.db import migrations


def seed_tier_system(apps, schema_editor):
    """
    Seed tier-based plans and features for Jeevit.
    Replaces the deprecated FeatureConfig model.
    """
    AirPlan = apps.get_model('airpay', 'AirPlan')
    AirPlanFeatures = apps.get_model('airpay', 'AirPlanFeatures')
    PaymentGateway = apps.get_model('airpay', 'PaymentGateway')

    # Get or create default gateway
    gateway, _ = PaymentGateway.objects.get_or_create(
        name='razorpay',
        defaults={'is_active': True}
    )

    # Create tier plans
    companion_plan, _ = AirPlan.objects.get_or_create(
        tier_level='companion',
        defaults={
            'name': 'Companion Tier',
            'price': 0.0,
            'description': 'Free tier with AI coaching and basic features',
            'currency': 'INR',
            'is_active': True,
            'plan_id': 'companion_tier_free',
            'billing_cycle': 'monthly',
            'gateway': gateway,
        }
    )

    guardian_plan, _ = AirPlan.objects.get_or_create(
        tier_level='guardian',
        defaults={
            'name': 'Guardian Tier',
            'price': 2999.0,
            'description': 'Paid tier with full protocol management and physician access',
            'currency': 'INR',
            'is_active': True,
            'plan_id': 'guardian_tier_monthly',
            'billing_cycle': 'monthly',
            'gateway': gateway,
        }
    )

    medical_plan, _ = AirPlan.objects.get_or_create(
        tier_level='medical',
        defaults={
            'name': 'Medical Tier',
            'price': 4999.0,
            'description': 'Physician-managed tier with dedicated medical support',
            'currency': 'INR',
            'is_active': True,
            'plan_id': 'medical_tier_monthly',
            'billing_cycle': 'monthly',
            'gateway': gateway,
        }
    )

    alumni_plan, _ = AirPlan.objects.get_or_create(
        tier_level='alumni',
        defaults={
            'name': 'Alumni Tier',
            'price': 499.0,
            'description': 'Maintenance tier for graduated users',
            'currency': 'INR',
            'is_active': True,
            'plan_id': 'alumni_tier_monthly',
            'billing_cycle': 'monthly',
            'gateway': gateway,
        }
    )

    # Create features
    full_protocol, _ = AirPlanFeatures.objects.get_or_create(
        feature_key='full_protocol_management',
        defaults={
            'name': 'Full Protocol Management',
            'description': 'AI manages full protocol including target calibration, interaction checking, symptom correlation',
            'feature_type': 'protocol',
            'is_active': True,
            'config_value': {
                'target_calibration': True,
                'interaction_checking': True,
                'symptom_correlation': True,
                'physician_integration': True,
            }
        }
    )

    titration_mgmt, _ = AirPlanFeatures.objects.get_or_create(
        feature_key='medication_titration_management',
        defaults={
            'name': 'Medication Titration Management',
            'description': 'AI suggests dose adjustments based on progress and physician guidelines',
            'feature_type': 'medication',
            'is_active': True,
            'config_value': {
                'auto_suggestions': True,
                'physician_approval_required': True,
            }
        }
    )

    supplement_suggestions, _ = AirPlanFeatures.objects.get_or_create(
        feature_key='supplement_suggestions',
        defaults={
            'name': 'Supplement Suggestions',
            'description': 'AI suggests supplements based on medications, blood work, and goals',
            'feature_type': 'supplement',
            'is_active': True,
            'config_value': {
                'blood_work_based': True,
                'medication_interaction_check': True,
            }
        }
    )

    physician_access, _ = AirPlanFeatures.objects.get_or_create(
        feature_key='physician_access',
        defaults={
            'name': 'Physician Access',
            'description': 'Access to Jeevit physicians for consultations',
            'feature_type': 'access',
            'is_active': True,
            'config_value': {
                'consultation_slots_per_month': 2,
            }
        }
    )

    abnormal_signal_alerts, _ = AirPlanFeatures.objects.get_or_create(
        feature_key='abnormal_signal_alerts',
        defaults={
            'name': 'Abnormal Signal Alerts',
            'description': 'Alerts for rapid weight changes, symptom combinations',
            'feature_type': 'monitoring',
            'is_active': True,
            'config_value': {
                'rapid_weight_loss_threshold': 2.0,  # kg per week
                'rapid_weight_gain_threshold': 2.0,
                'physician_notification': True,
            }
        }
    )

    # Assign features to tiers

    # Companion tier: Basic features only
    companion_plan.features.add(supplement_suggestions)

    # Guardian tier: Full protocol + physician access
    guardian_plan.features.add(
        full_protocol,
        titration_mgmt,
        supplement_suggestions,
        physician_access,
        abnormal_signal_alerts,
    )

    # Medical tier: Same as Guardian (physician-managed)
    medical_plan.features.add(
        full_protocol,
        titration_mgmt,
        supplement_suggestions,
        physician_access,
        abnormal_signal_alerts,
    )

    # Alumni tier: Maintenance features
    alumni_plan.features.add(
        supplement_suggestions,
        abnormal_signal_alerts,
    )


def reverse_seed(apps, schema_editor):
    """Remove seeded tier data"""
    AirPlan = apps.get_model('airpay', 'AirPlan')
    AirPlanFeatures = apps.get_model('airpay', 'AirPlanFeatures')

    # Delete tier plans
    AirPlan.objects.filter(
        tier_level__in=['companion', 'guardian', 'medical', 'alumni']
    ).delete()

    # Delete features
    AirPlanFeatures.objects.filter(
        feature_key__in=[
            'full_protocol_management',
            'medication_titration_management',
            'supplement_suggestions',
            'physician_access',
            'abnormal_signal_alerts',
        ]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('airpay', '0021_airplan_metadata_airplan_tier_level_and_more'),
    ]

    operations = [
        migrations.RunPython(seed_tier_system, reverse_seed),
    ]
