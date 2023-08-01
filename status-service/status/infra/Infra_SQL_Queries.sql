
DELETE
FROM aws.ec2_current;
DELETE
FROM aws.rds_current;
DELETE
FROM aws.subnet_current;
DELETE
FROM aws.sg_current;
DELETE
FROM aws.nacl_current;

DELETE
FROM aws.ec2_baseline;
DELETE
FROM aws.rds_baseline;
DELETE
FROM aws.subnet_baseline;
DELETE
FROM aws.sg_baseline;
DELETE
FROM aws.nacl_baseline;

DELETE
FROM aws.audit_log;

DELETE SCHEMA aws;


CREATE SCHEMA aws;

CREATE TABLE aws.ec2_current
(
    instance_id    TEXT PRIMARY KEY,
    instance_name  TEXT,
    instance_type  TEXT      NOT NULL,
    subnet         TEXT      NOT NULL,
    security_group jsonb     NOT NULL,
    created_on     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE aws.ec2_baseline
(
    instance_id    TEXT PRIMARY KEY,
    instance_name  TEXT,
    instance_type  TEXT      NOT NULL,
    subnet         TEXT      NOT NULL,
    security_group jsonb     NOT NULL,
    created_on     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE aws.rds_current
(
    instance_id         TEXT PRIMARY KEY,
    endpoint            TEXT,
    instance_class      TEXT      NOT NULL,
    subnet              jsonb     NOT NULL,
    security_group      jsonb     NOT NULL,
    engine              TEXT      NOT NULL,
    engine_version      TEXT      NOT NULL,
    storage_encrypted   TEXT      NOT NULL,
    availability_zone   TEXT      NOT NULL,
    db_parameter_groups TEXT      NOT NULL,
    multi_az            TEXT      NOT NULL,
    created_on          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE aws.rds_baseline
(
    instance_id         TEXT PRIMARY KEY,
    endpoint            TEXT,
    instance_class      TEXT      NOT NULL,
    subnet              jsonb     NOT NULL,
    security_group      jsonb     NOT NULL,
    engine              TEXT      NOT NULL,
    engine_version      TEXT      NOT NULL,
    storage_encrypted   TEXT      NOT NULL,
    availability_zone   TEXT      NOT NULL,
    db_parameter_groups TEXT      NOT NULL,
    multi_az            TEXT      NOT NULL,
    created_on          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE aws.subnet_current
(
    subnet_id         TEXT PRIMARY KEY,
    subnet_name       TEXT      NOT NULL,
    cidr_block        TEXT      NOT NULL,
    availability_zone TEXT,
    created_on        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE aws.subnet_baseline
(
    subnet_id         TEXT PRIMARY KEY,
    subnet_name       TEXT      NOT NULL,
    cidr_block        TEXT      NOT NULL,
    availability_zone TEXT,
    created_on        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE aws.sg_current
(
    sg_id         TEXT PRIMARY KEY,
    sg_name       TEXT      NOT NULL,
    inbound_rules jsonb     NOT NULL,
    created_on    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE aws.sg_baseline
(
    sg_id         TEXT PRIMARY KEY,
    sg_name       TEXT      NOT NULL,
    inbound_rules jsonb     NOT NULL,
    created_on    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE aws.nacl_current
(
    nacl_id    TEXT PRIMARY KEY,
    nacl_name  TEXT      NOT NULL,
    entries    jsonb     NOT NULL,
    created_on TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE aws.nacl_baseline
(
    nacl_id    TEXT PRIMARY KEY,
    nacl_name  TEXT      NOT NULL,
    entries    jsonb     NOT NULL,
    created_on TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE aws.audit_log
(
    audit_id     SERIAL PRIMARY KEY,
    service_name VARCHAR(20) NOT NULL,
    instance_id  VARCHAR(40) NOT NULL,
    log          TEXT        NOT NULL,
    created_on   TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE aws.audit_log
ADD COLUMN  username VARCHAR(20) NOT NULL;

ALTER TABLE aws.ec2_baseline
ADD COLUMN  instance_state VARCHAR(15) NOT NULL DEFAULT 'running';

ALTER TABLE aws.ec2_current
ADD COLUMN  instance_state VARCHAR(15) NOT NULL DEFAULT 'running';

ALTER TABLE aws.ec2_baseline
ALTER COLUMN security_group TYPE jsonb USING security_group::jsonb;

ALTER TABLE aws.ec2_current
ALTER COLUMN security_group TYPE jsonb USING security_group::jsonb;

ALTER TABLE aws.rds_baseline
ALTER COLUMN security_group TYPE jsonb USING security_group::jsonb;

ALTER TABLE aws.rds_current
ALTER COLUMN security_group TYPE jsonb USING security_group::jsonb;

ALTER TABLE aws.rds_baseline
ALTER COLUMN subnet TYPE jsonb USING subnet::jsonb;

ALTER TABLE aws.rds_current
ALTER COLUMN subnet TYPE jsonb USING subnet::jsonb;

ALTER TABLE aws.nacl_baseline
ALTER COLUMN entries TYPE jsonb USING entries::jsonb;

ALTER TABLE aws.nacl_current
ALTER COLUMN entries TYPE jsonb USING entries::jsonb;


ALTER TABLE aws.subnet_baseline
ADD COLUMN  public_ip VARCHAR(5) NOT NULL DEFAULT 'NULL';

ALTER TABLE aws.subnet_current
ADD COLUMN  public_ip VARCHAR(5) NOT NULL DEFAULT 'NULL';

ALTER TABLE aws.subnet_baseline
ADD COLUMN  available_ips VARCHAR(10) NOT NULL DEFAULT '0';

ALTER TABLE aws.subnet_current
ADD COLUMN  available_ips VARCHAR(10) NOT NULL DEFAULT '0';



ALTER TABLE aws.ec2_current ADD COLUMN deleted BOOLEAN DEFAULT FALSE;
ALTER TABLE aws.ec2_baseline ADD COLUMN deleted BOOLEAN DEFAULT FALSE;
ALTER TABLE aws.rds_current ADD COLUMN deleted BOOLEAN DEFAULT FALSE;
ALTER TABLE aws.rds_baseline ADD COLUMN deleted BOOLEAN DEFAULT FALSE;
ALTER TABLE aws.subnet_current ADD COLUMN deleted BOOLEAN DEFAULT FALSE;
ALTER TABLE aws.subnet_baseline ADD COLUMN deleted BOOLEAN DEFAULT FALSE;
ALTER TABLE aws.sg_current ADD COLUMN deleted BOOLEAN DEFAULT FALSE;
ALTER TABLE aws.sg_baseline ADD COLUMN deleted BOOLEAN DEFAULT FALSE;
ALTER TABLE aws.nacl_current ADD COLUMN deleted BOOLEAN DEFAULT FALSE;
ALTER TABLE aws.nacl_baseline ADD COLUMN deleted BOOLEAN DEFAULT FALSE;


CREATE TABLE aws.route_current
(
    route_id    TEXT PRIMARY KEY,
    route_name  TEXT      NOT NULL,
    routes      jsonb     NOT NULL,
    subnet_ids  jsonb     NOT NULL,
    created_on TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted   BOOLEAN   NOT NULL DEFAULT FALSE
);

CREATE TABLE aws.route_baseline
(
    route_id    TEXT PRIMARY KEY,
    route_name  TEXT      NOT NULL,
    routes      jsonb     NOT NULL,
    subnet_ids  jsonb     NOT NULL,
    created_on TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted   BOOLEAN   NOT NULL DEFAULT FALSE
);


ALTER TABLE aws.ec2_baseline
ADD COLUMN  instance_iam VARCHAR(100) DEFAULT '';

ALTER TABLE aws.ec2_current
ADD COLUMN  instance_iam VARCHAR(100) DEFAULT '';

ALTER TABLE aws.subnet_current DROP COLUMN  available_ips;
ALTER TABLE aws.subnet_baseline DROP COLUMN  available_ips;