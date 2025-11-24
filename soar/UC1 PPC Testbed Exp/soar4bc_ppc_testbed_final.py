"""
SOAR4BC - UC1 and UC1.2 Enhanced
Added Features:
- Topology listener for UC1.MADT4BC.full-topology
- Target UUID parsing from playbooks
"""

import json
import logging
import subprocess
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Any
import pytz
import re
import requests
from flask import Flask
from kafka import KafkaConsumer, KafkaProducer

# Suppress SSL warnings
requests.packages.urllib3.disable_warnings(requests.packages.urllib3.exceptions.InsecureRequestWarning)
logging.getLogger("kafka").setLevel(logging.WARNING)
logging.getLogger("kafka").setLevel(logging.ERROR)
logging.getLogger("kafka.conn").setLevel(logging.CRITICAL)
logging.getLogger("kafka.client").setLevel(logging.CRITICAL)
logging.getLogger("kafka.cluster").setLevel(logging.CRITICAL)
logging.getLogger("kafka.consumer").setLevel(logging.CRITICAL)
logging.getLogger("kafka.producer").setLevel(logging.CRITICAL)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class Config:
    """Configuration settings for the SOAR system"""
    # Kafka Configuration
    KAFKA_SERVER: str = 'kafka.dynabic.dev:9092'
    KAFKA_USERNAME: str = 'soar4bc'
    KAFKA_PASSWORD: str = 'xxxxx'
    PLAYBOOK_TOPIC: str = 'UC1.SOAR4BC.playbook'
    TOPOLOGY_TOPIC: str = 'UC1.MADT4BC.full-topology'
    RESULT_TOPIC: str = 'UC1.SOAR4BC.result'
    
    # Neo4j Configuration
    NEO4J_URL: str = "http://localhost:7474/db/neo4j/tx/commit"
    NEO4J_USERNAME: str = 'neo4j'
    NEO4J_PASSWORD: str = 'xxxxxx'
    
    # External APIs
    SDN_CONTROLLER_URI: str = "http://127.0.0.1:8080/firewall/rules/00001ac506786f40"
    PFSENSE_URI: str = "https://10.250.100.1/api/v2/firewall/rule"
    PFSENSE_API_KEY: str = 'xxxxxx'
    CSMS_URI: str = "https://dynabic-csms.trsc.net/api/ocpp16/setchargingprofile/"
    CSMS_TOKEN: str = 'Bearer xxxxxx'
    
    # System Configuration
    HONEYPOT_IP: str = "10.250.100.50"
    TIMEZONE: str = 'Europe/Berlin'
    HONEYPOT_SCRIPT: str = "/home/user/pentbox_run.sh"


class TimeTracker:
    """Utility class for tracking execution times"""
    
    @staticmethod
    def get_timestamp(timezone: str = Config.TIMEZONE) -> str:
        """Get current timestamp in specified timezone"""
        tz = pytz.timezone(timezone)
        return datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")
    
    @staticmethod
    def time_execution(func_name: str):
        """Decorator to time function execution"""
        def decorator(func):
            def wrapper(*args, **kwargs):
                start_time = time.time()
                result = func(*args, **kwargs)
                execution_time = time.time() - start_time
                logger.info(f"{func_name} execution time: {execution_time:.6f} seconds")
                return result
            return wrapper
        return decorator


