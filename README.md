# Pingdom Probe IP Whitelisting Automation for AWS Security Group🛡️

This Python script automates the process of fetching Pingdom's probe IPv4 addresses for a selected region and synchronizing those IPs with a specific **AWS Security Group** ingress rules on port 443 (HTTPS).

It is designed to run periodically (e.g. via a Jenkins job, cron job, or AWS Lambda) to ensure that only the active, region-specific Pingdom monitoring probes are allowed to access your AWS infrastructure. This enhances security by following the principle of least privilege.

***

## 🚀 Key Features

* **Dynamic Fetching:** Retrieves active IPv4 probes from the Pingdom API based on a configurable region (NA, EU, APAC, or LATAM).
* **CIDR Formatting:** Converts each probe IP address into a standard /32 CIDR block for use in AWS Security Groups.
* **Incremental Updates:** Only adds new rules and removes stale rules (**diff-based update**), preserving any existing, unchanged rules.
* **Security Group Rule Limit Check:** Prevents rule addition if the collapsed CIDRs exceed the AWS rule limit (default 60 for AWS VPCs).
* **Dry-Run Mode:** Supports a safe **Dry-Run** option for testing the changes without affecting the AWS Security Group.
* **Slack Notifications:** Sends success or failure alerts to a Slack channel.

***

## ⚙️ Prerequisites

-  **Python 3.x** and the required packages (`requests`, `boto3`).
-  **AWS Credentials:** The execution environment must have valid AWS credentials configured with `ec2:DescribeSecurityGroups`, `ec2:AuthorizeSecurityGroupIngress`, and `ec2:RevokeSecurityGroupIngress` permissions.
-  **Pingdom API Token:** A Pingdom API Token is required to access the probe IP feed.
-  **Slack Bot Token:** A Slack Bot Token with permissions to post messages to the target channel.

***

## 📝 Environment Variables

The script relies on several environment variables for configuration:

| Variable | Description | Required | Example |
| :--- | :--- | :--- | :--- |
| `AWS_SG_ID` | The ID of the AWS Security Group to update. | Yes | `sg-0a1b2c3d4e5f6g7h8` |
| `AWS_REGION` | The AWS region where the Security Group resides. | Yes | `us-east-1` |
| `PINGDOM_API_TOKEN` | The Token for authenticating with the Pingdom API. | Yes | `abc-12345...` |
| `PINGDOM_REGION` | The Pingdom region to whitelist probes for. | No | `NA, EU, APAC or LATAM (Default: NA)` |
| `SLACK_BOT_TOKEN` | Slack Bot Token for sending notifications. | Yes | `xoxb-12345...` |
| `DRY_RUN` | If set to `true`, the script performs all checks but *skips* the final AWS update. | No | `true` or `false` |
| `JENKINS_URL` | Contextual URL for the Jenkins job (for Slack alerts). | No | `https://jenkins.mycompany.com` |
| `JOB_NAME` | Contextual name of the Jenkins job (for Slack alerts). | No | `pingdom-ip-sync` |

***

## 📦 Installation and Usage

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment
Set the necessary environment variables (e.g., in your shell or CI/CD system).
```bash
export AWS_SG_ID="sg-xxxxxxxxxx"
export AWS_REGION="us-west-2"
export PINGDOM_API_TOKEN="abc-12345..."
export PINGDOM_REGION="EU" # Whitelist probes from the EU region
export SLACK_BOT_TOKEN="xoxb-..."
# export DRY_RUN="true" # Optional, for testing changes
```

### 3. Run the Script
Execute the Python script:
```bash
python pingdom-aws-sg-whitelister.py
```

### Example Output
```bash
🔍 Fetching Pingdom probes from https://api.pingdom.com/api/3.1/probes ...

✅ Total EU IPv4 probes: 15
  46.101.12.34/32
  51.15.67.89/32
  ...

🔑 Current SG (sg-xxxxxxxxx) CIDRs: 12
  46.101.12.34/32
  198.51.100.0/32
  ...

⚡ Checking Security Group for differences...

🗑  Removing below 1 stale rules...
  198.51.100.0/32

➕ Adding below 4 new rules...
  1.2.3.4/32
  5.6.7.8/32
  9.10.11.12/32
  13.14.15.16/32

✅ Updated Security Group with 15 Pingdom EU IPv4 probe IPs.

📤 Slack alert sent to #alerts
```

## ⚠️ Notes
* **Target Port:** The script manages Ingress rules for TCP Port 443 (HTTPS). To change the port, modify the constant AWS_SG_RULE_PORT in the script.
* **Rule Descriptions:** All rules added by this script are tagged with the description: "Pingdom probe rule added via automation".
* **AWS Limit:** The script uses a hard limit of 60 rules (AWS_SG_RULE_LIMIT) to prevent hitting the default AWS VPC Security Group rule limit.

## ⚖️ License
This project is licensed under the [MIT License](LICENSE) - see the file for details.
