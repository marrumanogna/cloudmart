# cloudmart

\# CloudMart — AWS Cloud Infrastructure \& Serverless Application



\## 1. Project Overview



\*\*CloudMart\*\* is a cloud-native e-commerce backend application built on AWS using a serverless and managed-services architecture.



The project is designed around secure API access, private database connectivity, infrastructure-as-code, automated CI/CD deployment, event-driven communication, and centralized monitoring.



The infrastructure is deployed using \*\*AWS CloudFormation\*\* and \*\*GitHub Actions\*\*. The application uses \*\*Amazon API Gateway\*\* as the API entry point, a \*\*Lambda Authorizer\*\* for token-based authentication, \*\*AWS Lambda\*\* for application services, and \*\*Amazon RDS MySQL\*\* for persistent relational data.



\### Core Architecture



```text

&#x20;                        GitHub Repository

&#x20;                               |

&#x20;                               v

&#x20;                      GitHub Actions CI/CD

&#x20;                               |

&#x20;                               v

&#x20;                     AWS CloudFormation

&#x20;                               |

&#x20;            +------------------+------------------+

&#x20;            |                  |                  |

&#x20;            v                  v                  v

&#x20;      Network Stack        Data Stack         Auth Stack

&#x20;            |                  |                  |

&#x20;            |                  |                  |

&#x20;            |              RDS MySQL              |

&#x20;            |              S3 Buckets             |

&#x20;            |                  |                  |

&#x20;            +------------------+------------------+

&#x20;                               |

&#x20;                               v

&#x20;                          API Stack

&#x20;                               |

&#x20;                        Amazon API Gateway

&#x20;                               |

&#x20;                      Lambda Authorizer

&#x20;                               |

&#x20;                   SSM Parameter Store

&#x20;                               |

&#x20;                +--------------+--------------+

&#x20;                |                             |

&#x20;                v                             v

&#x20;         Product Lambda                Order Lambda

&#x20;                |                             |

&#x20;                |                             v

&#x20;                |                     Order Processor

&#x20;                |                          Lambda

&#x20;                |                             |

&#x20;                +-------------+---------------+

&#x20;                              |

&#x20;                              v

&#x20;                        RDS MySQL

&#x20;                              |

&#x20;                    EventBridge Event Bus

&#x20;                              |

&#x20;                        SNS Notifications

&#x20;                              |

&#x20;                      Low-Stock Email Alert



&#x20;                        Report Lambda

&#x20;                              |

&#x20;                              v

&#x20;                        Reports S3 Bucket

```



\---



\# 2. Project Goals



The main goals of CloudMart are:



\* Build a secure AWS cloud infrastructure.

\* Deploy infrastructure using Infrastructure as Code.

\* Automate deployments using GitHub Actions.

\* Keep the RDS database inside private subnets.

\* Implement token-based API authentication.

\* Use a Lambda Authorizer with API Gateway.

\* Store sensitive configuration in AWS SSM Parameter Store.

\* Build product and order services using AWS Lambda.

\* Use EventBridge for event-driven communication.

\* Use SNS for low-stock notifications.

\* Store generated reports in Amazon S3.

\* Apply IAM permissions based on service responsibilities.

\* Implement structured application logging.

\* Avoid unnecessary infrastructure such as NAT Gateway where possible.

\* Maintain separate CloudFormation stacks for different infrastructure responsibilities.



\---



\# 3. AWS Services Used



| AWS Service             | Purpose                                     |

| ----------------------- | ------------------------------------------- |

| Amazon VPC              | Provides isolated networking environment    |

| Amazon EC2 Subnets      | Public and private network segmentation     |

| Internet Gateway        | Internet connectivity for the public subnet |

| VPC Endpoints           | Private connectivity to AWS services        |

| Amazon RDS MySQL        | Primary relational database                 |

| Amazon S3               | Artifact and report storage                 |

| AWS Lambda              | Serverless application services             |

| Amazon API Gateway      | REST API entry point                        |

| Lambda Authorizer       | Token-based API authentication              |

| AWS SSM Parameter Store | Secure configuration and secret storage     |

| Amazon EventBridge      | Event-driven communication                  |

| Amazon SNS              | Notification and email alerts               |

