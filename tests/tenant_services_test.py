import importlib.util
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock

sys.modules.setdefault('boto3', types.SimpleNamespace())
sys.modules.setdefault('pymongo', types.SimpleNamespace(MongoClient=Mock()))
root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('tenant_services', root / 'functions/tenant-services/index.py')
provider = importlib.util.module_from_spec(spec)
spec.loader.exec_module(provider)


class TenantServicesTest(unittest.TestCase):
    def setUp(self):
        self.stack = 'arn:aws:cloudformation:us-east-1:123456789012:stack/cms-test/11111111-1111-4111-8111-111111111111'
        self.database, self.username, self.user, self.prefix = provider.identities(self.stack)
        self.event = {'StackId':self.stack, 'RequestType':'Create', 'RequestId':'22222222-2222-4222-8222-222222222222',
                      'ResourceProperties':{'TenantSecretArn':'tenant', 'CacheUserId':self.user}}
        self.environment = {'PLATFORM_STACK_ID':'platform','CACHE_USER_GROUP':'group','ADMIN_SECRET_ARN':'admin','DOCUMENT_ENDPOINT':'documentdb'}
        self.secrets = Mock()
        self.secrets.describe_secret.return_value = {'Tags':[{'Key':'ApplicationStackId','Value':self.stack},{'Key':'PlatformStackId','Value':'platform'}]}
        self.secrets.get_secret_value.side_effect = lambda **kw: {'SecretString':json.dumps({'mongo_password':'a'*48} if kw['SecretId']=='tenant' else {'username':'admin','password':'secret'})}
        self.cache = Mock()
        self.cache.describe_user_groups.side_effect = [{'UserGroups':[{'Status':'active','UserIds':[]}]},{'UserGroups':[{'Status':'active','UserIds':[self.user]}]}]
        self.mongo = Mock()
        self.mongo.admin.command.side_effect = [{'users':[]},{}]
        self.context = Mock(__enter__=Mock(return_value=self.mongo),__exit__=Mock(return_value=False))
        self.connect = Mock(return_value=self.context)

    def run_provider(self):
        return provider.provision(self.event,self.secrets,self.cache,self.connect,self.environment)

    def test_tenant_gets_only_its_document_database_and_cache_identity(self):
        physical,data = self.run_provider()
        self.assertEqual(data['MongoDatabase'],self.database)
        self.assertEqual(data['RedisPrefix'],self.prefix)
        create = self.mongo.admin.command.call_args_list[1]
        self.assertEqual(create.args,('createUser',self.username))
        self.assertEqual(create.kwargs['roles'],[{'role':'readWrite','db':self.database}])
        self.cache.modify_user_group.assert_called_once_with(UserGroupId='group',UserIdsToAdd=[self.user])
        self.assertTrue(self.connect.call_args.kwargs['tls'])
        self.assertNotIn('password',json.dumps(data))

    def test_cache_only_does_not_require_documentdb_or_its_admin_secret(self):
        self.event['ResourceProperties']['UseDocumentDatabase'] = False
        self.environment.pop('DOCUMENT_ENDPOINT')
        self.environment.pop('ADMIN_SECRET_ARN')
        self.secrets.get_secret_value.return_value = {'SecretString': json.dumps({'redis_password': 'r' * 48})}
        self.secrets.get_secret_value.side_effect = None
        _, data = self.run_provider()
        self.connect.assert_not_called()
        self.secrets.get_secret_value.assert_called_once_with(SecretId='tenant')
        self.assertEqual(data, {'RedisPrefix': self.prefix})
        stored = json.loads(self.secrets.put_secret_value.call_args.kwargs['SecretString'])
        self.assertNotIn('mongo_user', stored)
        self.assertEqual(stored['redis_user'], self.user)

    def test_cloudformation_boolean_string_is_supported(self):
        self.assertFalse(provider.document_enabled({'UseDocumentDatabase': 'false'}))
        self.assertTrue(provider.document_enabled({'UseDocumentDatabase': 'true'}))
        with self.assertRaises(ValueError): provider.document_enabled({'UseDocumentDatabase': 'disabled'})

    def test_document_allocation_cannot_be_silently_removed_on_update(self):
        self.event.update(RequestType='Update', OldResourceProperties=dict(self.event['ResourceProperties']))
        self.event['ResourceProperties']['UseDocumentDatabase'] = False
        with self.assertRaises(ValueError): self.run_provider()
        self.connect.assert_not_called()
        self.cache.modify_user_group.assert_not_called()

    def test_reusing_a_stack_name_does_not_reuse_any_tenant_identity(self):
        reused = self.stack.rsplit('/', 1)[0] + '/33333333-3333-4333-8333-333333333333'
        original = provider.identities(self.stack)
        replacement = provider.identities(reused)
        for before, after in zip(original, replacement):
            self.assertNotEqual(before, after)
        self.assertEqual(original[0] + ':', original[3])

    def test_foreign_secret_is_rejected_before_any_data_or_cache_mutation(self):
        self.secrets.describe_secret.return_value={'Tags':[]}
        with self.assertRaises(ValueError): self.run_provider()
        self.connect.assert_not_called();self.cache.modify_user_group.assert_not_called()

    def test_foreign_cache_identity_is_rejected(self):
        self.event['ResourceProperties']['CacheUserId']='foreign'
        with self.assertRaises(ValueError): self.run_provider()
        self.connect.assert_not_called()

    def test_delete_retains_document_data_and_only_detaches_this_cache_user(self):
        self.event['RequestType']='Delete'
        self.cache.describe_user_groups.side_effect=[{'UserGroups':[{'Status':'active','UserIds':[self.user,'other']}]},{'UserGroups':[{'Status':'active','UserIds':['other']}]}]
        self.assertTrue(self.run_provider()[1]['Retained'])
        self.cache.modify_user_group.assert_called_once_with(UserGroupId='group',UserIdsToRemove=[self.user])
        self.connect.assert_not_called();self.secrets.put_secret_value.assert_not_called()

    def test_update_cannot_move_allocation_to_another_secret(self):
        self.event.update(RequestType='Update',OldResourceProperties={'TenantSecretArn':'foreign','CacheUserId':self.user})
        with self.assertRaises(ValueError): self.run_provider()
        self.connect.assert_not_called()


if __name__=='__main__':unittest.main()
