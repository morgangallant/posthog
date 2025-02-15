from posthog.clickhouse.kafka_engine import KAFKA_COLUMNS, KAFKA_ENGINE_DEFAULT_SETTINGS, kafka_engine, ttl_period
from posthog.clickhouse.table_engines import MergeTreeEngine, ReplacingMergeTree, ReplicationScheme
from posthog.kafka_client.topics import KAFKA_PLUGIN_LOG_ENTRIES
from posthog.models.kafka_engine_dlq.sql import KAFKA_ENGINE_DLQ_BASE_SQL, KAFKA_ENGINE_DLQ_MV_BASE_SQL
from posthog.settings import CLICKHOUSE_CLUSTER, CLICKHOUSE_DATABASE

PLUGIN_LOG_ENTRIES_TABLE = "plugin_log_entries"
PLUGIN_LOG_ENTRIES_TTL_WEEKS = 1

PLUGIN_LOG_ENTRIES_TABLE_BASE_SQL = """
CREATE TABLE IF NOT EXISTS {table_name} ON CLUSTER '{cluster}'
(
    id UUID,
    team_id Int64,
    plugin_id Int64,
    plugin_config_id Int64,
    timestamp DateTime64(6, 'UTC'),
    source VARCHAR,
    type VARCHAR,
    message VARCHAR,
    instance_id UUID
    {extra_fields}
) ENGINE = {engine}
{partition_by}
{ttl_period}
{settings}
"""

PLUGIN_LOG_ENTRIES_TABLE_ENGINE = lambda: ReplacingMergeTree(PLUGIN_LOG_ENTRIES_TABLE, ver="_timestamp")
PLUGIN_LOG_ENTRIES_TABLE_SQL = lambda: PLUGIN_LOG_ENTRIES_TABLE_BASE_SQL.format(
    table_name=PLUGIN_LOG_ENTRIES_TABLE,
    cluster=CLICKHOUSE_CLUSTER,
    extra_fields=KAFKA_COLUMNS,
    engine=PLUGIN_LOG_ENTRIES_TABLE_ENGINE(),
    ttl_period=ttl_period("timestamp", PLUGIN_LOG_ENTRIES_TTL_WEEKS),
    partition_by="PARTITION BY plugin_id ORDER BY (team_id, id)",
    settings="SETTINGS index_granularity=512",
)

KAFKA_PLUGIN_LOG_ENTRIES_TABLE_SQL = lambda: PLUGIN_LOG_ENTRIES_TABLE_BASE_SQL.format(
    table_name="kafka_" + PLUGIN_LOG_ENTRIES_TABLE,
    cluster=CLICKHOUSE_CLUSTER,
    engine=kafka_engine(topic=KAFKA_PLUGIN_LOG_ENTRIES),
    extra_fields="",
    ttl_period="",
    partition_by="",
    settings=KAFKA_ENGINE_DEFAULT_SETTINGS,
)

KAFKA_PLUGIN_LOG_ENTRIES_DLQ_SQL = lambda: KAFKA_ENGINE_DLQ_BASE_SQL.format(
    table="kafka_dlq_plugin_log_entries",
    cluster=CLICKHOUSE_CLUSTER,
    engine=MergeTreeEngine("kafka_dlq_plugin_log_entries", replication_scheme=ReplicationScheme.REPLICATED),
)

KAFKA_PLUGIN_LOG_ENTRIES_DLQ_MV_SQL = lambda: KAFKA_ENGINE_DLQ_MV_BASE_SQL.format(
    view_name="kafka_dlq_plugin_log_entries_mv",
    target_table=f"{CLICKHOUSE_DATABASE}.kafka_dlq_plugin_log_entries",
    kafka_table_name=f"{CLICKHOUSE_DATABASE}.kafka_plugin_log_entries",
    cluster=CLICKHOUSE_CLUSTER,
)

PLUGIN_LOG_ENTRIES_TABLE_MV_SQL = """
CREATE MATERIALIZED VIEW {table_name}_mv ON CLUSTER '{cluster}'
TO {database}.{table_name}
AS SELECT
id,
team_id,
plugin_id,
plugin_config_id,
timestamp,
source,
type,
message,
instance_id,
_timestamp,
_offset
FROM {database}.kafka_{table_name}
WHERE length(_error) = 0
""".format(
    table_name=PLUGIN_LOG_ENTRIES_TABLE, cluster=CLICKHOUSE_CLUSTER, database=CLICKHOUSE_DATABASE
)


INSERT_PLUGIN_LOG_ENTRY_SQL = """
INSERT INTO plugin_log_entries SELECT %(id)s, %(team_id)s, %(plugin_id)s, %(plugin_config_id)s, %(timestamp)s, %(source)s, %(type)s, %(message)s, %(instance_id)s, now(), 0
"""

TRUNCATE_PLUGIN_LOG_ENTRIES_TABLE_SQL = (
    f"TRUNCATE TABLE IF EXISTS {PLUGIN_LOG_ENTRIES_TABLE} ON CLUSTER '{CLICKHOUSE_CLUSTER}'"
)