| Amazon CloudWatch       | Logs and monitoring                         |

| AWS IAM                 | Roles and permissions                       |

| AWS CloudFormation      | Infrastructure as Code                      |

| GitHub Actions          | CI/CD automation                            |



\*\*DynamoDB is not used in the final CloudMart architecture.\*\* RDS MySQL is the single primary application database.



\---



\# 4. Repository Structure



```text

cloudmart/

│

├── .github/

│   └── workflows/

│       └── deploy.yaml

│

├── cloudformation/

│   ├── network-stack.yaml

│   ├── data-stack.yaml

│   ├── auth-stack.yaml

│   └── api-stack.yaml

│

├── database/

│   └── schema.sql

│

├── docs/

│   └── architecture documentation

│

├── lambda/

│   └── application Lambda source files

│

├── authorizer-code/

│   └── Lambda Authorizer source

│

├── product-lambda/

│   └── Product Lambda source

│

├── rds-test/

│   └── RDS connectivity test Lambda

│

├── auth-template.yaml

├── oidc-policy.json

├── trust-policy.json

├── README.md

└── deploy.yaml

```



Temporary deployment/test artifacts such as ZIP files and generated JSON responses should preferably not be committed to the repository unless they are intentionally required by the project.



\---



\# 5. CloudFormation Stack Architecture



CloudMart follows a layered CloudFormation deployment model.



```text

1\. Network Stack

&#x20;       ↓

2\. Data Stack

&#x20;       ↓

3\. Authentication Stack

&#x20;       ↓

4\. API / Application Stack

```



Each stack has a specific responsibility.



\---



\## 5.1 Network Stack



File:



```text

cloudformation/network-stack.yaml

```



Stack:



```text

cloudmart-network-dev

```



\### Resources



The Network Stack creates:



\* VPC

\* Internet Gateway

\* Public Subnet

\* Private Subnet

\* Second Private Subnet

\* Public Route Table

\* Private Route Table

\* Route Table Associations

\* Lambda Security Group

\* RDS Security Group

\* EC2 Dashboard Security Group

\* VPC Endpoint Security Group

\* SSM Interface VPC Endpoint

\* S3 Gateway VPC Endpoint



\### VPC CIDR



```text

10.0.0.0/16

```



\### Subnets



```text

Public Subnet

10.0.1.0/24



Private Subnet

10.0.2.0/24



Private Subnet 2

10.0.3.0/24

```



\### Network Design



The application database and Lambda functions operate in private subnets.



The RDS database is not publicly accessible.



The architecture uses VPC endpoints instead of relying on a NAT Gateway for the required AWS service connectivity.



\---



\# 6. Security Group Design



\## Lambda Security Group



The Lambda security group allows:



\* TCP 3306 to the RDS security group.

\* TCP 443 for required private AWS service communication.



Purpose:



```text

Lambda → RDS MySQL

Lambda → AWS services through VPC endpoints

```



\---



\## RDS Security Group



The RDS security group allows:



```text

TCP 3306

Source: Lambda Security Group

```



This means the database accepts MySQL connections from authorized Lambda functions rather than allowing unrestricted access.



\---



\## EC2 Dashboard Security Group



The dashboard security group allows:



```text

TCP 80

TCP 443

```



from the internet.



It also contains outbound rules for required communication.



\---



\## VPC Endpoint Security Group



The VPC Endpoint security group allows:



```text

TCP 443

```



from authorized Lambda and dashboard security groups.



\---



\# 7. Data Stack



File:



```text

cloudformation/data-stack.yaml

```



Stack:



```text

cloudmart-data-dev

```



The Data Stack creates the persistent data infrastructure.



\### Amazon RDS MySQL



Configuration includes:



```text

Engine: MySQL

Instance Class: db.t3.micro

Storage: 20 GB

Storage Type: gp3

Port: 3306

Publicly Accessible: false

Multi-AZ: false

```



RDS is deployed into private subnets using an RDS DB subnet group.



\### S3 Buckets



Two private S3 buckets are created:



```text

CloudMart Artifacts Bucket

CloudMart Reports Bucket

```



Both buckets use:



\* Server-side encryption

\* Public access blocking



\---



\# 8. RDS Database Schema



The CloudMart database is named:



