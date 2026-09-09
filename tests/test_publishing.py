import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock

from md2gdoc.google_docs import utf16_length
from md2gdoc.parser import parse_markdown
from md2gdoc.publishing import publish_document, state_path


class PublishingTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.source = Path(temporary.name) / 'source.md'
        self.source.write_text('First')
        self.drive, self.docs = Mock(), Mock()
        self.api = self.docs.documents.return_value
        self.api.create.return_value.execute.return_value = {'documentId': 'target-id'}
        self.api.get.return_value.execute.return_value = self.remote('First', 'revision-1')

    def remote(self, text, revision):
        return {'documentId': 'target-id', 'revisionId': revision, 'title': 'Title', 'body': {'content': [
            {'startIndex': 1, 'endIndex': 2 + utf16_length(text),
             'paragraph': {'elements': [{'textRun': {'content': text + '\n'}}]}},
        ]}}

    def publish(self, text='First', **kwargs):
        return publish_document(self.drive, self.docs, parse_markdown(text), self.source.with_suffix('.docx'),
                                'Title', self.source, native=True, **kwargs)

    def state(self):
        return json.loads(state_path(self.source).read_text())

    def test_create_then_update_saved_identity_and_detect_remote_edit(self):
        self.assertTrue(self.publish()['ok'])
        self.assertEqual(self.state()['document_id'], 'target-id')
        self.api.get.return_value.execute.side_effect = [self.remote('First', 'fresh-revision'), self.remote('Second', 'revision-2')]
        self.api.batchUpdate.return_value.execute.return_value = {'writeControl': {'requiredRevisionId': 'revision-2'}}
        self.assertEqual(self.publish('Second', update='')['action'], 'updated')
        self.assertEqual(self.state()['status'], 'verified')
        self.api.batchUpdate.reset_mock()
        self.api.get.return_value.execute.side_effect = None
        self.api.get.return_value.execute.return_value = self.remote('User edit', 'revision-3')
        with self.assertRaisesRegex(ValueError, 'changed since'):
            self.publish('Third', update='')
        self.api.batchUpdate.assert_not_called()
        self.assertEqual(self.state()['revision_id'], 'revision-2')
        self.api.get.return_value.execute.side_effect = [self.remote('User edit', 'revision-3'), self.remote('Third', 'revision-4')]
        self.api.batchUpdate.return_value.execute.return_value = {'writeControl': {'requiredRevisionId': 'revision-4'}}
        self.assertTrue(self.publish('Third', update='', expected_revision='revision-3')['ok'])

    def test_pending_failure_retains_id_and_blocks_retry_until_explicit_new(self):
        self.api.batchUpdate.return_value.execute.side_effect = RuntimeError('timeout')
        with self.assertRaisesRegex(RuntimeError, 'target-id'):
            self.publish()
        self.assertEqual(self.state()['status'], 'pending')
        self.assertEqual(self.state()['document_id'], 'target-id')
        self.api.create.reset_mock()
        with self.assertRaisesRegex(ValueError, 'unverified'):
            self.publish()
        self.api.create.assert_not_called()
        self.api.batchUpdate.return_value.execute.side_effect = None
        self.assertTrue(self.publish(new=True)['ok'])
        self.api.create.assert_called_once()

    def test_wrong_source_or_returned_id_is_never_adopted(self):
        state_path(self.source).write_text(json.dumps({'source': '/different/source.md', 'document_id': 'wrong'}))
        with self.assertRaisesRegex(ValueError, 'another source'):
            self.publish(update='target-id')
        self.api.get.assert_not_called()
        state_path(self.source).unlink()
        self.api.get.return_value.execute.return_value = self.remote('First', 'revision-1') | {'documentId': 'wrong'}
        with self.assertRaisesRegex(ValueError, 'different document ID'):
            self.publish(update='target-id')
        self.api.batchUpdate.assert_not_called()

    def test_folder_is_verified_before_creation_and_used_as_parent(self):
        self.drive.files.return_value.get.return_value.execute.return_value = {
            'id': 'folder-id', 'mimeType': 'application/vnd.google-apps.folder',
            'capabilities': {'canAddChildren': False}}
        with self.assertRaisesRegex(ValueError, 'writable Drive folder'):
            self.publish(folder_id='folder-id')
        self.api.create.assert_not_called()
        self.drive.files.return_value.create.assert_not_called()
        self.drive.files.return_value.get.return_value.execute.return_value['capabilities']['canAddChildren'] = True
        self.drive.files.return_value.create.return_value.execute.return_value = {'id': 'target-id'}
        self.assertTrue(self.publish(folder_id='folder-id')['ok'])
        self.assertEqual(self.drive.files.return_value.create.call_args.kwargs['body']['parents'], ['folder-id'])

    def test_update_readback_race_leaves_pending_state(self):
        self.publish()
        self.api.get.return_value.execute.side_effect = [self.remote('First', 'revision-1'), self.remote('Second', 'someone-else')]
        self.api.batchUpdate.return_value.execute.return_value = {'writeControl': {'requiredRevisionId': 'revision-2'}}
        with self.assertRaisesRegex(RuntimeError, 'changed before read-back'):
            self.publish('Second', update='')
        self.assertEqual(self.state()['status'], 'pending')

    def test_lock_prevents_concurrent_publications(self):
        state_path(self.source).with_suffix('.lock').touch()
        with self.assertRaisesRegex(ValueError, 'locked'):
            self.publish()
        self.api.create.assert_not_called()


if __name__ == '__main__':
    unittest.main()