class PlaybookParser:
    """Handles parsing of security playbooks"""
    
    SUPPORTED_ACTIONS = {
        "Block IP SDN Controller",
        "Block IP Firewall", 
        "Start Honeypot Server",
        "Redirect Traffic",
        "Reset Routing",
        "Stop Honeypot Server",
        "Overwrite Charging Profiles",
        "Do Nothing"
    }
    
    @staticmethod
    def extract_action(playbook_data: Dict[str, Any]) -> Optional[str]:
        """Extract action from playbook data"""
        try:
            workflow = playbook_data.get("workflow", {})
            for key, value in workflow.items():
                if value.get("type") == "action":
                    action_name = value.get("name")
                    if action_name in PlaybookParser.SUPPORTED_ACTIONS:
                        return action_name
                elif value.get("name") == "start workflow Do Nothing":
                    return "Do Nothing"
        except Exception as e:
            logger.error(f"Error extracting action: {e}")
        return None
    
    @staticmethod
    def extract_ips_from_playbook(playbook_data: Dict[str, Any]) -> Dict[str, Optional[str]]:
        result = {
            "attacker_ip": None,
            "attacker_uuid": None,
            "target_ip": None,
            "target_uuid": None,
        }

        try:
            external_refs = (
                playbook_data.get("external_references")
                or playbook_data.get("external_reference")
                or []
            )
            if isinstance(external_refs, dict):
                external_refs = [external_refs]

            attacker_uuid = None
            target_uuid = None
            object_refs = []
            ipv4_ref_ids = []

            for ref in external_refs:
                if not isinstance(ref, dict):
                    continue
                if ref.get("type") != "bundle":
                    continue

                objects = ref.get("objects", []) or []

                # observed-data → object_refs
                for obj in objects:
                    if obj.get("type") == "observed-data":
                        object_refs = obj.get("object_refs", []) or []
                        break

                # ipv4 refs → uuids
                ipv4_ref_ids = [rid for rid in object_refs if rid.startswith("ipv4-addr")]
                if len(ipv4_ref_ids) >= 1 and "--" in ipv4_ref_ids[0]:
                    attacker_uuid = ipv4_ref_ids[0].split("--", 1)[1]
                if len(ipv4_ref_ids) >= 2 and "--" in ipv4_ref_ids[1]:
                    target_uuid = ipv4_ref_ids[1].split("--", 1)[1]

                # ipv4 objects → attacker_ip / target_ip
                ipv4_objs = [o for o in objects if o.get("type") == "ipv4-addr"]
                if ipv4_objs:
                    if not result["attacker_ip"]:
                        result["attacker_ip"] = ipv4_objs[0].get("value")
                    if len(ipv4_objs) > 1 and not result["target_ip"]:
                        result["target_ip"] = ipv4_objs[1].get("value")

            # debug logs
            # logger.info(f"object_refs: {object_refs}")
            # logger.info(f"ipv4_ref_ids: {ipv4_ref_ids}")
            # logger.info(f"attacker_uuid local: {attacker_uuid}, target_uuid local: {target_uuid}")

            # FORCE the assignment into the result dict
            result["attacker_uuid"] = attacker_uuid
            result["target_uuid"] = target_uuid
            #logger.info(f"After assignment, result['target_uuid']: {result['target_uuid']}")

            # fallback only for missing attacker_ip / target_ip 
            if not result["attacker_ip"]:
                IPV4_RE = re.compile(
                    r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d{1,2})\.){3}"
                    r"(?:25[0-5]|2[0-4]\d|1?\d{1,2})\b"
                )
                serialized = json.dumps(playbook_data)
                matches = [ip for ip in IPV4_RE.findall(serialized) if ip != "0.0.0.1"]
                if matches:
                    result["attacker_ip"] = matches[0]
                    if len(matches) > 1 and not result["target_ip"]:
                        result["target_ip"] = matches[1]

            logger.info(f"Extracted IPs from playbook: {result}")

        except Exception as e:
            logger.error(f"Error extracting IPs from playbook: {e}")

        return result
    
    # @staticmethod
    # def extract_ips_from_playbook(playbook_data: Dict[str, Any]) -> Dict[str, Optional[str]]:
    #     """
    #     Extract both attacker IP (source) and target IP/UUID from playbook data
    #     Returns dict with 'attacker_ip', 'target_ip', and 'target_uuid'
    #     """
    #     result = {
    #         "attacker_ip": None,
    #         "target_ip": None,
    #         "target_uuid": None
    #     }
        
    #     try:
    #         external_references = playbook_data.get("external_reference", []) or playbook_data.get("external_references", [])
            
    #         for ref in external_references:
    #             if ref.get("type") == "bundle":
    #                 objects = ref.get("objects", [])
                    
    #                 # First pass: find the observed-data to get object_refs
    #                 object_refs = []
    #                 for obj in objects:
    #                     if obj.get("type") == "observed-data":
    #                         object_refs = obj.get("object_refs", [])
    #                         break
                    
    #                 # Second pass: extract IPs based on their IDs
    #                 for obj in objects:
    #                     if obj.get("type") == "ipv4-addr":
    #                         obj_id = obj.get("id", "")
    #                         ip_value = obj.get("value")
                            
    #                         if ip_value and ip_value != "0.0.0.1":
    #                             # Extract UUID from the ID (format: ipv4-addr--<uuid>)
    #                             uuid = obj_id.split("--")[-1] if "--" in obj_id else None
                                
    #                             # Determine if this is target or attacker based on position in object_refs
    #                             # First IP is usually attacker (source) and second is target (destination)
    #                             if obj_id in object_refs:
    #                                 idx = object_refs.index(obj_id)
    #                                 if idx == 0:
    #                                     result["attacker_ip"] = ip_value
    #                                 elif idx == 1:
    #                                     result["target_ip"] = ip_value
    #                                     result["target_uuid"] = uuid
                    
    #                 # Fallback: if we didn't identify properly, use any non-placeholder IP
    #                 if not result["attacker_ip"]:
    #                     for obj in objects:
    #                         if obj.get("type") == "ipv4-addr":
    #                             ip_value = obj.get("value")
    #                             if ip_value and ip_value != "0.0.0.1":
    #                                 result["attacker_ip"] = ip_value
    #                                 break
        
    #     except Exception as e:
    #         logger.error(f"Error extracting IPs from playbook: {e}")
        
    #     return result


