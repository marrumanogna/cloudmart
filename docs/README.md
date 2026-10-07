# CloudMart

CloudMart is an AWS-based cloud e-commerce backend and operations
platform. It provides customer, product, and order APIs, asynchronous
order processing, inventory/low-stock notifications, daily reporting, an
EC2-hosted Flask dashboard, and CloudWatch monitoring.

The infrastructure is defined with AWS CloudFormation and deployed
through GitHub Actions using GitHub OIDC and temporary AWS credentials.

Main request flow

1. A client sends an HTTP request to API Gateway.
2. Protected API methods invoke the Lambda Authorizer.
3. The Authorizer validates the supplied token.
4. A valid request is allowed to reach the application Lambda.
5. The Lambda communicates with RDS MySQL and/or AWS event services.
6. Business events are published to EventBridge.
7. EventBridge rules route events to SNS topics.
8. Failed order processing is sent to SQS.
9. CloudWatch records logs and custom operational metrics.
10. The reporting workflow creates daily CSV reports in S3.
11. The Flask dashboard running on EC2 displays operational data.

\---

## 2\. AWS Services Used

\---

Service                             Purpose

\---

Amazon VPC                          Network isolation for CloudMart

EC2                                 Hosts the Flask operations
dashboard

RDS MySQL                           Stores customers, products, orders,
order items, and history

Lambda                              Runs backend business logic and
automation

API Gateway                         Exposes REST APIs

Lambda Authorizer                   Token-based API authorization

S3                                  Stores deployment artifacts and
generated reports

EventBridge                         Event bus, routing rules, and daily
schedule

SNS                                 Email notifications

SQS                                 Failed-order queue

SSM Parameter Store                 Stores/retrieves selected
configuration values

CloudWatch                          Logs, metrics, alarms, and
operations dashboard

IAM                                 Service and deployment permissions

STS + GitHub OIDC                   Temporary AWS credentials for CI/CD

CloudFormation                      Infrastructure as Code

## GitHub Actions                      Automated deployment pipeline

\---

## 3\. VPC and Network Design

CloudMart uses a VPC with CIDR:

``` text
10.0.0.0/16
```

### Subnets

Subnet             CIDR            Purpose

\---

Public Subnet      `10.0.1.0/24`   EC2 Flask Dashboard
Private Subnet 1   `10.0.2.0/24`   Lambda ENIs and RDS
Private Subnet 2   `10.0.3.0/24`   Lambda ENIs / secondary AZ

RDS is not publicly accessible.

Lambda functions are attached to the private subnets and use the Lambda
security group. RDS allows MySQL traffic on port `3306` from the Lambda
security group.

The network stack also creates VPC endpoints for AWS services used by
the private workloads, including SSM, S3, EventBridge, SNS, SQS, Lambda,
and CloudWatch monitoring.

\---

## 4\. CloudFormation Stack Structure

CloudMart is divided into independent CloudFormation stacks.

### 4.1 Network Stack

File:

``` text
cloudformation/network-stack.yaml
```

Creates:

* VPC
* Internet Gateway
* Public and private subnets
* Route tables
* Security groups
* VPC endpoints
* Artifacts S3 bucket

Exports networking values for the dependent stacks.

### 4.2 Data Stack

File:

``` text
cloudformation/data-stack.yaml
```

Creates:

* RDS MySQL
* RDS subnet group
* Reports S3 bucket
* Database initialization Lambda
* RDS-related SSM parameters

The database parameters include:

``` text
/cloudmart/<environment>/rds/host
/cloudmart/<environment>/rds/port
/cloudmart/<environment>/rds/db-name
```

### 4.3 Auth Stack

File:

``` text
cloudformation/auth-stack.yaml
```

Creates the Lambda Authorizer and its IAM configuration.

The Authorizer:

* Accepts the API token.
* Supports the admin token.
* Hashes customer tokens using SHA-256 before database lookup.
* Returns an API Gateway policy.
* Adds the authenticated customer ID to the authorizer context for
customer requests.

### 4.4 API/Application Stack

File:

``` text
cloudformation/api-stack.yaml
```

Creates:

* Customer Lambda
* Product Lambda
* Order Lambda
* Order Processor Lambda
* Report Lambda
* API Gateway REST API
* EventBridge event bus and rules
* SNS topics/subscriptions
* Failed-order SQS queue
* Lambda IAM roles and API permissions
* API throttling configuration

### 4.5 Reporting and Dashboard Stack

