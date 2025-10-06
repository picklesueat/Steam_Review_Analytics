"""Dagster sensors and alerts for freshness/completeness SLOs."""

from dagster import FreshnessPolicy, SensorEvaluationContext, sensor


@sensor(name="bronze_freshness_sensor")
def bronze_freshness_sensor(context: SensorEvaluationContext):  # pragma: no cover - placeholder
    """Trigger alerts when bronze comments fall behind SLO."""

    context.log.info("Freshness sensor placeholder - connect to monitoring backend")
    return []


BRONZE_FRESHNESS_POLICY = FreshnessPolicy(maximum_lag_minutes=180)