class Neo4jDashboard:
    """Handles Neo4j database operations for dashboard updates"""
    
    def __init__(self, config: Config):
        self.url = config.NEO4J_URL
        self.auth = (config.NEO4J_USERNAME, config.NEO4J_PASSWORD)
    
    def cleanup_old_data(self):
        """Clean up old data from Neo4j database"""
        try:
            data = {
                "statements": [
                    {"statement": "MATCH (s:SOAR)-[r:RESPONSE]->(resp:RESPONSE) DELETE s, r, resp"},
                    {"statement": "MATCH (a:Attacker) DELETE a"}
                ]
            }
            requests.post(self.url, auth=self.auth, json=data)
        except Exception as e:
            logger.error(f"Error cleaning up Neo4j: {e}")
    
    def clear_topology(self):
        """Clear existing topology data from Neo4j"""
        try:
            data = {
                "statements": [
                    {"statement": "MATCH (n:ASSET) DETACH DELETE n"},
                    {"statement": "MATCH (n:DATASOURCE) DETACH DELETE n"},
                    {"statement": "MATCH (n:EVENT) DETACH DELETE n"},
                    {"statement": "MATCH (n:ATTACKER) DETACH DELETE n"}
                ]
            }
            response = requests.post(self.url, auth=self.auth, json=data)
            if response.status_code == 200:
                logger.info("Topology data cleared from Neo4j")
            else:
                logger.error(f"Failed to clear topology: {response.status_code}")
        except Exception as e:
            logger.error(f"Error clearing topology: {e}")
    
    def insert_topology(self, topology_data: List[Dict[str, Any]]):
        """
        Insert topology data into Neo4j database
        Expected format: List of relationship records with 'n', 'r', 'm' structure
        """
        try:
            logger.info(f"Inserting {len(topology_data)} topology records into Neo4j")
            
            # Clear existing topology first
            self.clear_topology()
            
            statements = []
            
            for record in topology_data:
                try:
                    # Extract node 'n' (source)
                    n = record.get("n", {})
                    n_labels = ":".join(n.get("labels", []))
                    n_props = n.get("properties", {})
                    
                    # Extract relationship 'r'
                    r = record.get("r", {})
                    r_type = r.get("type", "RELATES_TO")
                    r_props = r.get("properties", {})
                    
                    # Extract node 'm' (target)
                    m = record.get("m", {})
                    m_labels = ":".join(m.get("labels", []))
                    m_props = m.get("properties", {})
                    
                    # Build Cypher query
                    # Create or merge source node
                    n_prop_str = ", ".join([f"n.{k} = ${k}_n" for k in n_props.keys()])
                    m_prop_str = ", ".join([f"m.{k} = ${k}_m" for k in m_props.keys()])
                    
                    query = f"""
                    MERGE (n:{n_labels} {{uid: $uid_n}})
                    SET {n_prop_str}
                    MERGE (m:{m_labels} {{uid: $uid_m}})
                    SET {m_prop_str}
                    MERGE (n)-[r:{r_type}]->(m)
                    """
                    
                    # Prepare parameters
                    parameters = {}
                    for k, v in n_props.items():
                        parameters[f"{k}_n"] = v
                    for k, v in m_props.items():
                        parameters[f"{k}_m"] = v
                    
                    statements.append({
                        "statement": query,
                        "parameters": parameters
                    })
                
                except Exception as e:
                    logger.error(f"Error processing topology record: {e}")
                    continue
            
            # Execute all statements in batches
            batch_size = 100
            for i in range(0, len(statements), batch_size):
                batch = statements[i:i+batch_size]
                data = {"statements": batch}
                response = requests.post(self.url, auth=self.auth, json=data)
                
                if response.status_code == 200:
                    logger.info(f"Inserted topology batch {i//batch_size + 1}")
                else:
                    logger.error(f"Failed to insert topology batch: {response.status_code}")
            
            logger.info("Topology insertion completed")
        
        except Exception as e:
            logger.error(f"Error inserting topology into Neo4j: {e}")
    
    def update_attacker_status(self, attacker_ip: str, status: str, target_uuid: str = None):
        """Update attacker node status with optional target UUID"""
        try:
            timestamp = TimeTracker.get_timestamp()
            query = """
            MERGE (a:Attacker {ip: $attacker_ip})
            ON CREATE SET a.status = $status, a.timestamp = $timestamp, a.target_uuid = $target_uuid
            ON MATCH SET a.status = $status, a.timestamp = $timestamp, a.target_uuid = $target_uuid
            """
            data = {
                "statements": [{
                    "statement": query,
                    "parameters": {
                        "attacker_ip": attacker_ip,
                        "status": status,
                        "timestamp": timestamp,
                        "target_uuid": target_uuid
                    }
                }]
            }
            requests.post(self.url, auth=self.auth, json=data)
            logger.info(f"Updated attacker {attacker_ip} status to: {status} ")
        except Exception as e:
            logger.error(f"Error updating attacker node: {e}")
    
    def update_response(
        self,
        attacker_ip: str,
        response: str,
        reason: str,
        human_in_loop: str = "no",
        human_decision: str = "auto",
        target_uuid: str = None
    ):
        """Update SOAR response in dashboard"""
        self.cleanup_old_data()
        try:
            timestamp = TimeTracker.get_timestamp()
            query = (
                "MERGE (s:SOAR {ip: $attacker_ip}) "
                "CREATE (s)-[:RESPONSE]->(resp:RESPONSE {"
                "ip: $attacker_ip, "
                "response: $response, "
                "reason: $reason, "
                "timestamp: $timestamp, "
                "human_in_the_loop: $human_in_loop, "
                "human_decision: $human_decision, "
                "target_uuid: $target_uuid})"
            )
            data = {
                "statements": [{
                    "statement": query,
                    "parameters": {
                        "attacker_ip": attacker_ip,
                        "response": response,
                        "reason": reason,
                        "timestamp": timestamp,
                        "human_in_loop": human_in_loop,
                        "human_decision": human_decision,
                        "target_uuid": target_uuid
                    }
                }]
            }
            response_obj = requests.post(self.url, auth=self.auth, json=data)
            if response_obj.status_code == 200:
                logger.info("Neo4j dashboard updated successfully")
            else:
                logger.error(f"Failed to update Neo4j dashboard: {response_obj.status_code}")
        except Exception as e:
            logger.error(f"Error updating Neo4j dashboard: {e}")