File:

``` text
cloudformation/reporting-stack.yaml
```

Creates the daily reporting schedule and the EC2 Flask dashboard
environment.

The daily report Lambda queries order data, generates a CSV report, and
stores it in the reports S3 bucket.

The EC2 instance runs the Flask dashboard and retrieves dashboard data
from RDS.

### 4.6 Monitoring Stack

File:

``` text
cloudformation/monitoring-stack.yaml
```

Creates:

* CloudWatch alarms
* CloudWatch operations dashboard
* Monitoring SNS topic
* Email subscription

Important operational metrics include:

``` text
OrdersPlaced
OrdersFailed
LowStockEvents
```

It also monitors API latency and EC2 dashboard health.

\---

## 5\. Backend Lambda Responsibilities

### Customer Lambda

Responsible for:

* Creating customers.
* Generating a customer token.
* Hashing the token before storing it in the database.
* Returning the original token to the customer only during creation.

### Product Lambda

Responsible for product operations:

``` text
GET    /products
GET    /products/{id}
POST   /products
PUT    /products/{id}
DELETE /products/{id}
```

Product deletion is implemented as a soft delete using the `soft\\\_delete`
column.

When inventory becomes low, the Product Lambda publishes an
`Inventory Change` event to EventBridge.

### Order Lambda

Responsible for:

``` text
POST  /orders
GET   /orders
GET   /orders/{order\\\_id}
PATCH /orders/{order\\\_id}
```

The Order Lambda performs request validation and handles customer-facing
order operations.

For order creation it invokes the Order Processor Lambda.

For cancellation it validates the order state and records the status
change.

### Order Processor Lambda

Responsible for actual order processing.

It:

1. Validates the customer.
2. Validates products and quantities.
3. Locks product rows using `SELECT ... FOR UPDATE`.
4. Checks available inventory.
5. Calculates the order total.
6. Creates the order and order items.
7. Deducts inventory.
8. Updates the order to `CONFIRMED`.
9. Writes order history.
10. Publishes order events.
11. Sends failed orders to the SQS failed-order queue when processing
fails.
12. Publishes CloudWatch custom metrics.

### Report Lambda

Runs from the daily EventBridge schedule.

It:

1. Connects to RDS.
2. Retrieves the day's order statistics.
3. Creates a CSV report in memory.
4. Uploads the CSV to the reports S3 bucket.

\---

## 6\. Authentication and Authorization

CloudMart uses an API Gateway Lambda Authorizer.

### Customer authentication

The customer token returned by:

``` text
POST /customers
```

is saved by the client.

The database stores the SHA-256 hash of the token rather than the
original token.

During authentication:

``` text
Client token
     ↓
SHA-256 hash
     ↓
Database lookup
     ↓
Customer ID
     ↓
Allow / Deny policy
```

For a customer request, the Authorizer passes the authenticated
`customer\\\_id` through API Gateway authorizer context.

This is used by the order logic to restrict customer order access to the
authenticated customer.

### Admin authentication

Admin operations use the configured `ADMIN\\\_TOKEN`.

The admin token is supplied through deployment configuration/secrets and
is not committed to the repository.

\---

## 7\. API Endpoints

Base URL:

``` text
{{base\\\_url}}
```

### Customers

Method   Endpoint       Purpose

\---

POST     `/customers`   Create a customer

Example:

``` json
{
  "name": "Test User",
  "email": "test.user@example.com"
}
```

The response provides the `customer\\\_id` and customer token.

### Products

Method   Endpoint           Purpose

\---

GET      `/products`        List products
GET      `/products/{id}`   Get one product
POST     `/products`        Create product
PUT      `/products/{id}`   Update product
DELETE   `/products/{id}`   Soft-delete product

Example product:

``` json
{
  "name": "Test Item",
  "description": "demo",
  "price": 999.00,
  "category": "Test",
  "stock\\\_count": 10
}
```

### Orders

Method   Endpoint               Purpose

\---

POST     `/orders`              Create an order
GET      `/orders`              Get customer orders
GET      `/orders/{order\\\_id}`   Get one order
PATCH    `/orders/{order\\\_id}`   Cancel an order

Example:

``` json
{
  "customer\\\_id": 1,
  "items": \\\[
    {
      "product\\\_id": 1,
      "quantity": 2
    }
  ]
}
```

Cancellation:

``` json
{
  "status": "CANCELLED"
}
```

