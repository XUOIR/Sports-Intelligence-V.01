-- Review reference. Deploy using Alembic.
CREATE TYPE state AS ENUM ('WATCH', 'HOLD', 'PASS', 'RECOMMEND');

CREATE TYPE outcome AS ENUM ('WIN', 'LOSS', 'PUSH', 'VOID', 'PENDING');


CREATE TABLE fixtures (
	id VARCHAR(100) NOT NULL, 
	sport VARCHAR(8) NOT NULL, 
	home VARCHAR(160) NOT NULL, 
	away VARCHAR(160) NOT NULL, 
	commence_time TIMESTAMP WITH TIME ZONE NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	state state NOT NULL, 
	dirty BOOLEAN NOT NULL, 
	revision INTEGER NOT NULL, 
	probability NUMERIC(8, 6), 
	target_price NUMERIC(12, 6), 
	edge NUMERIC(8, 6), 
	suggested_stake NUMERIC(12, 2) NOT NULL, 
	selection VARCHAR(160), 
	gates JSON NOT NULL, 
	metrics JSON NOT NULL, 
	risk_assessment JSON NOT NULL, 
	reason VARCHAR(500) NOT NULL, 
	final_home_win BOOLEAN, 
	PRIMARY KEY (id), 
	CHECK (sport IN ('NHL','MLB','NFL','NBA','CS2','VAL','LOL'))
)

;

CREATE INDEX ix_fixtures_commence_time ON fixtures (commence_time);


CREATE TABLE account (
	id INTEGER NOT NULL, 
	initial_bankroll NUMERIC(12, 2) NOT NULL, 
	PRIMARY KEY (id)
)

;


CREATE TABLE runtime_limits (
	key VARCHAR(100) NOT NULL, 
	used INTEGER NOT NULL, 
	blocked_until TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (key)
)

;


CREATE TABLE job_leases (
	key VARCHAR(100) NOT NULL, 
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (key)
)

;


CREATE TABLE model_validation (
	version VARCHAR(40) NOT NULL, 
	sport VARCHAR(8) NOT NULL, 
	parameters JSON NOT NULL, 
	report JSON NOT NULL, 
	approved BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (version)
)

;


CREATE TABLE audit_log (
	id SERIAL NOT NULL, 
	action VARCHAR(60) NOT NULL, 
	entity_id VARCHAR(100) NOT NULL, 
	details JSON NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
)

;


CREATE TABLE market_odds (
	id SERIAL NOT NULL, 
	fixture_id VARCHAR(100) NOT NULL, 
	bookmaker VARCHAR(40) NOT NULL, 
	market VARCHAR(20) NOT NULL, 
	selection VARCHAR(160) NOT NULL, 
	line NUMERIC(12, 4), 
	decimal_odds NUMERIC(16, 8) NOT NULL, 
	implied_probability NUMERIC(6, 4) NOT NULL, 
	source_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	identity VARCHAR(64) NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (fixture_id, identity, source_at), 
	CHECK (decimal_odds > 1.0001), 
	FOREIGN KEY(fixture_id) REFERENCES fixtures (id)
)

;

CREATE INDEX ix_quote_lookup ON market_odds (fixture_id, bookmaker, market, selection);

CREATE INDEX ix_market_odds_fixture_id ON market_odds (fixture_id);


CREATE TABLE personal_bets (
	id VARCHAR(36) NOT NULL, 
	request_id VARCHAR(36) NOT NULL, 
	fixture_id VARCHAR(100) NOT NULL, 
	selection VARCHAR(160) NOT NULL, 
	market VARCHAR(20) NOT NULL, 
	line NUMERIC(12, 4), 
	bookmaker VARCHAR(40) NOT NULL, 
	odds_taken NUMERIC(16, 8) NOT NULL, 
	stake_cad NUMERIC(12, 2) NOT NULL, 
	unit_size_at_execution NUMERIC(12, 2) NOT NULL, 
	outcome outcome NOT NULL, 
	profit_cad NUMERIC(12, 2) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (stake_cad > 0 AND odds_taken > 1.0001 AND unit_size_at_execution > 0), 
	UNIQUE (request_id), 
	FOREIGN KEY(fixture_id) REFERENCES fixtures (id)
)

;


CREATE TABLE source_evidence (
	id SERIAL NOT NULL, 
	fixture_id VARCHAR(100) NOT NULL, 
	kind VARCHAR(30) NOT NULL, 
	observed_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	source_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	payload JSON NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(fixture_id) REFERENCES fixtures (id)
)

;

CREATE INDEX ix_source_evidence_fixture_id ON source_evidence (fixture_id);


CREATE TABLE frozen_snapshots (
	fixture_id VARCHAR(100) NOT NULL, 
	anchor_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	collected_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	game_date DATE NOT NULL, 
	vector JSON NOT NULL, 
	evidence_ids JSON NOT NULL, 
	context JSON NOT NULL, 
	baseline_home_probability NUMERIC(8, 6), 
	prediction_home_probability NUMERIC(8, 6), 
	model_version VARCHAR(40) NOT NULL, 
	final_home_win BOOLEAN, 
	brier NUMERIC(12, 8), 
	PRIMARY KEY (fixture_id), 
	FOREIGN KEY(fixture_id) REFERENCES fixtures (id)
)

;


CREATE TABLE evaluation_cycles (
	id VARCHAR(64) NOT NULL, 
	fixture_id VARCHAR(100) NOT NULL, 
	llm_attempts INTEGER NOT NULL, 
	report JSON, 
	PRIMARY KEY (id), 
	FOREIGN KEY(fixture_id) REFERENCES fixtures (id)
)

;

INSERT INTO account (id, initial_bankroll) VALUES (1, 1100.00) ON CONFLICT DO NOTHING;

ALTER TABLE "account" ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE "account" FROM anon, authenticated;

ALTER TABLE "audit_log" ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE "audit_log" FROM anon, authenticated;

ALTER TABLE "fixtures" ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE "fixtures" FROM anon, authenticated;

ALTER TABLE "job_leases" ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE "job_leases" FROM anon, authenticated;

ALTER TABLE "model_validation" ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE "model_validation" FROM anon, authenticated;

ALTER TABLE "runtime_limits" ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE "runtime_limits" FROM anon, authenticated;

ALTER TABLE "evaluation_cycles" ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE "evaluation_cycles" FROM anon, authenticated;

ALTER TABLE "frozen_snapshots" ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE "frozen_snapshots" FROM anon, authenticated;

ALTER TABLE "market_odds" ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE "market_odds" FROM anon, authenticated;

ALTER TABLE "personal_bets" ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE "personal_bets" FROM anon, authenticated;

ALTER TABLE "source_evidence" ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE "source_evidence" FROM anon, authenticated;