class ActionExecutor(ABC):
    """Abstract base class for action executors"""
    
    def __init__(self, config: Config, dashboard: Neo4jDashboard):
        self.config = config
        self.dashboard = dashboard
    
    @abstractmethod
    def execute(self, attacker_ip: str, target_uuid: str = None) -> Dict[str, Any]:
        """Execute the action and return result"""
        pass
    
    def publish_result(self, producer: KafkaProducer, attacker_ip: str, target_ip: str,
                      action: str, status: str, details: str, 
                      human_in_loop: bool = False, human_decision: str = None,
                      attacker_uuid: str = None, target_uuid: str = None):
        """Publish action result to Kafka"""
        try:
            result_payload = {
                "action": action,
                "attacker_ip": attacker_ip,
                "attacker_uuid": attacker_uuid,
                "target_ip": target_ip,
                "target_uuid": target_uuid,
                "status": status,
                "details": details,
                "timestamp": TimeTracker.get_timestamp(),
                "human_in_the_loop": "yes" if human_in_loop else "no",
                "human_in_the_loop_decision": human_decision if human_in_loop else "auto"
            }
            producer.send(self.config.RESULT_TOPIC, result_payload)
            producer.flush()
            logger.info(f"Published action result to Kafka topic {self.config.RESULT_TOPIC}")
        except Exception as e:
            logger.error(f"Error publishing action result to Kafka: {e}")