### Current API authorization configuration

The CloudFormation template currently configures:

* `POST /customers` → no custom authorizer
* `GET /products` → no custom authorizer
* `GET /products/{id}` → no custom authorizer
* Product `POST`, `PUT`, `DELETE` → custom authorizer
* All order operations → custom authorizer

This reflects the current `api-stack.yaml`. If the intended design is to
protect product GET operations as well, their `AuthorizationType` should
be changed to `CUSTOM`.

\---

## 8\. Event-Driven Architecture

CloudMart uses a custom EventBridge event bus.

``` text
Product Lambda
     |
     | Inventory Change
     v
EventBridge
     |
     v
Inventory Change Rule
     |
     v
SNS Low Stock Topic
     |
     v
Email
```

### Order events

``` text
Order Lambda / Order Processor
             |
             v
       EventBridge
       /    |     \\\\
      /     |      \\\\
OrderPlaced Confirmed Failed
   |          |       |
   v          v       v
 SNS         SNS     SNS
   |          |       |
 Email       Email   Email
```

### Failed order processing

``` text
Order Processor
      |
      | processing failure
      v
     SQS
      |
      v
Failed Orders Queue
```

\---

## 9\. Inventory and Low-Stock Flow

When a product is created or updated and its stock reaches the
configured low-stock condition:

``` text
Product Lambda
      ↓
EventBridge
      ↓
InventoryChangeRule
      ↓
LowStock SNS Topic
      ↓
Email Notification
```

The event includes:

* Product ID
* Product name
* Remaining stock quantity

\---

## 10\. Order Processing Flow

``` text
POST /orders
      ↓
API Gateway
      ↓
Lambda Authorizer
      ↓
Order Lambda
      ↓
Order Processor Lambda
      ↓
Validate customer
      ↓
Validate products
      ↓
SELECT ... FOR UPDATE
      ↓
Check stock
      ↓
Calculate total
      ↓
Create order + order items
      ↓
Deduct inventory
      ↓
Update order = CONFIRMED
      ↓
Write history
      ↓
Publish OrderConfirmed event
      ↓
EventBridge
      ↓
SNS
      ↓
Email notification
```

If processing fails, the failure is recorded, a failed-order event can
be published, and the failed order is sent to SQS.

\---

## 11\. Database

Database:

``` text
cloudmart
```

Main tables:

``` text
customers
products
orders
order\\\_items
history
```

### Relationships

``` text
customers
   |
   +----< orders
              |
              +----< order\\\_items >---- products
              |
              +----< history
```

### Important order statuses

``` text
PLACED
CONFIRMED
FAILED
CANCELLED
```

The schema also uses indexes for common customer, order, product, and
status queries.

\---

## 12\. Reporting and Dashboard

The reporting workflow uses:

``` text
EventBridge rate(1 day)
        ↓
Report Lambda
        ↓
RDS MySQL
        ↓
Create CSV
        ↓
Reports S3 Bucket
        ↓
EC2 Flask Dashboard
```

The Flask dashboard provides operational views for data such as:

* Products and inventory
* Customers
* Orders
* Order details
* Order items
* History
* Reports

The dashboard is hosted on EC2 and is deployed from the CloudMart
artifacts stored in S3.

\---

## 13\. Monitoring

CloudWatch is used for both AWS service monitoring and application-level
metrics.

### Custom metrics

``` text
CloudMart/Operations
```

Metrics include:

``` text
OrdersPlaced
OrdersFailed
LowStockEvents
```

### Alarms

The monitoring stack includes alarms for:

* Failed orders
* Low-stock events
* Orders placed
* High EC2 CPU
* EC2 status check failures
* High API Gateway latency

Alarm notifications are delivered through SNS email subscriptions.

\---

## 14\. CI/CD Pipeline

GitHub Actions deploys the infrastructure in dependency order:

``` text
Network
   ↓
Data
   ↓
Auth
   ↓
API
   ↓
Reporting / Dashboard
   ↓
Monitoring
```

The workflow is defined in:

``` text
.github/workflows/deploy.yaml
```

### GitHub OIDC flow

CloudMart does not require long-lived AWS access keys for GitHub
Actions.

``` text
Git push
   ↓
GitHub Actions
   ↓
GitHub OIDC token
   ↓
AWS STS AssumeRoleWithWebIdentity
   ↓
CloudMart-GitHubActions-Role
   ↓
Temporary AWS credentials
   ↓
AWS services
```