```text

cloudmart

```



The relational schema contains five primary tables.



\## Customers



```text

customers

```



Stores customer information.



Important columns:



```text

customer\_id

name

email

created\_at

```



The email field is unique.



\---



\## Products



```text

products

```



Stores product information and inventory.



Important columns:



```text

product\_id

name

description

price

category

stock\_count

created\_at

updated\_at

soft\_delete

```



Indexes are created for:



```text

name

category

```



\---



\## Orders



```text

orders

```



Stores customer orders.



Important columns:



```text

order\_id

customer\_id

status

total\_amount

created\_at

updated\_at

```



Supported order states:



```text

PLACED

CONFIRMED

FAILED

CANCELLED

```



The table contains a foreign key to the customers table.



Indexes support:



\* Customer-based queries

\* Status-based queries

\* Date-based queries

\* Customer + date queries



\---



\## Order Items



```text

order\_items

```



Stores products belonging to an order.



Important columns:



```text

order\_item\_id

order\_id

product\_id

quantity

unit\_price

```



Foreign keys connect order items to:



```text

orders

products

```



\---



\## History



```text

history

```



Stores order status changes.



Important columns:



```text

history\_id

order\_id

old\_status

new\_status

changed\_at

changed\_by

```



This provides an audit trail for order status transitions.



\---



\# 9. Authentication Architecture



CloudMart uses a custom \*\*API Gateway Lambda Authorizer\*\*.



Authentication flow:



```text

Client

&#x20; |

&#x20; | Authorization: token

&#x20; v

API Gateway

&#x20; |

&#x20; v

Lambda Authorizer

&#x20; |

&#x20; v

SSM Parameter Store

&#x20; |

&#x20; | Compare token

&#x20; v

Allow / Deny

&#x20; |

&#x20; v

Application Lambda

```



The API token is stored as an SSM `SecureString`.



Parameter:



```text

/cloudmart/dev/auth/api-token

```



The Authorizer Lambda retrieves the token from SSM using:



```text

ssm:GetParameter

```



with decryption enabled.



\---



\# 10. Authentication Behaviour



The API should behave as follows:



\### No token



```text

401 Unauthorized

```



\### Incorrect token



```text

401 Unauthorized

```



\### Correct token



```text

200 / successful API response

```



The Authorizer supports both direct token values and:



```text

Bearer <token>

```



format.



\---



\# 11. Authorizer Security



The Lambda Authorizer does not hardcode the authentication token.



Instead:



```text

GitHub Actions Secret

&#x20;       ↓

SSM SecureString

&#x20;       ↓

Lambda Authorizer

```



The token is therefore separated from application source code.



The Authorizer also uses an environment variable:



```text

AUTH\_TOKEN\_PARAMETER

```



to determine the SSM parameter name.



\---



\# 12. API Gateway



The API is implemented using Amazon API Gateway.



API stage:



```text

dev

```



Example API structure:



```text

/products

/products/{id}

/orders

```



\---



\## Product Endpoints



```text

GET    /products

POST   /products



GET    /products/{id}

PUT    /products/{id}

DELETE /products/{id}

```



All product endpoints are configured with the Lambda Authorizer.



\---



\## Order Endpoint



```text

POST /orders

```



The order endpoint also uses the Lambda Authorizer.



\---



\# 13. Lambda Services



CloudMart contains separate Lambda functions for different responsibilities.



\## Product Lambda



```text

cloudmart-product-dev

```



Responsibilities:



\* Product operations

\* Product/inventory processing

\* RDS connectivity

\* Event publishing

\* Low-stock notification flow



\---



\## Order Lambda



```text

cloudmart-order-dev

```



Responsibilities:



\* Accept order requests

\* Start order processing

\* Invoke the order processor

\* Publish order-related events



\---



\## Order Processor Lambda



```text

cloudmart-order-processor-dev

```



Responsibilities:



\* Process order operations

\* Interact with RDS

\* Handle order processing logic



\---



\## Report Lambda



```text

cloudmart-report-dev

```



Responsibilities:



\* Generate reports

\* Retrieve required database information

\* Store reports in the Reports S3 bucket



\---



\## Authorizer Lambda



```text

cloudmart-authorizer-dev

```