class SDNBlockExecutor(ActionExecutor):
    """Executor for SDN Controller IP blocking"""
    
    @TimeTracker.time_execution("SDN Block Action")
    def execute(self, attacker_ip: str, target_uuid: str = None) -> Dict[str, Any]:
        firewall_rule = {
            "nw_src": f"{attacker_ip}/32",
            "priority": 1,
            "actions": "DENY"
        }
        
        logger.info(f"Blocking IP {attacker_ip} via SDN Controller")
        
        try:
            response = requests.post(
                self.config.SDN_CONTROLLER_URI,
                headers={'Content-Type': 'application/json'},
                data=json.dumps(firewall_rule)
            )
            
            if response.status_code == 200:
                logger.info(f"Successfully blocked {attacker_ip} on SDN Controller")
                self.dashboard.update_response(
                    attacker_ip, 
                    "Block Attacker IP by Ryu SDN", 
                    "Potential DoS Detected Against CSMS",
                    target_uuid=target_uuid
                )
                self.dashboard.update_attacker_status(attacker_ip, "Blocked", target_uuid)
                return {"status": "success", "message": "IP blocked successfully"}
            else:
                logger.error(f"Failed to block {attacker_ip}: {response.status_code}")
                return {"status": "error", "message": f"Failed to block IP: {response.text}"}
        except Exception as e:
            logger.error(f"Error blocking IP via SDN: {e}")
            return {"status": "error", "message": str(e)}


class FirewallBlockExecutor(ActionExecutor):
    """Executor for pfSense firewall IP blocking"""
    
    @TimeTracker.time_execution("Firewall Block Action")
    def execute(self, attacker_ip: str, target_uuid: str = None) -> Dict[str, Any]:
        headers = {
            'accept': 'application/json',
            'x-api-key': self.config.PFSENSE_API_KEY,
            'Content-Type': 'application/json'
        }
        
        payload = {
            "type": "block",
            "interface": ["WAN"],
            "ipprotocol": "inet",
            "source": attacker_ip,
            "destination": "any",
            "descr": "Automatic rule by DYNABIC SOAR"
        }
        
        logger.info(f"Blocking IP {attacker_ip} via pfSense firewall")
        
        try:
            response = requests.post(
                self.config.PFSENSE_URI,
                headers=headers,
                data=json.dumps(payload),
                verify=False
            )
            
            if response.status_code == 200:
                logger.info(f"Successfully blocked {attacker_ip} via pfSense")
                self.dashboard.update_response(
                    attacker_ip,
                    "Block Attacker IP by pfSense",
                    "Potential DoS Detected Against CSMS",
                    human_in_loop="no",
                    human_decision="disapproved",
                    target_uuid=target_uuid
                )
                self.dashboard.update_attacker_status(attacker_ip, "Blocked", target_uuid)
                return {"status": "success", "message": "IP blocked successfully", "human_in_the_loop": False, "human_in_the_loop_decision": "disapproved"}
            else:
                logger.error(f"Failed to block {attacker_ip} via pfSense: {response.status_code}")
                return {"status": "error", "message": f"Failed to block IP: {response.text}"}
        except Exception as e:
            logger.error(f"Error blocking IP via pfSense: {e}")
            return {"status": "error", "message": str(e)}