The workflow requires:

``` yaml
permissions:
  id-token: write
  contents: read
```

\---

## 15\. Required GitHub Secrets

Configure these secrets in the GitHub repository:

``` text
AWS\\\_ROLE\\\_ARN
DB\\\_USERNAME
DB\\\_PASSWORD
ADMIN\\\_TOKEN
NOTIFICATION\\\_EMAIL
```

Do not commit secret values to the repository.

\---

## 16\. Deployment

### Automatic deployment

The workflow runs for pushes to the configured deployment branches and
relevant project paths.

Typical deployment:

``` bash
git add .
git commit -m "deployment update"
git push origin milestone-4
```

GitHub Actions then executes the deployment pipeline.

### Manual deployment

Open:

``` text
GitHub → Actions → CloudMart Infrastructure Deployment
```

Select the required branch and run the workflow.

### AWS Region

The project is configured for:

``` text
ap-south-1
```

\---

## 17\. Deployment Verification

After deployment, verify:

1. Network stack is successful.
2. Data stack is successful.
3. Database initialization Lambda completes successfully.
4. Auth stack is successful.
5. API stack is successful.
6. Reporting/dashboard stack is successful.
7. Monitoring stack is successful.
8. API Invoke URL is available.
9. Dashboard URL is available.
10. Postman API operations work correctly.
11. CloudWatch logs show successful Lambda execution.
12. CloudWatch metrics and alarms are available.

\---

## 18\. Postman Test Sequence

Recommended execution order:

``` text
1. POST /customers
       ↓
2. Save customer\\\_token and customer\\\_id
       ↓
3. GET /products
       ↓
4. POST /products
       ↓
5. Save product\\\_id
       ↓
6. GET /products/{id}
       ↓
7. PUT /products/{id}
       ↓
8. POST /orders
       ↓
9. Save order\\\_id
       ↓
10. GET /orders
       ↓
11. GET /orders/{order\\\_id}
       ↓
12. PATCH /orders/{order\\\_id}
       ↓
13. DELETE /products/{id}
```

Postman variables:

``` text
{{base\\\_url}}
{{admin\\\_token}}
{{customer\\\_token}}
{{customer\\\_id}}
{{product\\\_id}}
{{order\\\_id}}
```

\---

## 19\. Project Structure

``` text
cloudmart/
│
├── .github/
│   ├── workflows/
│   │   └── deploy.yaml
│   └── database/
│       └── schema.sql
│
├── authorizer-code/
│   └── index.py
│
├── customer-lambda/
│   └── package/
│       └── index.py
│
├── product-lambda/
│   ├── index.py
│   └── package/
│
├── order-lambda/
│   └── package/
│       └── index.py
│
├── order-processor-lambda/
│   └── package/
│       └── index.py
│
├── report-lambda-package/
│   └── index.py
│
├── database-init-lambda/
│   ├── index.py
│   └── schema.sql
│
├── dashboard/
│   ├── app.py
│   ├── requirements.txt
│   ├── static/
│   └── templates/
│
├── cloudformation/
│   ├── network-stack.yaml
│   ├── data-stack.yaml
│   ├── auth-stack.yaml
│   ├── api-stack.yaml
│   ├── reporting-stack.yaml
│   ├── monitoring-stack.yaml
│   ├── parameters.json
│   └── readme.md
│
├── docs/
│   ├── CloudMart AWS Architecture (2).pdf
│   ├── CloudMart-RunBook.docx
│   └── milestone2.docx
│
└── github-actions-role-reference.txt
```

\---

## 20\. Security Design

CloudMart applies several security controls:

* RDS is private and not publicly accessible.
* Lambda functions access RDS through private subnets.
* Security groups restrict RDS MySQL access to the Lambda security
group.
* API authorization is handled through a Lambda Authorizer for
protected methods.
* Customer tokens are hashed with SHA-256 before database storage.
* GitHub Actions uses OIDC instead of long-lived AWS access keys.
* Sensitive deployment values are supplied through GitHub Secrets /
CloudFormation parameters.
* S3 buckets use encryption and public-access blocking.
* IAM roles are used for Lambda and EC2 access.
* VPC endpoints provide private access to required AWS services.

\---

## 21\. Infrastructure Dependency Flow

