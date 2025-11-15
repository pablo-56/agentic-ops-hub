// === Unique node keys on :id (safe + idempotent) ===
CREATE CONSTRAINT site_id       IF NOT EXISTS FOR (n:Site)         REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT plant_id      IF NOT EXISTS FOR (n:Plant)        REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT line_id       IF NOT EXISTS FOR (n:Line)         REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT machine_id    IF NOT EXISTS FOR (n:Machine)      REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT sensor_id     IF NOT EXISTS FOR (n:Sensor)       REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT service_id    IF NOT EXISTS FOR (n:Service)      REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT database_id   IF NOT EXISTS FOR (n:Database)     REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT team_id       IF NOT EXISTS FOR (n:Team)         REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT incident_id   IF NOT EXISTS FOR (n:Incident)     REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT alert_id      IF NOT EXISTS FOR (n:Alert)        REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT ticket_id     IF NOT EXISTS FOR (n:Ticket)       REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT runbook_id    IF NOT EXISTS FOR (n:Runbook)      REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT action_id     IF NOT EXISTS FOR (n:AgentAction)  REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT api_id        IF NOT EXISTS FOR (n:API)          REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT topic_id      IF NOT EXISTS FOR (n:Topic)        REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT server_id     IF NOT EXISTS FOR (n:Server)       REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT netdev_id     IF NOT EXISTS FOR (n:NetworkDevice) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT user_id       IF NOT EXISTS FOR (n:User)         REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT alerttype_id  IF NOT EXISTS FOR (n:AlertType)    REQUIRE n.id IS UNIQUE;

// === Full-text index for search (id/name/title) ===
CREATE FULLTEXT INDEX entity_text IF NOT EXISTS
FOR (n:Service|Machine|Line|Plant|Database|Sensor|API|Server|Topic|Incident|Alert|Team)
ON EACH [n.id, n.name, n.title];
// --- Physical / logical topology ---
MERGE (site:Site {id: "Site-1"})
  ON CREATE SET site.name="Factory Campus", site.created_at=datetime()
  ON MATCH  SET site.updated_at=datetime();

MERGE (plant:Plant {id: "Plant-A"})
  ON CREATE SET plant.name="Plant A", plant.created_at=datetime()
  ON MATCH  SET plant.updated_at=datetime();

MERGE (line:Line {id: "Line-3"})
  ON CREATE SET line.name="Assembly Line 3", line.created_at=datetime()
  ON MATCH  SET line.updated_at=datetime();

MERGE (m1:Machine {id: "M-42"})
  ON CREATE SET m1.name="Cutter M-42", m1.criticality="high", m1.created_at=datetime()
  ON MATCH  SET m1.updated_at=datetime();

MERGE (m2:Machine {id: "P-7"})
  ON CREATE SET m2.name="Pump P-7", m2.criticality="high", m2.created_at=datetime()
  ON MATCH  SET m2.updated_at=datetime();

MERGE (s22:Sensor {id: "S-22"})
  ON CREATE SET s22.name="Vibration S-22", s22.created_at=datetime()
  ON MATCH  SET s22.updated_at=datetime();

// --- App / infra ---
MERGE (svc:Service {id: "order-service"})
  ON CREATE SET svc.name="Order Service", svc.tier=2, svc.created_at=datetime()
  ON MATCH  SET svc.updated_at=datetime();

MERGE (db:Database {id: "orders-db"})
  ON CREATE SET db.name="Orders DB", db.engine="postgres", db.created_at=datetime()
  ON MATCH  SET db.updated_at=datetime();

MERGE (api:API {id: "payments-api"})
  ON CREATE SET api.name="Payments API", api.version="v1", api.created_at=datetime()
  ON MATCH  SET api.updated_at=datetime();

MERGE (srv:Server {id: "srv-10"})
  ON CREATE SET srv.name="App Server 10", srv.az="us-east-1a", srv.created_at=datetime()
  ON MATCH  SET srv.updated_at=datetime();

MERGE (topic1:Topic {id: "orders-events"})
  ON CREATE SET topic1.name="orders-events", topic1.partitions=6, topic1.created_at=datetime()
  ON MATCH  SET topic1.updated_at=datetime();

// --- Orgs / users ---
MERGE (team:Team {id: "Team-A"})
  ON CREATE SET team.name="Core Platform", team.created_at=datetime()
  ON MATCH  SET team.updated_at=datetime();

MERGE (user:User {id: "sre-1"})
  ON CREATE SET user.name="On-Call SRE 1", user.role="SRE", user.created_at=datetime()
  ON MATCH  SET user.updated_at=datetime();
// Site -> Plant (optional if you model sites)
MERGE (site:Site {id: "Site-1"})
MERGE (plant:Plant {id: "Plant-A"})
MERGE (site)-[:HAS_PLANT]->(plant)  // not in REL_CHILD but OK to have; remove if you want strictness

// Plant -> Line
MERGE (plant:Plant {id: "Plant-A"})
MERGE (line:Line   {id:'Line-3'})
MERGE (plant)-[:HAS_LINE]->(line)

// Line -> Machines
MERGE (line:Line   {id:'Line-3'})
MERGE (m1:Machine  {id:'M-42'})
MERGE (line)-[:HAS_MACHINE]->(m1)

MERGE (line:Line   {id:'Line-3'})
MERGE (m2:Machine  {id:'P-7'})
MERGE (line)-[:HAS_MACHINE]->(m2)

// Machine -> Sensor
MERGE (m1:Machine  {id:'M-42'})
MERGE (s22:Sensor {id: "S-22"})
MERGE (m1)-[:HAS_SENSOR]->(s22)