Responsibilities:



\* Validate API tokens

\* Read authentication token from SSM

\* Return Allow/Deny IAM policies to API Gateway



\---



\# 14. Event-Driven Architecture



CloudMart uses Amazon EventBridge for asynchronous event communication.



```text

Application Lambda

&#x20;      |

&#x20;      v

EventBridge Event Bus

&#x20;      |

&#x20;      +------------------+

&#x20;      |                  |

&#x20;      v                  v

&#x20;Event Processing     Notifications

```



The custom EventBridge bus is:



```text

cloudmart-dev-event-bus

```



Application functions can publish events using:



```text

events:PutEvents

```



\---



\# 15. SNS Low-Stock Notification



CloudMart uses Amazon SNS for low-stock alerts.



Topic:



```text

cloudmart-low-stock-dev

```



The intended flow is:



```text

Product / Inventory Update

&#x20;         |

&#x20;         v

&#x20;    Stock Check

&#x20;         |

&#x20;    stock below

&#x20;     threshold?

&#x20;         |

&#x20;        Yes

&#x20;         |

&#x20;         v

&#x20;   SNS Low Stock Topic

&#x20;         |

&#x20;         v

&#x20;      Email Alert

```



The email subscription is configurable using the CloudFormation parameter:



```text

LowStockEmail

```



The subscription is created only when an email address is provided.



\---



\# 16. S3 Reporting



CloudMart uses Amazon S3 to store generated reports.



Reports are stored in the dedicated Reports bucket.



The Report Lambda has permission to:



```text

s3:PutObject

s3:GetObject

```



for report objects.



The Reports bucket blocks public access and uses server-side encryption.



\---



\# 17. SSM Parameter Store



SSM Parameter Store is used for configuration and sensitive values.



Parameters include:



```text

/cloudmart/dev/rds/host

/cloudmart/dev/rds/port

/cloudmart/dev/rds/db-name

/cloudmart/dev/rds/username

/cloudmart/dev/rds/password

/cloudmart/dev/auth/api-token

```



Sensitive values use:



```text

SecureString

```



while non-sensitive connection information can use:



```text

String

```



\---



\# 18. IAM Design



Each Lambda function has a dedicated IAM role.



Examples:



```text

cloudmart-authorizer-role-dev

cloudmart-product-lambda-role-dev

cloudmart-order-lambda-role-dev

cloudmart-order-processor-role-dev

cloudmart-report-lambda-role-dev

```



Permissions are separated according to function responsibility.



Examples:



\### Product Lambda



Can access:



```text

SSM

RDS connectivity

EventBridge

SNS

CloudWatch

VPC networking

```



\### Order Lambda



Can access:



```text

SSM

Order Processor Lambda

EventBridge

CloudWatch

VPC networking

```



\### Report Lambda



Can access:



```text

SSM

S3 Reports Bucket

CloudWatch

VPC networking

```



\### Authorizer Lambda



Can access:



```text

SSM authentication parameter

CloudWatch Logs

```



\---



\# 19. CI/CD Pipeline



CloudMart uses GitHub Actions for automated infrastructure deployment.



Workflow:



```text

GitHub Push

&#x20;   |

&#x20;   v

GitHub Actions

&#x20;   |

&#x20;   v

Configure AWS Credentials

&#x20;   |

&#x20;   v

Deploy Network

&#x20;   |

&#x20;   v

Deploy Data

&#x20;   |

&#x20;   v

Deploy Auth

&#x20;   |

&#x20;   v

Deploy API

```



Deployment order is controlled using GitHub Actions job dependencies.



```text

deploy-network

&#x20;     ↓

deploy-data

&#x20;     ↓

deploy-auth

&#x20;     ↓

deploy-api

```



This prevents dependent stacks from being deployed before their required infrastructure exists.



\---



\# 20. GitHub Actions Authentication



GitHub Actions uses AWS IAM OIDC authentication.



The workflow uses:



```yaml

permissions:

&#x20; id-token: write

&#x20; contents: read

```



AWS credentials are obtained through:



```text

aws-actions/configure-aws-credentials

```



The workflow assumes the configured AWS IAM role using:



```text

sts:AssumeRoleWithWebIdentity

```



