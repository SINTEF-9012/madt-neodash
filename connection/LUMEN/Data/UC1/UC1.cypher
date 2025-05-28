CREATE (n:ASSET {name:"CSMS", uc: 1,  layer:"Functional", description: "Charging Station Management System: cloud-based platform for electric vehicle charging station management.",  ip: "192.168.21.70", uid: "53a565c1-f81b-4b38-861e-51ffdba2b1f8"});
CREATE (n:ASSET {name:"switch_1",  uc: 1, layer:"Network", description: "Switch.",  ip: "192.168.21.215", uid: "d5694e14-16a3-4397-9141-b608e1aef8b7"});
CREATE (n:ASSET {name:"switch_2",  uc: 1, layer:"Network", description: "Switch.",  ip: "192.168.21.128", uid: "3080086b-8c79-49c8-a48e-375fa026c811"});
CREATE (n:ASSET {name:"router",  uc: 1, layer:"Network", description: "Router that provides Internet access and functions as a VPN gateway and firewall.",  ip: "192.168.21.120", uid: "7a5fc9ef-6b4a-4de6-89c4-745f9c511a3a"});
CREATE (n:ASSET {name:"EVCS_1",  uc: 1, layer:"Physical", description: "Electric Vehicle Charging Station.",  ip: "192.168.21.233", uid: "832ebdb3-b51c-4719-9d21-5260f8cab966"});
CREATE (n:ASSET {name:"EVCS_2",  uc: 1, layer:"Physical", description: "Electric Vehicle Charging Station.",  ip: "192.168.21.225", uid: "9d2a741a-d2e4-4cb6-b757-b1223e5cca98"});
CREATE (n:ASSET {name:"FPR",  uc: 1, layer:"Physical", description: "Safeguards against grid anomalies such as overcurrent or overvoltage events.",  ip: "192.168.21.228", uid:"49ec91b9-86c6-49e4-97ae-58af0b173420"});

MATCH (a:ASSET), (b:ASSET) WHERE a.name = "EVCS_1" AND b.name = "FPR"
CREATE (b)-[r:ConnectTo]->(a);

MATCH (a:ASSET), (b:ASSET) WHERE a.name = "EVCS_2" AND b.name = "FPR"
CREATE (b)-[r:ConnectTo]->(a);

MATCH (a:ASSET), (b:ASSET), (c:ASSET) WHERE a.name = "EVCS_1" AND b.name = "EVCS_2" AND c.name = "switch_1"
CREATE (a)-[r:ConnectTo]->(c)<-[j:ConnectTo]-(b);

MATCH (a:ASSET), (b:ASSET), (c:ASSET) WHERE a.name = "switch_2" AND b.name = "switch_1" AND c.name = "router"
CREATE (b)-[r:ConnectTo]->(c)-[j:ConnectTo]->(a);

MATCH (a:ASSET), (b:ASSET) WHERE a.name = "switch_2" AND b.name = "CSMS"
CREATE (b)-[r:ConnectTo]->(a);

MATCH (a:ASSET), (b:ASSET) WHERE a.name = "router" AND b.name = "switch_2"
CREATE (a)-[r:Secures]->(b);

CREATE (n:DATASOURCE {name:"CSMS_CIC", uc: 1, type:"cicflowmeter", format:"timeseries", uid: "8f081e80-1c4e-4f54-a3b6-80357d9a68de"});
CREATE (n:DATASOURCE {name:"CSMS_OCPP", uc: 1, type:"ocppflowmeter", format:"timeseries", uid: "a62944bd-d9fb-4cda-80f2-f277d5ce8da1"});
CREATE (n:DATASOURCE {name:"CSMS_MetricBeat", uc: 1, type:"metricbeat", format:"timeseries", uid: "25f33f41-3d65-4191-bab8-87cd21c30d93"});

MATCH (a:DATASOURCE), (b:ASSET) WHERE a.name = "CSMS_CIC" AND b.name = "switch_2"
CREATE (a)-[r:DataSourceOf]->(b);
MATCH (a:DATASOURCE), (b:ASSET) WHERE a.name = "CSMS_OCPP" AND b.name = "switch_2"
CREATE (a)-[r:DataSourceOf]->(b);
MATCH (a:DATASOURCE), (b:ASSET) WHERE a.name = "CSMS_MetricBeat" AND b.name = "CSMS"
CREATE (a)-[r:DataSourceOf]->(b);

MATCH (a:ASSET) WHERE a.name = "switch_1" CREATE (s:STATICDATA {name: a.name + "_StaticData", uc: 1, type: "", file_name: "", add_date: "", format: "", uid: "1a2230d0-277f-4cdf-8ccf-a02952447a8b"})
MERGE (s)-[:StaticDataOf]->(a);
MATCH (a:ASSET) WHERE a.name = "switch_2" CREATE (s:STATICDATA {name: a.name + "_StaticData", uc: 1, type: "", file_name: "", add_date: "", format: "", uid: "aabba598-d5c5-4825-8552-c71a65460ed8"})
MERGE (s)-[:StaticDataOf]->(a);

MATCH (a:ASSET)<-[:DataSourceOf]-(d:DATASOURCE)
SET d.bucket = d.uid;

MATCH (a:ASSET)<-[:StaticDataOf]-(d:STATICDATA)
SET d.bucket = d.uid;


### StaticData contents: 
switch-1 StaticData: metricbeat.json
switch_2 StaticData: 20230511_Denial_of_Charge_IdTag_filtered_pcaplabelled.pcap
### DataSource contents:
CIC - see HeartDDoS doc
MetricBeat - see HeartDDoS doc
OCPP - see HeartDDoS doc