// Service owns / runs on infra
MERGE (svc:Service {id: "order-service"})
MERGE (srv:Server {id: "srv-10"})
MERGE (svc)-[:RUNS_ON {strength:"critical"}]->(srv)

// Service uses DB
MERGE (db:Database {id: "orders-db"})
MERGE (svc)-[:USES_DB {dependency_type:"READS_FROM", strength:"critical"}]->(db)

// Service calls API
MERGE (api:API {id: "payments-api"})
MERGE (svc)-[:CALLS_API {dependency_type:"USES", strength:"normal"}]->(api)

// Service publishes/consumes Kafka topics
MERGE (topic1:Topic {id: "orders-events"})
MERGE (svc)-[:PUBLISHES_TO]->(topic1)

// Example: another service consumes from the same topic
MERGE (svc2:Service {id: "billing-service"})
  ON CREATE SET svc2.name="Billing Service", svc2.tier=2, svc2.created_at=datetime()
  ON MATCH  SET svc2.updated_at=datetime();

MERGE (svc2)-[:CONSUMES_FROM]->(topic1)

// Service owned by team
MERGE (team:Team {id: "Team-A"})
MERGE (svc)-[:OWNED_BY]->(team)
MERGE (svc2)-[:OWNED_BY]->(team)
// Incident affecting machine & service
MERGE (inc:Incident {id: "INC-1001"})
  ON CREATE SET inc.title="Line-3 throughput drop", inc.severity="high", inc.status="open", inc.created_at=datetime()
  ON MATCH  SET inc.updated_at=datetime();

MERGE (m2:Machine {id: "P-7"})
MERGE (svc:Service {id: "order-service"})
MERGE (inc)-[:AFFECTS]->(m2)
MERGE (inc)-[:AFFECTS]->(svc)

// Alert about a sensor / machine
MERGE (al:Alert {id: "ALERT-5001"})
  ON CREATE SET al.name="Vibration high S-22", al.severity="warning", al.source="monitoring", al.created_at=datetime()
  ON MATCH  SET al.updated_at=datetime();

MERGE (s22:Sensor {id: "S-22"})
MERGE (al)-[:ABOUT]->(s22)

// Correlate alerts (multi-symptom)
MERGE (al2:Alert {id: "ALERT-5002"})
  ON CREATE SET al2.name="Pump P-7 temp spike", al2.severity="warning", al2.source="monitoring", al2.created_at=datetime()
  ON MATCH  SET al2.updated_at=datetime();
MERGE (al)-[:CORRELATED_WITH]->(al2)

// Ticket tracks the incident
MERGE (t:Ticket {id: "TIC-9001"})
  ON CREATE SET t.title="Investigate Line-3", t.status="open", t.created_at=datetime()
  ON MATCH  SET t.updated_at=datetime();
MERGE (t)-[:TRACKS]->(inc)
// Runbook applies to a Service and to an AlertType
MERGE (rb:Runbook {id: "RB-restore-pump"})
  ON CREATE SET rb.name="Restore Pump P-7", rb.risk="low", rb.created_at=datetime()
  ON MATCH  SET rb.updated_at=datetime();

MERGE (svc:Service {id: "order-service"})
MERGE (rb)-[:APPLIES_TO]->(svc)

MERGE (atype:AlertType {id: "vibration-high"})
  ON CREATE SET atype.name="Vibration High", atype.created_at=datetime()
  ON MATCH  SET atype.updated_at=datetime();
MERGE (rb)-[:APPLIES_TO]->(atype)

// Agent action executed by user and related to incident
MERGE (aa:AgentAction {id: "ACT-7001"})
  ON CREATE SET aa.action="run_playbook", aa.status="completed", aa.created_at=datetime()
  ON MATCH  SET aa.updated_at=datetime();

MERGE (u:User {id: "sre-1"})
MERGE (aa)-[:EXECUTED_BY]->(u)

MERGE (inc:Incident {id: "INC-1001"})
MERGE (aa)-[:RELATES_TO]->(inc)

// Agent action targeted a machine and was based on an alert and runbook
MERGE (m2:Machine {id: "P-7"})
MERGE (aa)-[:TARGETS]->(m2)

MERGE (al:Alert {id: "ALERT-5001"})
MERGE (aa)-[:BASED_ON]->(al)
MERGE (aa)-[:BASED_ON]->(rb)

// Optional: approval trail
MERGE (approver:User {id: "lead-1"})
  ON CREATE SET approver.name="SRE Lead", approver.role="Lead", approver.created_at=datetime()
  ON MATCH  SET approver.updated_at=datetime();
MERGE (aa)-[:APPROVED_BY]->(approver)
MERGE (s22:Sensor {id: "S-22"})
MERGE (m1:Machine {id: "M-42"})
MERGE (s22)-[:ATTACHED_TO]->(m1)

// Basic service + infra
MERGE (s:Service {id:'order-service', name:'Order Service'})
MERGE (db:Database {id:'orders-db', name:'Orders DB'})
MERGE (api:API {id:'payments-api', name:'Payments API'})
MERGE (srv:Server {id:'srv-1', name:'K8s Node 1'})
MERGE (t:Team {id:'team-checkout', name:'Checkout Team'})

// Ownership + dependencies with strengths
MERGE (s)-[:OWNED_BY]->(t)
MERGE (s)-[:USES_DB {dependency_type:'READS_FROM', strength:'critical'}]->(db)
MERGE (s)-[:CALLS_API {dependency_type:'USES', strength:'normal'}]->(api)
MERGE (s)-[:RUNS_ON {strength:'critical'}]->(srv)

// Optional: a topic
MERGE (topic:Topic {id:'orders.events', name:'orders.events'})
MERGE (s)-[:PUBLISHES_TO]->(topic)

 
