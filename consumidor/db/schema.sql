-- Esquema TimescaleDB do consumidor. Idempotente: pode rodar várias vezes.
-- Aplicado automaticamente por db.py na conexão (DB_APLICAR_SCHEMA=1) ou manualmente:
--   psql "postgresql://$POSTGRES_USER:$POSTGRES_PASSWORD@$POSTGRES_HOST:5432/$POSTGRES_DB" -f db/schema.sql

CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Medições de vibração (medicao.vibracao, apenas quality = VALIDO)
CREATE TABLE IF NOT EXISTS medicoes_vibracao (
    ts             TIMESTAMPTZ      NOT NULL,   -- eventTime (tempo do evento, não de processamento)
    entity_id      TEXT             NOT NULL,
    device_id      TEXT             NOT NULL,
    event_id       TEXT             NOT NULL,
    sequence       BIGINT,
    rms_x          DOUBLE PRECISION,
    rms_y          DOUBLE PRECISION,
    rms_z          DOUBLE PRECISION,
    rms_resultante DOUBLE PRECISION,
    pico           DOUBLE PRECISION,
    curtose        DOUBLE PRECISION,
    freq_dominante DOUBLE PRECISION,
    UNIQUE (entity_id, event_id, ts)            -- idempotência (a chave precisa incluir ts)
);
SELECT create_hypertable('medicoes_vibracao', 'ts', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS medicoes_vibracao_entity_ts ON medicoes_vibracao (entity_id, ts DESC);

-- Medições de temperatura (medicao.temperatura, apenas quality = VALIDO)
CREATE TABLE IF NOT EXISTS medicoes_temperatura (
    ts            TIMESTAMPTZ      NOT NULL,
    entity_id     TEXT             NOT NULL,
    device_id     TEXT             NOT NULL,
    event_id      TEXT             NOT NULL,
    sequence      BIGINT,
    temp_carcaca  DOUBLE PRECISION,
    temp_ambiente DOUBLE PRECISION,
    delta_t       DOUBLE PRECISION,
    UNIQUE (entity_id, event_id, ts)
);
SELECT create_hypertable('medicoes_temperatura', 'ts', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS medicoes_temperatura_entity_ts ON medicoes_temperatura (entity_id, ts DESC);

-- Decisões do hub, gravadas apenas quando o estado do ativo muda
CREATE TABLE IF NOT EXISTS decisoes (
    ts          TIMESTAMPTZ NOT NULL,
    entity_id   TEXT        NOT NULL,
    decisao     TEXT        NOT NULL,   -- NORMAL, ATENCAO, CRITICO, SEM_COMUNICACAO, DADOS_INSUFICIENTES, NAO_AVALIAVEL
    rms_norm    DOUBLE PRECISION,
    curtose_max DOUBLE PRECISION,
    delta_t     DOUBLE PRECISION,
    UNIQUE (entity_id, ts)
);
SELECT create_hypertable('decisoes', 'ts', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS decisoes_entity_ts ON decisoes (entity_id, ts DESC);

-- Compressão (segmentada por ativo) após 7 dias; retenção de 1 ano nas medições.
ALTER TABLE medicoes_vibracao    SET (timescaledb.compress, timescaledb.compress_segmentby = 'entity_id');
ALTER TABLE medicoes_temperatura SET (timescaledb.compress, timescaledb.compress_segmentby = 'entity_id');
SELECT add_compression_policy('medicoes_vibracao',    INTERVAL '7 days', if_not_exists => TRUE);
SELECT add_compression_policy('medicoes_temperatura', INTERVAL '7 days', if_not_exists => TRUE);
SELECT add_retention_policy('medicoes_vibracao',    INTERVAL '365 days', if_not_exists => TRUE);
SELECT add_retention_policy('medicoes_temperatura', INTERVAL '365 days', if_not_exists => TRUE);
-- decisoes: sem retenção (poucas linhas, valem como histórico de manutenção)
