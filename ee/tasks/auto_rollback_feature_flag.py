from datetime import datetime, timedelta
from typing import Dict

import pytz
from celery import shared_task

from ee.api.sentry_stats import get_stats_for_timerange
from posthog.models.feature_flag import FeatureFlag
from posthog.models.filters.filter import Filter
from posthog.queries.trends.trends import Trends


def check_flags_to_rollback():
    flags_with_threshold = FeatureFlag.objects.exclude(rollback_conditions__isnull=True).exclude(
        rollback_conditions__exact=[]
    )

    for feature_flag in flags_with_threshold:
        check_feature_flag_rollback_conditions(feature_flag_id=feature_flag.pk)


@shared_task(ignore_result=True, max_retries=2)
def check_feature_flag_rollback_conditions(feature_flag_id: int) -> None:
    flag: FeatureFlag = FeatureFlag.objects.get(pk=feature_flag_id)

    if any(check_condition(condition, flag) for condition in flag.rollback_conditions):
        flag.performed_rollback = True
        flag.active = False
        flag.save()


def check_condition(rollback_condition: Dict, feature_flag: FeatureFlag) -> bool:
    if rollback_condition["threshold_type"] == "sentry":
        created_date = feature_flag.created_at
        base_start_date = created_date.strftime("%Y-%m-%dT%H:%M:%S")
        base_end_date = (created_date + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S")

        current_time = datetime.utcnow()
        target_end_date = current_time.strftime("%Y-%m-%dT%H:%M:%S")
        target_start_date = (current_time - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S")

        base, target = get_stats_for_timerange(base_start_date, base_end_date, target_start_date, target_end_date)

        if rollback_condition["operator"] == "lt":
            return target < float(rollback_condition["threshold"]) * base
        else:
            return target > float(rollback_condition["threshold"]) * base

    elif rollback_condition["threshold_type"] == "insight":
        curr = datetime.now(tz=pytz.timezone(feature_flag.team.timezone))

        # rolling average last 7 days
        filter = Filter(
            data={
                **rollback_condition["threshold_metric"],
                "date_from": (curr - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S.%f"),
                "date_to": curr.strftime("%Y-%m-%d %H:%M:%S.%f"),
            },
            team=feature_flag.team,
        )
        trends_query = Trends()
        result = trends_query.run(filter, feature_flag.team)

        if not len(result):
            return False

        data = result[0]["data"]
        data = data[0:7]

        if rollback_condition["operator"] == "lt":
            return sum(data) / len(data) < rollback_condition["threshold"]
        else:
            return sum(data) / len(data) > rollback_condition["threshold"]

    return False
