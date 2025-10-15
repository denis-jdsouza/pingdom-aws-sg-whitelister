"""
Automation to whitelist Pingdom probe IPs in AWS Security Group
based on a selected region (NA, EU, APAC, LATAM).
"""

import ipaddress
import os
import sys
import requests
import boto3

# Constants
PINGDOM_API_URL = "https://api.pingdom.com/api/3.1/probes"  # Pingdom IP feed
AWS_SG_RULE_LIMIT = 60
AWS_SG_RULE_PORT = 443
RULE_DESCRIPTION = "Pingdom probe rule added via automation"

# Env vars
AWS_SG_ID = os.getenv("AWS_SG_ID")
AWS_REGION = os.getenv("AWS_REGION")
DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"
JENKINS_URL = os.getenv("JENKINS_URL")
JOB_NAME = os.getenv("JOB_NAME")
PINGDOM_API_TOKEN = os.getenv("PINGDOM_API_TOKEN")
PINGDOM_REGION = os.getenv("PINGDOM_REGION", "NA").upper()  # Default "NA"

# Slack config
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_CHANNEL = "#alerts"


def fetch_pingdom_probes():
    """
    Fetch all Pingdom probes via API
    """
    headers = {"Authorization": f"Bearer {PINGDOM_API_TOKEN}"}
    resp = requests.get(PINGDOM_API_URL, headers=headers, timeout=10)
    resp.raise_for_status()
    return resp.json()


def extract_pingdom_region_ipv4(data, region):
    """
    Extract active IPv4 probe IPs for the given region.
    Region can be NA, EU, APAC, LATAM
    """
    cidrs = []
    for probe in data.get("probes", []):
        if probe.get("region") == region and probe.get("ip") != "NULL":
            ip = probe.get("ip")
            cidrs.append(f"{ip}/32")  # convert to CIDR /32

    return sorted(cidrs, key=ipaddress.ip_network)


def get_sg_ingress_rules():
    """
    Get current ingress rules on AWS SG (port 443/tcp).
    """
    ec2 = boto3.client("ec2", region_name=AWS_REGION)
    ec2_sg = ec2.describe_security_groups(GroupIds=[AWS_SG_ID])["SecurityGroups"][0]
    rules = []
    for perm in ec2_sg.get("IpPermissions", []):
        if perm.get("IpProtocol") == "tcp" and perm.get("FromPort") == AWS_SG_RULE_PORT:
            rules.extend([ip["CidrIp"] for ip in perm.get("IpRanges", [])])
    return sorted(rules, key=ipaddress.ip_network)


def replace_sg_ingress_rules(after_cidrs, current_cidrs):
    """
    Update AWS security group rules incrementally:
    - Add only missing CIDRs
    - Remove only stale CIDRs
    - Preserve unchanged rules
    """
    ec2 = boto3.client("ec2", region_name=AWS_REGION)
    print("\n⚡ Checking Security Group for differences...")
    to_add = sorted(set(after_cidrs) - set(current_cidrs), key=ipaddress.ip_network)
    to_remove = sorted(set(current_cidrs) - set(after_cidrs), key=ipaddress.ip_network)

    if not to_add and not to_remove:
        print("\n✅ No changes detected in SG rules.")
        return

    # Remove stale rules
    if to_remove:
        print(f"\n🗑  Removing below {len(to_remove)} stale rules...")
        for cidr in to_remove:
            print(f"  {cidr}")
        if not DRY_RUN:
            revoke_payload = [{
                "IpProtocol": "tcp",
                "FromPort": AWS_SG_RULE_PORT,
                "ToPort": AWS_SG_RULE_PORT,
                "IpRanges": [{"CidrIp": c} for c in to_remove]
            }]
            ec2.revoke_security_group_ingress(
                GroupId=AWS_SG_ID, IpPermissions=revoke_payload)

    # Add missing rules
    if to_add:
        print(f"\n➕ Adding below {len(to_add)} new rules...")
        for cidr in to_add:
            print(f"  {cidr}")
        if not DRY_RUN:
            auth_payload = [{
                "IpProtocol": "tcp",
                "FromPort": AWS_SG_RULE_PORT,
                "ToPort": AWS_SG_RULE_PORT,
                "IpRanges": [{"CidrIp": c, "Description": RULE_DESCRIPTION} for c in to_add]
            }]
            ec2.authorize_security_group_ingress(
                GroupId=AWS_SG_ID, IpPermissions=auth_payload)

    if DRY_RUN:
        print("\n🟡 DRY-RUN mode: Not updating SG in AWS.")
        sys.exit()


def send_slack_alert(message: str):
    """
    Send Slack notifications
    """
    if not SLACK_BOT_TOKEN:
        print("⚠️ SLACK_BOT_TOKEN not set, exiting..")
        sys.exit(1)

    headers = {
        "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {"channel": SLACK_CHANNEL, "text": message, "mrkdwn": True}

    try:
        resp = requests.post("https://slack.com/api/chat.postMessage",
                             headers=headers, json=payload, timeout=10)
        data = resp.json()
        if not data.get("ok"):
            raise Exception(data)
        print(f"\n📤 Slack alert sent to {SLACK_CHANNEL}")
    except Exception as e:
        print(f"❌ Failed to send Slack alert: {e}")


def main():
    print(f"🔍 Fetching Pingdom probes from {PINGDOM_API_URL} ...\n")
    data = fetch_pingdom_probes()
    new_cidrs = extract_pingdom_region_ipv4(data, PINGDOM_REGION)

    print(f"✅ Total {PINGDOM_REGION} IPv4 probes: {len(new_cidrs)}")
    for cidr in new_cidrs:
        print(f"  {cidr}")

    current_cidrs = get_sg_ingress_rules()
    print(f"\n🔑 Current SG ({AWS_SG_ID}) CIDRs: {len(current_cidrs)}")
    for cidr in current_cidrs:
        print(f"  {cidr}")

    if new_cidrs == current_cidrs:
        print("\n✅ No changes detected in SG rules.")
        return

    # Check SG rule limit
    if len(new_cidrs) > AWS_SG_RULE_LIMIT:
        alert_msg = (
            f"🚨 ALERT: NOT able to update Security group !!\n"
            f"Pingdom IP CIDRs = {len(new_cidrs)}, exceeds AWS SG limit of {AWS_SG_RULE_LIMIT}.\n"
            f"*SG:* `{AWS_SG_ID}`\n"
            f"*Jenkins URL:* `{JENKINS_URL}`\n"
            f"*Jenkins Job:* `{JOB_NAME}`\n"
            f"*Pingdom Region:* `{PINGDOM_REGION}`"
        )
        print("\n🚨 ALERT: Too many Pingdom IPs for SG limit!")
        if not DRY_RUN:
            send_slack_alert(alert_msg)
        sys.exit(1)

    # Update SG with diffs
    replace_sg_ingress_rules(new_cidrs, current_cidrs)

    success_msg = (
        f"✅ Updated SG with {len(new_cidrs)} Pingdom {PINGDOM_REGION} IPv4 probe IPs.\n"
        f"*SG:* `{AWS_SG_ID}`\n"
        f"*Jenkins URL:* `{JENKINS_URL}`\n"
        f"*Jenkins Job:* `{JOB_NAME}`\n"
        f"*Pingdom Region:* `{PINGDOM_REGION}`"
    )
    print(f"\n✅ Updated Security Group with {len(new_cidrs)} Pingdom {PINGDOM_REGION} IPv4 probe IPs.")
    send_slack_alert(success_msg)


if __name__ == "__main__":
    main()