``` text
Network
  ├── VPC
  ├── Subnets
  ├── Security Groups
  ├── VPC Endpoints
  └── Artifacts Bucket
          │
          ↓
Data
  ├── RDS
  ├── Reports Bucket
  └── Database Init Lambda
          │
          ↓
Auth
  └── Lambda Authorizer
          │
          ↓
API
  ├── API Gateway
  ├── Customer Lambda
  ├── Product Lambda
  ├── Order Lambda
  ├── Order Processor Lambda
  ├── EventBridge
  ├── SNS
  └── SQS
          │
          ↓
Reporting
  ├── Report Lambda
  ├── EventBridge Schedule
  └── EC2 Flask Dashboard
          │
          ↓
Monitoring
  ├── CloudWatch Dashboard
  ├── Metrics
  └── Alarms / SNS
```

\---

## 22\. Troubleshooting Checklist

### GitHub Actions cannot assume the AWS role

Check:

* GitHub OIDC provider exists.
* Provider URL is `https://token.actions.githubusercontent.com`.
* Audience is `sts.amazonaws.com`.
* Trust policy allows the correct repository.
* The workflow has `id-token: write`.
* `AWS\\\_ROLE\\\_ARN` is configured correctly.

### API returns 401

Check:

* Correct token is being sent.
* `Authorization` header is present.
* Customer token belongs to an existing customer.
* Admin token matches the configured secret.
* Lambda Authorizer logs in CloudWatch.

### API returns 403

Check:

* API Gateway method authorization.
* Lambda Authorizer policy.
* IAM/API Gateway permissions.
* Deployment/stage contains the latest API configuration.

### Lambda cannot connect to RDS

Check:

* Lambda is attached to the correct private subnets.
* RDS is in the correct private subnet group.
* Lambda security group can reach RDS on port `3306`.
* RDS endpoint and port are correct.
* Database credentials are correct.
* Required VPC endpoints/network access are available.

### Dashboard is unavailable

Check:

* EC2 instance is running.
* EC2 status checks are healthy.
* Security group allows required HTTP/HTTPS traffic.
* Dashboard deployment completed.
* Flask/Gunicorn/Nginx services are running.
* EC2 can reach RDS and required S3 resources.

### Report is not generated

Check:

* EventBridge daily schedule exists.
* Report Lambda is enabled.
* Report Lambda can connect to RDS.
* Reports bucket exists.
* Lambda has S3 write permissions.
* CloudWatch logs for the report Lambda.

\---

## 23\. Important Design Decisions

### Why RDS MySQL?

CloudMart uses relational data with relationships between customers,
orders, order items, products, and history. MySQL provides relational
constraints, joins, transactions, and row-level locking needed for order
processing.

### Why Lambda?

Lambda provides serverless execution for individual backend
responsibilities without maintaining application servers for the API
workloads.

### Why EventBridge?

EventBridge separates business-event producers from notification
consumers and allows rules to route different event types independently.

### Why SQS?

SQS provides a queue for failed-order information so failures can be
retained independently from the synchronous API request.

### Why SNS?

SNS provides a simple fan-out mechanism for email notifications such as
low-stock, order placed, order confirmed, and order failed
notifications.

### Why CloudFormation?

CloudFormation defines the infrastructure as code, makes the environment
reproducible, and allows the infrastructure to be deployed through
CI/CD.

### Why GitHub OIDC?

OIDC allows GitHub Actions to obtain temporary AWS credentials through
STS instead of storing long-lived AWS access keys.

\---

## 24\. Quick Project Summary

``` text
CloudMart
│
├── REST API
│   └── API Gateway + Lambda
│
├── Authentication
│   └── Lambda Authorizer
│
├── Database
│   └── RDS MySQL
│
├── Order Processing
│   └── Order Lambda + Order Processor Lambda
│
├── Event Driven Processing
│   └── EventBridge + SNS + SQS
│
├── Reporting
│   └── EventBridge + Report Lambda + S3
│
├── Dashboard
│   └── EC2 + Flask
│
├── Monitoring
│   └── CloudWatch + SNS
│
└── CI/CD
    └── GitHub Actions + OIDC + CloudFormation
```

## Documentation

The repository contains the architecture diagram and deployment runbook
under `docs/`.

* `docs/CloudMart AWS Architecture (2).pdf` --- architecture and
component flow
* `docs/CloudMart-RunBook.docx` --- deployment, OIDC, Postman, and
verification procedures

\---

## Status

CloudMart is structured as a multi-stack AWS deployment with API,
database, authentication, asynchronous event processing, reporting,
dashboard, monitoring, and CI/CD components.