class ChargingProfileExecutor(ActionExecutor):
    """Executor for overwriting charging profiles"""
    
    @TimeTracker.time_execution("Charging Profile Override Action")
    def execute(self, attacker_ip: str, target_uuid: str = None) -> Dict[str, Any]:
        headers = {
            'accept': 'application/json',
            'Authorization': self.config.CSMS_TOKEN,
            'Content-Type': 'application/json'
        }
        
        payload = {
            "chargepoint_id": "CS-ABB-00001",
            "ip_address": attacker_ip,
            "sync": True,
            "connector_id": 0,
            "charging_profile_id": 1
        }
        
        logger.info(f"Setting predefined charging profile for attacker {attacker_ip}")
        
        try:
            response = requests.post(
                self.config.CSMS_URI,
                headers=headers,
                data=json.dumps(payload),
                verify=False
            )
            
            if response.status_code == 200:
                logger.info("Charging profile overwritten successfully")
                self.dashboard.update_response(
                    attacker_ip,
                    "Overwrite Charging Profile",
                    "MiTM Attack Detected Against CSMS",
                    human_in_loop="yes",
                    human_decision="approved",
                    target_uuid=target_uuid
                )
                self.dashboard.update_attacker_status(attacker_ip, "Blocked", target_uuid)
                return {"status": "success", "message": "Charging profile overwritten", "human_in_the_loop": True, "human_in_the_loop_decision": "approved"}
            else:
                logger.error(f"Failed to update charging profile: {response.status_code}")
                return {"status": "error", "message": f"Failed to update profile: {response.text}"}
        except Exception as e:
            logger.error(f"Error updating charging profile: {e}")
            return {"status": "error", "message": str(e)}


class HoneypotExecutor(ActionExecutor):
    """Executor for honeypot operations"""
    
    @TimeTracker.time_execution("Honeypot Action")
    def execute(self, attacker_ip: str, target_uuid: str = None) -> Dict[str, Any]:
        try:
            # Start honeypot server
            subprocess.run(["sudo", self.config.HONEYPOT_SCRIPT], check=True)
            logger.info("Pentbox honeypot server started successfully")
            
            # Redirect traffic
            redirect_cmd = (
                f"iptables -t nat -A PREROUTING -p tcp -s {attacker_ip} "
                f"--dport 80 -j DNAT --to-destination {self.config.HONEYPOT_IP}:80"
            )
            subprocess.run(redirect_cmd, shell=True, check=True)
            logger.info(f"Traffic from {attacker_ip} redirected to honeypot")
            
            self.dashboard.update_response(
                attacker_ip,
                "Start Pentbox Honeypot and Redirect Attacker Traffic",
                "Potential DoS Detected Against CSMS",
                target_uuid=target_uuid
            )
            self.dashboard.update_attacker_status(attacker_ip, "Redirecting Traffic", target_uuid)
            
            return {"status": "success", "message": "Honeypot started and traffic redirected"}
        except subprocess.CalledProcessError as e:
            logger.error(f"Error with honeypot operations: {e}")
            return {"status": "error", "message": str(e)}


class TrafficRedirectExecutor(ActionExecutor):
    """Executor for traffic redirection"""
    
    def execute(self, attacker_ip: str, target_uuid: str = None) -> Dict[str, Any]:
        try:
            redirect_cmd = (
                f"iptables -t nat -A PREROUTING -p tcp -s {attacker_ip} "
                f"--dport 80 -j DNAT --to-destination {self.config.HONEYPOT_IP}:80"
            )
            subprocess.run(redirect_cmd, shell=True, check=True)
            logger.info(f"Traffic from {attacker_ip} redirected to honeypot")
            
            self.dashboard.update_response(
                attacker_ip,
                "Redirect Traffic to Honeypot",
                "Traffic Redirection Activated",
                target_uuid=target_uuid
            )
            self.dashboard.update_attacker_status(attacker_ip, "Redirecting Traffic")
            
            return {"status": "success", "message": "Traffic redirected successfully"}
        except subprocess.CalledProcessError as e:
            logger.error(f"Error redirecting traffic: {e}")
            return {"status": "error", "message": str(e)}


