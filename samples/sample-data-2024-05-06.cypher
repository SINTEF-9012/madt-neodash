CREATE (n:ASSET {name:"Scada", layer:"Functional"});
CREATE (n:ATTACHMENT {name:"architecture", type:"image", endpoint:"https://eratblob.blob.core.windows.net/dynabic-temp-attach/ferro-arch.png"});
CREATE (n:DATASOURCE {name:"testrest", type:"rest", endpoint:"https://httpbin.org/get"});
MATCH (a:ATTACHMENT), (b:ASSET) WHERE a.name = "architecture" AND b.name = "Scada"
CREATE (a)-[r:AttachTo]->(b);
MATCH (a:DATASOURCE), (b:ASSET) WHERE a.name = "testrest" AND b.name = "Scada"
CREATE (a)-[r:AttachTo]->(b);
CREATE (n:ASSET {name:"pmv1", layer:"Functional"});
CREATE (n:ASSET {name:"Switch1", layer:"Physical", latitude:59.629083, longitude:10.7361537});
CREATE (n:ASSET {name:"Switch2", layer:"Physical", latitude:59.606961, longitude:10.735244});
MATCH (a:ASSET), (b:ASSET) WHERE a.name = "Scada" AND b.name = "pmv1"
CREATE (b)-[r:ControlledBy]->(a);
MATCH (a:ASSET), (b:ASSET) WHERE a.name = "pmv1" AND b.name = "Switch1"
CREATE (a)-[r:ConnectTo]->(b);
MATCH (a:ASSET), (b:ASSET) WHERE a.name = "Switch1" AND b.name = "Switch2"
CREATE (a)-[r:ConnectTo]->(b);
MATCH (n:ASSET) SET n.uid = apoc.create.uuid();
MATCH (a:ASSET) WHERE a.layer = "Physical" CREATE (s:REALTIME {name: "realtimedata", endpoint: a.uid})
MERGE (s)-[:AttachTo]->(a);
MATCH (a:ASSET) WHERE a.layer = "Physical" CREATE (s:STATICDATA {name: "staticdata", endpoint: a.uid})
MERGE (s)-[:AttachTo]->(a);
MATCH (s:STATICDATA)
CREATE (an:ANALYTICS {name: "analytics", endpoint: s.endpoint})
CREATE (st:STATISTICS {name: "statistics", endpoint: s.endpoint})
CREATE (co:COUNT {name: "count", endpoint: s.endpoint})
MERGE (an)-[:WorksOn]->(s)
MERGE (st)-[:WorksOn]->(s)
MERGE (co)-[:WorksOn]->(s);

