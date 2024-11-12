# MADT4BC: Multi-Aspect Digital Twin for Business Continuity

## Installation

This software requires the following versions of node and yarn:

```
node version v20.2.0
yarn version v1.22.19
```

Install dependencies:

```
yarn install
```

Make sure chart.js, react-chartjs-2 and cl-react-graph are installed, if not, use:

```
yarn add chart.js, react-chartjs-2, cl-react-graph
```

TODO: Update with docker build command for neodash & databases

To setup environment and run all services, we have two alternatives:

Navigate to the `connection` directory and build containers using following command for each subdirectory:

```
docker build -t minio -f Dockerfile .
docker build -t neo4j -f Dockerfile .
docker build -t influxdb -f Dockerfile .
docker build -t statistics -f Dockerfile .
docker build -t analytics -f Dockerfile .
```


## Setup

Launch databases in docker:

```
docker compose up
```

Run in another terminal:

```
yarn run dev
```

To run services, navigate to the `connection` directory, go to each corresponding subdirectory, and run: 

```
docker run -p 5000:5000 -v ${PWD}/temp:/usr/minio/temp --network=sindit_network -it minio
docker run -p 5001:5001 --network=sindit_network -it neo4j
docker run -p 4999:4999 -v ${PWD}/outputs:/usr/influxdb/outputs --network=sindit_network -it influxdb
docker run -p 5003:5003 --network=sindit_network -it statistics
docker run -p 5002:5002 -v ${PWD}/temp:/usr/analytics/temp --network=sindit_network -it analytics
```

TODO: Update with docker run command for neodash & databases

### Accessing Database and Dashboard

Open the minio database in browser: [http://localhost:9099](http://localhost:9099).
Log in with user name and password (detailed in docker compose file).

Create a user and set the policy to read-write. The access and secret keys need to be updated in the `connection/minio_config.ini` file, and in `statistics/minio_config.ini`.
Create a bucket and update the bucket name in `connection/minio_api.py` file. Add the PCAP file to the bucket. 

Open the neo4j database in browser: [http://localhost:7474](http://localhost:7474).
Log in with user name and password (detailed in docker compose file).

Open the dashboard in browser: [http://localhost:3000](http://localhost:3000), choose "New Dashboard". 
Log in with user name and password (detailed in docker compose file).

**Create database**: If the database is empty, you can load one by opening Neo4j Browser at [http://localhost:7474](http:localhost:7474). Copy the content from `samples/<latest-date-sample>.cypher` and past it into the query box of the Neo4j browser, then execute the query. The name/type of the PCAP file needs to correspond to the endpoint/type properties of the static node. 

**Load dashboard**: To load a dashboard at [http://localhost:3000](http://localhost:3000), press load dashboard button in left side panel. Choose "Select from file", and choose a sample dashboard (e.g. `samples/dashboard-<latest-date>.json`).

## User Guide for NeoDash

NeoDash comes with built-in examples of dashboards and reports. For more details on the types of reports and how to customize them, see the [User Guide](
https://neo4j.com/labs/neodash/2.2/user-guide/).


## Questions / Suggestions

If you have any questions about NeoDash, please reach out to the maintainers:
- Create an [Issue](https://github.com/neo4j-labs/neodash/issues/new) on GitHub for feature requests/bugs.
- Connect with us on the [Neo4j Discord](https://neo4j.com/developer/discord/).
- Create a post on the Neo4j [Community Forum](https://community.neo4j.com/).

> NeoDash is a free and open-source tool developed by the Neo4j community - not an official Neo4j product. If you have a need for a commercial agreement around training, custom extensions or other services, please contact the [Neo4j Professional Services](https://neo4j.com/professional-services/) team.