class ResetRoutingExecutor(ActionExecutor):
    """Executor for resetting routing and stopping honeypot"""
    
    def execute(self, attacker_ip: str, target_uuid: str = None) -> Dict[str, Any]:
        try:
            # Reset routing
            reset_cmd = (
                f"iptables -t nat -D PREROUTING -p tcp -s {attacker_ip} "
                f"--dport 80 -j DNAT --to-destination {self.config.HONEYPOT_IP}:80"
            )
            subprocess.run(reset_cmd, shell=True, check=True)
            logger.info(f"Routing reset for {attacker_ip}")
            
            # Stop honeypot
            try:
                find_process_cmd = "sudo lsof -t -i:80"
                process_id = subprocess.check_output(find_process_cmd, shell=True).strip().decode('utf-8')
                
                if process_id:
                    kill_cmd = f"sudo kill -9 {process_id}"
                    subprocess.run(kill_cmd, shell=True, check=True)
                    logger.info(f"Honeypot server stopped (PID: {process_id})")
            except subprocess.CalledProcessError:
                logger.info("No honeypot process found running on port 80")
            
            self.dashboard.update_response(
                attacker_ip,
                "Reset Routing and Stop Honeypot",
                "Reset Routing and Honeypot Stopped After Mitigation",
                target_uuid=target_uuid
            )
            self.dashboard.update_attacker_status(attacker_ip, "Quarantined: Reset Traffic and Stop Honeypot", target_uuid)
            
            return {"status": "success", "message": "Routing reset and honeypot stopped"}
        except subprocess.CalledProcessError as e:
            logger.error(f"Error resetting routing: {e}")
            return {"status": "error", "message": str(e)}


class DoNothingExecutor(ActionExecutor):
    """Executor for do nothing action"""
    
    def execute(self, attacker_ip: str, target_uuid: str = None) -> Dict[str, Any]:
        logger.info("Executing 'Do Nothing' action")
        self.dashboard.update_response(attacker_ip, "Do Nothing", "Nothing to Execute", target_uuid=target_uuid)
        self.dashboard.update_attacker_status(attacker_ip, "Not Blocked", target_uuid)
        return {"status": "success", "message": "No action taken"}


class ActionFactory:
    """Factory for creating action executors"""
    
    @staticmethod
    def create_executor(action: str, config: Config, dashboard: Neo4jDashboard) -> Optional[ActionExecutor]:
        """Create appropriate executor for the given action"""
        executors = {
            "Block IP SDN Controller": SDNBlockExecutor,
            "Block IP Firewall": FirewallBlockExecutor,
            "Overwrite Charging Profiles": ChargingProfileExecutor,
            "Start Honeypot Server": HoneypotExecutor,
            "Redirect Traffic": TrafficRedirectExecutor,
            "Reset Routing": ResetRoutingExecutor,
            "Stop Honeypot Server": ResetRoutingExecutor,
            "Do Nothing": DoNothingExecutor
        }
        
        executor_class = executors.get(action)
        return executor_class(config, dashboard) if executor_class else None


class KafkaManager:
    """Manages Kafka connections and operations"""
    
    def __init__(self, config: Config):
        self.config = config
        self.kafka_config = {
            'bootstrap_servers': [config.KAFKA_SERVER],
            'security_protocol': 'SASL_PLAINTEXT',
            'sasl_mechanism': 'PLAIN',
            'sasl_plain_username': config.KAFKA_USERNAME,
            'sasl_plain_password': config.KAFKA_PASSWORD
        }
    
    def create_producer(self) -> KafkaProducer:
        """Create Kafka producer"""
        return KafkaProducer(
            **self.kafka_config,
            value_serializer=lambda x: json.dumps(x).encode('utf-8')
        )
    
    def create_consumer(self, topics: List[str], group_id: str) -> KafkaConsumer:
        """Create Kafka consumer for specified topics"""
        return KafkaConsumer(
            *topics,
            **self.kafka_config,
            group_id=group_id,
            auto_offset_reset='latest',
            enable_auto_commit=True,
            value_deserializer=lambda x: json.loads(x.decode('utf-8')) if x else None
        )


