"""The stack-owned backup store must clean up only its own data on deletion."""
import json
import os
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]


class BackupStoreTest(unittest.TestCase):
    def run_event(self, event, s3=None):
        template = json.loads((ROOT / 'devops/cloudformation/apphub.yaml').read_text())
        code = template['Resources']['ApplicationBackupCleanup']['Properties']['Code']['ZipFile']
        module = types.ModuleType('backup_store_lifecycle')
        boto = types.ModuleType('boto3'); boto.client = Mock(return_value=s3)
        context = Mock(log_stream_name='lifecycle'); context.get_remaining_time_in_millis.return_value = 900000
        with patch.dict(sys.modules, {'boto3': boto}), patch.dict(os.environ, {'OWNER_STACK': 'owner', 'BUCKET': 'owned-backups'}), \
             patch('urllib.request.urlopen') as response:
            exec(code, module.__dict__)
            module.handler(event, context)
            payload = json.loads(response.call_args.args[0].data)
        return payload, boto

    def event(self, request='Delete', stack='owner'):
        return {'RequestType': request, 'StackId': stack, 'ResponseURL': 'https://response.invalid',
                'RequestId': 'request', 'LogicalResourceId': 'ApplicationBackupStoreLifecycle',
                'ResourceProperties': {'Bucket': 'injected-other-bucket'}}

    def test_delete_cleans_versions_and_multipart_uploads_only_in_owned_bucket(self):
        s3 = Mock()
        s3.list_object_versions.side_effect = [{'Versions': [{'Key': 'applications/app/backup', 'VersionId': 'v1'}]}, {}]
        s3.delete_objects.return_value = {}
        s3.list_multipart_uploads.side_effect = [{'Uploads': [{'Key': 'applications/app/partial', 'UploadId': 'u1'}]}, {}]
        payload, _ = self.run_event(self.event(), s3)
        self.assertEqual('SUCCESS', payload['Status'])
        for call in s3.list_object_versions.call_args_list + s3.list_multipart_uploads.call_args_list:
            self.assertEqual('owned-backups', call.kwargs['Bucket'])
            self.assertEqual('applications/', call.kwargs['Prefix'])
        self.assertEqual('owned-backups', s3.delete_objects.call_args.kwargs['Bucket'])
        s3.abort_multipart_upload.assert_called_once_with(Bucket='owned-backups', Key='applications/app/partial', UploadId='u1')

    def test_create_and_update_never_delete_data(self):
        for request in ['Create', 'Update']:
            payload, boto = self.run_event(self.event(request))
            self.assertEqual('SUCCESS', payload['Status'])
            boto.client.assert_not_called()

    def test_foreign_stack_cannot_trigger_cleanup(self):
        payload, boto = self.run_event(self.event(stack='other'))
        self.assertEqual('FAILED', payload['Status'])
        boto.client.assert_not_called()

    def test_delete_failure_is_reported_instead_of_detaching_store(self):
        s3 = Mock(); s3.list_object_versions.side_effect = RuntimeError('denied')
        payload, _ = self.run_event(self.event(), s3)
        self.assertEqual('FAILED', payload['Status'])

if __name__ == '__main__': unittest.main()
