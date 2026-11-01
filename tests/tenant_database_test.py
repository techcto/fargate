import importlib.util
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock

sys.modules.setdefault('boto3', types.SimpleNamespace())
root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('tenant_database', root / 'functions/tenant-database/index.py')
provider = importlib.util.module_from_spec(spec)
spec.loader.exec_module(provider)


class TenantDatabaseTest(unittest.TestCase):
    def setUp(self):
        self.environment = {'CLUSTER_ARN': 'cluster', 'ADMIN_SECRET_ARN': 'admin-secret', 'PLATFORM_STACK_ID': 'platform'}
        self.event = {'StackId': 'arn:aws:cloudformation:us-east-1:123456789012:stack/app/id', 'RequestType': 'Create',
                      'RequestId': '00000000-0000-4000-8000-000000000001', 'ResourceProperties': {'TenantSecretArn': 'tenant'}}
        self.secrets = Mock()
        self.secrets.describe_secret.return_value = {'Tags': [{'Key': 'PlatformStackId', 'Value': 'platform'},
            {'Key': 'ApplicationStackId', 'Value': self.event['StackId']}]}
        self.secrets.get_secret_value.return_value = {'SecretString': json.dumps({'db_password': 'a' * 48})}
        self.data = Mock()

    def run_provider(self):
        return provider.provision(self.event, self.secrets, self.data, self.environment)

    def test_allocation_is_scoped_to_the_app_and_never_returns_password(self):
        physical, result = self.run_provider()
        database, username = provider.identities(self.event['StackId'])
        self.assertEqual(physical, 'cluster/' + database)
        self.assertEqual(result['DatabaseUser'], username)
        self.assertNotIn('db_password', result)
        statements = [call.kwargs['sql'] for call in self.data.execute_statement.call_args_list]
        self.assertEqual(len(statements), 4)
        self.assertIn(f'`{database}`.*', statements[-1])
        self.assertNotIn('GRANT OPTION', statements[-1])
        self.assertTrue(all(call.kwargs['secretArn'] == 'admin-secret' for call in self.data.execute_statement.call_args_list))

    def test_another_app_cannot_use_the_secret(self):
        self.event['StackId'] += '-other'
        with self.assertRaises(ValueError): self.run_provider()
        self.data.execute_statement.assert_not_called()

    def test_another_platform_cannot_use_the_secret(self):
        self.environment['PLATFORM_STACK_ID'] = 'foreign'
        with self.assertRaises(ValueError): self.run_provider()
        self.data.execute_statement.assert_not_called()

    def test_deletion_and_rollback_do_not_drop_data(self):
        self.event['RequestType'] = 'Delete'
        self.assertTrue(self.run_provider()[1]['Retained'])
        self.data.execute_statement.assert_not_called()
        self.secrets.put_secret_value.assert_not_called()

    def test_update_cannot_silently_move_database_credentials(self):
        self.event.update(RequestType='Update', OldResourceProperties={'TenantSecretArn': 'another-secret'})
        with self.assertRaises(ValueError): self.run_provider()
        self.data.execute_statement.assert_not_called()

    def test_password_cannot_inject_sql(self):
        self.secrets.get_secret_value.return_value = {'SecretString': json.dumps({'db_password': "x'; DROP USER root; --"})}
        with self.assertRaises(ValueError): self.run_provider()
        self.data.execute_statement.assert_not_called()

    def test_inline_release_provider_matches_the_authoritative_source(self):
        template = json.loads((root / 'devops/cloudformation/apphub.yaml').read_text())
        self.assertEqual(template['Resources']['TenantDatabaseProvider']['Properties']['Code']['ZipFile'],
                         (root / 'functions/tenant-database/index.py').read_text())


if __name__ == '__main__': unittest.main()