class SOAROrchestrator:
    """Main SOAR orchestrator that coordinates all components"""
    
    def __init__(self, config: Config = None):
        self.config = config or Config()
        self.dashboard = Neo4jDashboard(self.config)
        self.kafka_manager = KafkaManager(self.config)
        self.producer = self.kafka_manager.create_producer()
        self.app = Flask(__name__)
    
    def process_topology(self, topology_data: Any):
        """Process received topology data and insert into Neo4j"""
        try:
            logger.info("Received topology data from Kafka")
            start_time = time.time()
            
            # Validate topology data format
            if not isinstance(topology_data, list):
                logger.error("Invalid topology format: expected list")
                return
            
            # Insert topology into Neo4j
            self.dashboard.insert_topology(topology_data)
            
            processing_time = time.time() - start_time
            logger.info(f"Topology processing time: {processing_time:.6f} seconds")
        
        except Exception as e:
            logger.error(f"Error processing topology: {e}")
    
    def process_playbook(self, playbook_data: Dict[str, Any]):
        """Process received playbook and execute appropriate action"""
        try:
            logger.info("Received playbook from Kafka")
            
            # Extract action and IP
            start_time = time.time()
            action = PlaybookParser.extract_action(playbook_data)
            ips = PlaybookParser.extract_ips_from_playbook(playbook_data)
            attacker_ip = ips.get("attacker_ip")
            attacker_uuid = ips.get("attacker_uuid")
            target_ip = ips.get("target_ip")
            target_uuid = ips.get("target_uuid")
            extraction_time = time.time() - start_time
            logger.info(f"Playbook extraction time: {extraction_time:.6f} seconds")
            
            if not attacker_ip:
                logger.error("Attacker IP not found in playbook")
                return
            
            if not action:
                logger.error("No valid action found in playbook")
                return
            
            # Create and execute action
            executor = ActionFactory.create_executor(action, self.config, self.dashboard)
            if executor:
                start_time = time.time()
                result = executor.execute(attacker_ip)
                execution_time = time.time() - start_time
                logger.info(f"Action execution time: {execution_time:.6f} seconds")
                
                # Publish result
                human_flag = result.get("human_in_the_loop", False)
                human_decision = result.get("human_in_the_loop_decision", None)
                executor.publish_result(
                    self.producer, attacker_ip, target_ip, action,
                    result["status"], result["message"],
                    human_in_loop=human_flag,
                    human_decision=human_decision,
                    target_uuid=target_uuid,
                    attacker_uuid=attacker_uuid
                )
            else:
                logger.error(f"Unknown action: {action}")
        
        except Exception as e:
            logger.error(f"Error processing playbook: {e}")
    
    def kafka_consumer_loop(self):
        consumer = self.kafka_manager.create_consumer(
            topics=[self.config.PLAYBOOK_TOPIC, self.config.TOPOLOGY_TOPIC],
            group_id="soar4bc-consumer-group"
        )

        logger.info(f"Listening for messages on topics: "
                    f"{self.config.PLAYBOOK_TOPIC}, {self.config.TOPOLOGY_TOPIC}")

        try:
            for message in consumer:
                if not message.value:
                    continue

                topic = message.topic
                value = message.value

                if topic == self.config.PLAYBOOK_TOPIC:
                    self.process_playbook(value)

                elif topic == self.config.TOPOLOGY_TOPIC:
                    self.process_topology(value)

                else:
                    logger.warning(f"Received message from unknown topic: {topic}")

        except Exception as e:
            logger.error(f"Error in Kafka consumer loop: {e}")

        finally:
            consumer.close()

    
    def start_kafka_consumer(self):
        """Start Kafka consumer in a separate thread"""
        kafka_thread = threading.Thread(target=self.kafka_consumer_loop, daemon=True)
        kafka_thread.start()
        return kafka_thread
    
    def initialize_system(self):
        """Initialize the SOAR system"""
        def print_event_handler_message():
            self.dashboard.cleanup_old_data()
            # start_time = time.time()
            # time.sleep(7)  # Wait for detection system
            # logger.info("Potential attack against CSMS detected")
            # detection_time = time.time() - start_time
            # logger.info(f"Attack Detection Time: {detection_time:.6f} seconds")
            logger.info("Waiting for Playbook via Kafka...")
        
        # Start event handler thread
        threading.Thread(target=print_event_handler_message, daemon=True).start()
        
        # Start Kafka consumer
        return self.start_kafka_consumer()
    
    def run(self):
        """Run the SOAR system"""
        logger.info("Starting SOAR4BC System...")
        kafka_thread = self.initialize_system()
        
        try:
            # Keep main thread alive
            kafka_thread.join()
        except KeyboardInterrupt:
            logger.info("SOAR system stopped by user")
        except Exception as e:
            logger.error(f"Error running SOAR system: {e}")


def main():
    """Main entry point"""
    soar = SOAROrchestrator()
    soar.run()


if __name__ == '__main__':
    main()