No long-lived AWS access key is required inside GitHub Actions.



\---



\# 21. GitHub Actions Secrets



The deployment workflow uses GitHub Secrets for sensitive values.



Expected secrets include:



```text

AWS\_ROLE\_ARN

DB\_USERNAME

DB\_PASSWORD

CLOUDMART\_AUTH\_TOKEN

```



The values are passed to AWS only during deployment.



The database credentials and authentication token are subsequently stored in SSM Parameter Store.



\---



\# 22. Deployment Workflow



The deployment workflow is triggered when changes are pushed to:



```text

main

```



and relevant files change.



It can also be manually triggered using:



```text

workflow\_dispatch

```



The workflow uses:



```text

AWS Region: ap-south-1

Environment: dev

```



\---



\# 23. Infrastructure Deployment



The deployment process validates CloudFormation templates before deployment.



For example:



```text

aws cloudformation validate-template

```



is executed before each stack deployment.



The stacks are then deployed using:



```text

aws cloudformation deploy

```



The deployment pipeline also retrieves CloudFormation outputs such as:



```text

RDS endpoint

RDS port

database name

API Gateway outputs

```



and uses them for subsequent configuration.



\---



\# 24. RDS Connectivity



A dedicated RDS connectivity test Lambda is used to verify communication between Lambda and RDS.



The expected architecture is:



```text

Lambda

&#x20; |

&#x20; | TCP 3306

&#x20; v

RDS Security Group

&#x20; |

&#x20; v

RDS MySQL

```



The RDS instance is located in private subnets and is not publicly accessible.



\---



\# 25. Logging and Monitoring



CloudMart Lambda functions use Amazon CloudWatch Logs.



The application logs structured JSON information such as:



```json

{

&#x20; "message": "Product Lambda invoked",

&#x20; "environment": "dev",

&#x20; "request\_id": "..."

}

```



This provides useful information for:



\* Request tracing

\* Debugging

\* Application monitoring

\* Operational troubleshooting



Lambda IAM roles include permissions required to write CloudWatch logs.



\---



\# 26. Security Design



CloudMart follows several security principles.



\### Private Database



RDS is configured with:



```text

PubliclyAccessible: false

```



\### Security Group Based Database Access



RDS accepts MySQL traffic from the Lambda security group.



\### Secure Secrets



Passwords and API authentication tokens are stored using SSM SecureString.



\### No Hardcoded Authentication Token



The Authorizer retrieves the token dynamically from SSM.



\### IAM Role Separation



Each Lambda has its own IAM role.



\### GitHub OIDC



GitHub Actions uses temporary AWS credentials through OIDC instead of storing permanent AWS access keys.



\### S3 Public Access Blocking



S3 buckets have public access blocked.



\### Encryption



S3 buckets use server-side encryption.



\---



\# 27. Milestone 1 — Repository and Design Kickoff



\*\*Target Date:\*\* 12 August 2026



\### Deliverables



\* GitHub repository initialized.

\* Repository folder structure created.

\* README created.

\* High-level architecture designed.

\* CloudFormation stack plan created.

\* Initial architecture reviewed.



\### Status



\*\*Completed\*\*



\---



\# 28. Milestone 2 — Architecture, Design, and CI/CD Bootstrap



\*\*Target Date:\*\* 19 August 2026



\### Required Deliverables



\* Final architecture diagram

\* Detailed RDS schema

\* Authentication design

\* GitHub Actions workflow

\* Network CloudFormation stack

\* Data CloudFormation stack

\* IAM roles

\* SSM parameters

\* RDS connectivity test

\* CI/CD deployment verification



\### Current Architecture



The final design uses:



```text

RDS MySQL

```



instead of DynamoDB.



\### Expected Deployment Order



```text

Network

&#x20;  ↓

Data

&#x20;  ↓

Auth

&#x20;  ↓

API

```



\### Verification



The infrastructure should be verified from GitHub Actions execution logs and AWS resources.



Important checks include:



\* Network stack deployed successfully.

\* Data stack deployed successfully.

\* RDS created successfully.

\* RDS is private.

\* S3 buckets created.

\* SSM parameters created.

\* IAM roles created.

\* RDS connectivity test successful.

\* Authentication stack deployed.

