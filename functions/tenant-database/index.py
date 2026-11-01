"""CloudFormation-only tenant database allocation on the host's Aurora MySQL.

Credentials never appear in the custom-resource response or logs. Database and
user identities derive from the application stack, not caller-supplied SQL.
"""
import hashlib
import json
import os
import re
import urllib.request

import boto3


def identities(stack_id):
    digest = hashlib.sha256(stack_id.encode()).hexdigest()
    return 'd' + digest[:32], 'u' + digest[:24]


def provision(event, secrets, data, environment):
    stack = event['StackId']
    if not stack.startswith('arn:aws:cloudformation:'):
        raise ValueError('Invalid application stack identity')
    database, username = identities(stack)
    physical_id = environment['CLUSTER_ARN'] + '/' + database
    props = event['ResourceProperties']
    secret_arn = props['TenantSecretArn']
    # The execution role scopes access to this platform's tenant secret prefix.
    secret = secrets.describe_secret(SecretId=secret_arn)
    tags = {tag['Key']: tag['Value'] for tag in secret.get('Tags', [])}
    if tags.get('PlatformStackId') != environment['PLATFORM_STACK_ID'] or tags.get('ApplicationStackId') != stack:
        raise ValueError('Tenant secret does not belong to this application and platform')
    if event['RequestType'] == 'Update':
        old = event.get('OldResourceProperties', {})
        if old.get('TenantSecretArn') != secret_arn:
            raise ValueError('Changing a database allocation secret requires an explicit migration')
    if event.get('PhysicalResourceId', physical_id) != physical_id:
        raise ValueError('Database allocation identity mismatch')
    if event['RequestType'] == 'Delete':
        # The provider cannot drop tenant data. Removal/retention is a separate
        # reviewed data lifecycle; rollback must never destroy an existing DB.
        return physical_id, {'DatabaseName': database, 'DatabaseUser': username, 'Retained': True}
    if event['RequestType'] not in ('Create', 'Update'):
        raise ValueError('Unsupported CloudFormation request')
    values = json.loads(secrets.get_secret_value(SecretId=secret_arn)['SecretString'])
    password = values['db_password']
    if not isinstance(password, str) or not re.fullmatch(r'[A-Za-z0-9]{32,64}', password):
        raise ValueError('Tenant database password must be generated alphanumeric credentials')
    args = {'resourceArn': environment['CLUSTER_ARN'], 'secretArn': environment['ADMIN_SECRET_ARN']}
    # Identifiers are hex-only; passwords are validated alphanumeric. The SQL
    # grammar never includes hostnames, names, or statements supplied by callers.
    statements = [
        f'CREATE DATABASE IF NOT EXISTS `{database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci',
        f"CREATE USER IF NOT EXISTS '{username}'@'%' IDENTIFIED BY '{password}'",
        f"ALTER USER '{username}'@'%' IDENTIFIED BY '{password}'",
        f"GRANT ALL PRIVILEGES ON `{database}`.* TO '{username}'@'%'",
    ]
    for statement in statements:
        data.execute_statement(**args, sql=statement)
    values.update(db_user=username, db_database=database)
    secrets.put_secret_value(SecretId=secret_arn, SecretString=json.dumps(values), ClientRequestToken=event['RequestId'])
    return physical_id, {'DatabaseName': database, 'DatabaseUser': username, 'TenantSecretArn': secret_arn}


def handler(event, context):
    physical_id = event.get('PhysicalResourceId', context.log_stream_name)
    result = {}
    status = 'FAILED'
    try:
        physical_id, result = provision(event, boto3.client('secretsmanager'), boto3.client('rds-data'), os.environ)
        status = 'SUCCESS'
    except Exception:
        # SQL service errors can contain credentials. Do not return or log them.
        pass
    response = {
        'Status': status,
        'Reason': 'Tenant database allocation completed' if status == 'SUCCESS' else 'Tenant database allocation failed; verify platform ownership, credentials and Data API availability',
        'PhysicalResourceId': physical_id,
        'StackId': event['StackId'], 'RequestId': event['RequestId'],
        'LogicalResourceId': event['LogicalResourceId'], 'NoEcho': True, 'Data': result,
    }
    body = json.dumps(response).encode()
    request = urllib.request.Request(event['ResponseURL'], data=body, method='PUT', headers={'Content-Type': '', 'Content-Length': str(len(body))})
    with urllib.request.urlopen(request, timeout=20) as connection:
        connection.read()
