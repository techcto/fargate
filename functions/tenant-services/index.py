"""CloudFormation-owned tenant DocumentDB users and Valkey group membership."""
import hashlib
import json
import os
import re
import time
import urllib.request

import boto3
from pymongo import MongoClient


def identities(stack):
    match = re.fullmatch(r'arn:[^:]+:cloudformation:[^:]+:[0-9]{12}:stack/([A-Za-z][A-Za-z0-9-]*)/([0-9a-f-]{36})', stack)
    if not match:
        raise ValueError('Invalid application stack')
    digest = hashlib.sha256(stack.encode()).hexdigest()
    database = 'd' + digest[:32]
    return database, 'u' + digest[:24], 'u-' + match[2], database + ':'


def membership(cache, group, user, present):
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        current = cache.describe_user_groups(UserGroupId=group)['UserGroups'][0]
        if current['Status'] != 'active':
            time.sleep(3)
            continue
        if (user in current.get('UserIds', [])) == present:
            return
        try:
            cache.modify_user_group(UserGroupId=group, **{('UserIdsToAdd' if present else 'UserIdsToRemove'): [user]})
        except cache.exceptions.InvalidUserGroupStateFault:
            time.sleep(3)
    raise RuntimeError('Cache membership did not stabilize')


def document_enabled(properties):
    value = properties.get('UseDocumentDatabase', True)
    if isinstance(value, bool):
        return value
    if value in ('true', 'false'):
        return value == 'true'
    raise ValueError('UseDocumentDatabase must be true or false')


def provision(event, secrets, cache, connect, environment):
    database, username, cache_user, prefix = identities(event['StackId'])
    props = event['ResourceProperties']
    use_document = document_enabled(props)
    if props['CacheUserId'] != cache_user:
        raise ValueError('Cache user does not belong to application stack')
    secret_arn = props['TenantSecretArn']
    metadata = secrets.describe_secret(SecretId=secret_arn)
    tags = {x['Key']: x['Value'] for x in metadata.get('Tags', [])}
    if tags.get('ApplicationStackId') != event['StackId'] or tags.get('PlatformStackId') != environment['PLATFORM_STACK_ID']:
        raise ValueError('Tenant secret belongs to another application or platform')
    physical = environment['PLATFORM_STACK_ID'] + '/' + database
    if event.get('PhysicalResourceId', physical) != physical:
        raise ValueError('Allocation identity mismatch')
    if event['RequestType'] == 'Update':
        old = event['OldResourceProperties']
        if document_enabled(old) != use_document:
            raise ValueError('Changing document allocation requires a migration')
        if any(old.get(k) != props.get(k) for k in ['TenantSecretArn', 'CacheUserId']):
            raise ValueError('Changing tenant identity requires a migration')
    if event['RequestType'] == 'Delete':
        membership(cache, environment['CACHE_USER_GROUP'], cache_user, False)
        # Retain document data and its user, matching SQL and retained tenant secrets.
        return physical, {'Retained': True}
    if event['RequestType'] not in ['Create', 'Update']:
        raise ValueError('Unsupported request')
    values = json.loads(secrets.get_secret_value(SecretId=secret_arn)['SecretString'])
    if use_document:
        if not environment.get('DOCUMENT_ENDPOINT') or not environment.get('ADMIN_SECRET_ARN'):
            raise ValueError('DocumentDB is not enabled on this platform')
        password = values['mongo_password']
        if not isinstance(password, str) or not re.fullmatch(r'[A-Za-z0-9]{32,64}', password):
            raise ValueError('Invalid generated tenant password')
        admin = json.loads(secrets.get_secret_value(SecretId=environment['ADMIN_SECRET_ARN'])['SecretString'])
        with connect(environment['DOCUMENT_ENDPOINT'], 27017, username=admin['username'], password=admin['password'],
                     authSource='admin', authMechanism='SCRAM-SHA-1', tls=True, tlsCAFile=os.path.join(os.path.dirname(__file__), 'global-bundle.pem'),
                     retryWrites=False, serverSelectionTimeoutMS=10000, connectTimeoutMS=10000) as mongo:
            roles = [{'role': 'readWrite', 'db': database}]
            exists = mongo.admin.command('usersInfo', username)['users']
            mongo.admin.command('updateUser' if exists else 'createUser', username, pwd=password, roles=roles)
    membership(cache, environment['CACHE_USER_GROUP'], cache_user, True)
    if use_document:
        values.update(mongo_user=username, mongo_database=database)
    values.update(redis_user=cache_user, redis_prefix=prefix)
    secrets.put_secret_value(SecretId=secret_arn, SecretString=json.dumps(values), ClientRequestToken=event['RequestId'])
    data = {'RedisPrefix': prefix}
    if use_document:
        data.update(MongoDatabase=database, MongoUser=username)
    return physical, data


def handler(event, context):
    database = identities(event['StackId'])[0]
    physical = event.get('PhysicalResourceId', os.environ['PLATFORM_STACK_ID'] + '/' + database)
    status, data = 'FAILED', {}
    try:
        physical, data = provision(event, boto3.client('secretsmanager'), boto3.client('elasticache'), MongoClient, os.environ)
        status = 'SUCCESS'
    except Exception as error:
        # Driver and AWS exceptions can contain credentials; never log or return them.
        details = getattr(error, 'response', {}).get('Error', {})
        # Log only AWS identifiers, never service messages or request properties.
        operation = getattr(error, 'operation_name', '')
        code = details.get('Code', '')
        safe = lambda value: re.sub(r'[^A-Za-z0-9_.-]', '', str(value))[:100]
        print('Tenant services allocation failed: ' + type(error).__name__
              + ' operation=' + safe(operation) + ' code=' + safe(code))
    payload = json.dumps({'Status': status, 'Reason': 'Tenant services allocation ' + status.lower(),
        'PhysicalResourceId': physical, 'StackId': event['StackId'], 'RequestId': event['RequestId'],
        'LogicalResourceId': event['LogicalResourceId'], 'NoEcho': True, 'Data': data}).encode()
    request = urllib.request.Request(event['ResponseURL'], data=payload, method='PUT', headers={'Content-Type': '', 'Content-Length': str(len(payload))})
    with urllib.request.urlopen(request, timeout=20) as response:
        response.read()