\* API stack deployed.



\---



\# 29. Milestone 3 — Authentication Layer and Product Service



\*\*Target Date:\*\* 26 August 2026



\### Required Deliverables



\* Authentication stack deployed.

\* Lambda Authorizer deployed.

\* Secure authentication token stored in SSM.

\* Authorizer attached to API Gateway.

\* Authorizer cache TTL configured.

\* API Gateway deployed.

\* Product Lambda deployed.

\* RDS schema applied.

\* Product CRUD endpoints implemented.

\* EventBridge integration implemented.

\* SNS low-stock notification implemented.

\* Structured CloudWatch logging implemented.

\* All changes deployed through GitHub Actions.



\### Authentication Verification



Three cases must be demonstrated:



```text

No Token

&#x20;  ↓

401 Unauthorized

```



```text

Wrong Token

&#x20;  ↓

401 Unauthorized

```



```text

Correct Token

&#x20;  ↓

200 / Successful Response

```



\### Product Verification



The complete product flow should demonstrate:



```text

POST /products

&#x20;      ↓

Product Created

&#x20;      ↓

GET /products

&#x20;      ↓

Product Retrieved

&#x20;      ↓

PUT /products/{id}

&#x20;      ↓

Stock Updated

&#x20;      ↓

Low Stock Condition

&#x20;      ↓

SNS

&#x20;      ↓

Email Notification

```



\---



\# 30. Current Implementation Status



\### Infrastructure



| Component                            | Status     |

| ------------------------------------ | ---------- |

| GitHub Repository                    | Completed  |

| Repository Structure                 | Completed  |

| README                               | Completed  |

| Network Stack                        | Deployed   |

| VPC                                  | Deployed   |

| Public Subnet                        | Deployed   |

| Private Subnets                      | Deployed   |

| Internet Gateway                     | Deployed   |

| Route Tables                         | Deployed   |

| Security Groups                      | Deployed   |

| VPC Endpoints                        | Deployed   |

| RDS MySQL                            | Deployed   |

| S3 Buckets                           | Deployed   |

| SSM Parameters                       | Configured |

| IAM Lambda Roles                     | Deployed   |

| GitHub Actions OIDC                  | Configured |

| Network → Data → Auth → API Pipeline | Configured |



\### Authentication



| Requirement            | Status      |

| ---------------------- | ----------- |

| Lambda Authorizer      | Deployed    |

| SSM SecureString Token | Configured  |

| API Gateway Authorizer | Configured  |

| Authorizer Cache TTL   | 300 seconds |

| No Token Test          | Verified    |

| Wrong Token Test       | Verified    |

| Correct Token Test     | Verified    |



\### API



| Requirement             | Status   |

| ----------------------- | -------- |

| API Gateway             | Deployed |

| `/products` GET         | Deployed |

| `/products` POST        | Deployed |

| `/products/{id}` GET    | Deployed |

| `/products/{id}` PUT    | Deployed |

| `/products/{id}` DELETE | Deployed |

| `/orders` POST          | Deployed |

| Product Lambda          | Deployed |

| Order Lambda            | Deployed |

| Order Processor Lambda  | Deployed |

| Report Lambda           | Deployed |



> \*\*Note:\*\* API Gateway routes and Lambda infrastructure are deployed. Full business CRUD logic, inventory processing, EventBridge rules, SNS low-stock behaviour, and report scheduling must be verified separately against the final application code.



\---



\# 31. Deployment Region



CloudMart is currently configured for:



```text

AWS Region:

ap-south-1

```



Environment:



```text

dev

```



\---



\# 32. Environment Parameterization



CloudFormation templates support:



```text

dev

prod

```



through the:



```text

Environment

```



parameter.



Resource names follow the environment convention.



Examples:



```text

cloudmart-vpc-dev

cloudmart-mysql-dev

cloudmart-authorizer-dev

cloudmart-product-dev

cloudmart-api-dev

```



This allows the infrastructure to be deployed separately for different environments.



\---



\# 33. Key Design Decisions



\## RDS instead of DynamoDB



CloudMart uses \*\*Amazon RDS MySQL\*\* as the primary database because the application has relational entities and relationships between:



```text

Customers

Products

Orders

Order Items

History

```



Foreign keys and relational queries are therefore handled using MySQL.



\---



\## No NAT Gateway



The architecture avoids a NAT Gateway to reduce unnecessary infrastructure cost.



Private workloads use VPC endpoints for required AWS service connectivity.



\---



\## Lambda Authorizer instead of Cognito



CloudMart uses a custom Lambda Authorizer because the authentication requirement is based on validating an API token stored in SSM Parameter Store.



The API Gateway itself does not generate the token.



\---



\## EventBridge for Events



EventBridge is used to decouple application events from notification and processing components.



\---



\## SNS for Notifications



SNS is used for low-stock email notifications.



\---



\# 34. Important Project Commands



\### Check Git status



```powershell

git status

```



\### Check remote repository



```powershell

git remote -v

```



\### Push changes



```powershell

git add .

git commit -m "Update CloudMart infrastructure"

git push origin main

```



\### Check CloudFormation stacks



```powershell

aws cloudformation list-stacks --region ap-south-1

```



\### Check a specific stack



```powershell

aws cloudformation describe-stacks --stack-name cloudmart-api-dev --region ap-south-1

```



\### Check stack events



```powershell

aws cloudformation describe-stack-events --stack-name cloudmart-api-dev --region ap-south-1

```



\---



\# 35. Project Outcome



CloudMart demonstrates an AWS-based cloud application architecture using:



```text

Infrastructure as Code

&#x20;       +

CI/CD

&#x20;       +

Private Networking

&#x20;       +

Serverless Computing

&#x20;       +

Relational Database

&#x20;       +

API Authentication

&#x20;       +

Event-Driven Architecture

&#x20;       +

Notifications

&#x20;       +

Monitoring

```



The project provides a foundation for a secure and scalable e-commerce backend while keeping infrastructure deployment automated and reproducible.



\---



\# 36. Final Architecture Summary



```text

&#x20;                   GitHub

&#x20;                     |

&#x20;                     v

&#x20;              GitHub Actions

&#x20;                     |

&#x20;                     v

&#x20;             CloudFormation

&#x20;                     |

&#x20;      +--------------+--------------+

&#x20;      |              |              |

&#x20;      v              v              v

&#x20;   Network          Data           Auth

&#x20;      |              |              |

&#x20;      |            RDS           Authorizer

&#x20;      |             S3               |

&#x20;      |              |              |

&#x20;      +--------------+--------------+

&#x20;                     |

&#x20;                     v

&#x20;                API Gateway

&#x20;                     |

&#x20;               Lambda Authorizer

&#x20;                     |

&#x20;         +-----------+-----------+

&#x20;         |                       |

&#x20;         v                       v

&#x20;   Product Lambda          Order Lambda

&#x20;         |                       |

&#x20;         |                       v

&#x20;         |                Order Processor

&#x20;         |                       |

&#x20;         +-----------+-----------+

&#x20;                     |

&#x20;                     v

&#x20;                 RDS MySQL

&#x20;                     |

&#x20;                     v

&#x20;               EventBridge

&#x20;                     |

&#x20;                     v

&#x20;                    SNS

&#x20;                     |

&#x20;                     v

&#x20;               Email Alerts





&#x20;               Report Lambda

&#x20;                     |

&#x20;                     v

&#x20;                S3 Reports

```



\## Technology Stack



```text

Cloud Platform       : AWS

Infrastructure       : AWS CloudFormation

CI/CD                : GitHub Actions

Authentication       : API Gateway Lambda Authorizer

Database             : Amazon RDS MySQL

Compute              : AWS Lambda

API                  : Amazon API Gateway

Events               : Amazon EventBridge

Notifications        : Amazon SNS

Storage              : Amazon S3

Secrets/Config       : AWS SSM Parameter Store

Networking           : Amazon VPC

Monitoring           : Amazon CloudWatch

Identity             : AWS IAM + GitHub OIDC

Language             : Python 3.11

```



\## Project Status



\*\*CloudMart infrastructure is deployed using Infrastructure as Code and automated CI/CD.\*\*



The remaining work is to verify and complete the application-level business flows required by Milestone 3, particularly the full Product CRUD implementation, inventory/event processing, low-stock SNS notification, and complete end-to-end demonstration.



