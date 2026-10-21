"""Integration tests: real Git repositories; no GitHub or Pages network calls."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'tools' / 'publish.sh'


class PublishTests(unittest.TestCase):
    def run_cmd(self, *args, cwd=None, check=True, env=None):
        return subprocess.run(args, cwd=cwd, env=env or self.env, text=True,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=check)

    def git(self, folder, *args):
        return self.run_cmd('git', '-C', str(folder), *args).stdout.strip()

    def commit(self, folder, message):
        self.git(folder, 'add', '-A')
        self.git(folder, 'commit', '-qm', message)
        return self.git(folder, 'rev-parse', 'HEAD')

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.env = dict(os.environ, GIT_CONFIG_NOSYSTEM='1',
                        GIT_CONFIG_GLOBAL=os.devnull, GIT_TERMINAL_PROMPT='0',
                        GIT_AUTHOR_NAME='Test', GIT_AUTHOR_EMAIL='test@example.test',
                        GIT_COMMITTER_NAME='Test', GIT_COMMITTER_EMAIL='test@example.test')
        self.remote = self.root / 'remote.git'
        self.source = self.root / 'source'
        self.cache = self.root / 'cache'
        self.git(self.root, 'init', '--bare', '--initial-branch=main', str(self.remote))
        self.git(self.root, 'clone', str(self.remote), str(self.source))
        (self.source / 'tools').mkdir()
        shutil.copy2(SCRIPT, self.source / 'tools/publish.sh')
        (self.source / 'sw.js').write_text("const VERSION = 'v21';\n")
        (self.source / 'data').mkdir()
        (self.source / 'data/artworks.json').write_text('[{"id":"MFA","description":"restored"}]\n')
        (self.source / 'data/image.jpg').write_bytes(b'original image')
        (self.source / 'museums.js').write_text('multi-museum functionality\n')
        self.base = self.commit(self.source, 'initial')
        self.git(self.source, 'push', 'origin', 'main')
        self.git(self.root, 'clone', str(self.remote), str(self.cache))
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        # gh clone only ever clones our local fixture. Pages/curl are local stubs.
        self.stub('gh', '''#!/bin/bash
if [ "$1" = repo ]; then exec git clone -q "$TEST_REMOTE" "$4"; fi
printf '%s built\\n' "$(git --git-dir="$TEST_REMOTE" rev-parse main)"
''')
        self.stub('curl', '''#!/bin/bash
git --git-dir="$TEST_REMOTE" show main:sw.js
''')
        self.env.update(PATH=str(self.bin) + os.pathsep + self.env['PATH'],
                        CLONE=str(self.cache), TEST_REMOTE=str(self.remote))

    def stub(self, name, content):
        path = self.bin / name
        path.write_text(content)
        path.chmod(0o755)

    def upstream_change(self):
        other = self.root / 'other'
        self.git(self.root, 'clone', str(self.remote), str(other))
        (other / 'data/artworks.json').write_text('[{"id":"MFA","description":"new remote description"}]\n')
        (other / 'data/new-image.jpg').write_bytes(b'remote image')
        (other / 'collector.js').write_text('remote collector improvement\n')
        head = self.commit(other, 'remote data and code')
        self.git(other, 'push', 'origin', 'main')
        return head

    def publish(self, dry=True, source=None):
        before = self.git(self.remote, 'rev-parse', 'main')
        result = self.run_cmd('bash', str((source or self.source) / 'tools/publish.sh'),
                              *(['--dry-run'] if dry else []), 'test publish', check=False)
        if dry or result.returncode:
            self.assertEqual(before, self.git(self.remote, 'rev-parse', 'main'), result.stdout)
        return result

    def assertBlocked(self, result, reason, cache_head=None):
        self.assertNotEqual(0, result.returncode, result.stdout)
        self.assertIn(reason, result.stdout)
        self.assertEqual(cache_head or self.base, self.git(self.cache, 'rev-parse', 'HEAD'))
        self.assertEqual('', self.git(self.cache, 'status', '--porcelain'))

    def test_fresh_cache_missing_marker_rejects_stale_source(self):
        remote = self.upstream_change()
        shutil.rmtree(self.cache)
        self.assertBlocked(self.publish(), 'does not contain remote main', remote)

    def test_existing_cache_without_marker_rejects_stale_source(self):
        self.upstream_change()
        self.assertBlocked(self.publish(), 'does not contain remote main')

    def test_marker_and_force_cannot_bypass_history(self):
        remote = self.upstream_change()
        (self.cache / '.git/gg-last-publish').write_text(remote)
        self.env['FORCE_AFTER_MERGE'] = '1'
        self.assertBlocked(self.publish(), 'does not contain remote main')

    def test_corrupt_marker_is_irrelevant_when_source_is_current(self):
        (self.cache / '.git/gg-last-publish').write_text('not a commit')
        self.assertEqual(0, self.publish().returncode)

    def test_fresh_cache_current_source_succeeds_without_marker(self):
        shutil.rmtree(self.cache)
        original = (self.source / 'sw.js').read_bytes()
        result = self.publish()
        self.assertEqual(0, result.returncode, result.stdout)
        self.assertIn('Nothing pushed', result.stdout)
        self.assertEqual(original, (self.source / 'sw.js').read_bytes())
        self.assertEqual('', self.git(self.source, 'status', '--porcelain'))

    def test_dirty_stale_data_is_rejected_even_with_current_head(self):
        (self.source / 'data/artworks.json').write_text('[]')
        self.env['FORCE_AFTER_MERGE'] = '1'
        self.assertBlocked(self.publish(), 'uncommitted or untracked')

    def test_staged_deletion_is_rejected(self):
        self.git(self.source, 'rm', 'data/image.jpg')
        self.assertBlocked(self.publish(), 'uncommitted or untracked')

    def test_untracked_file_is_rejected(self):
        (self.source / 'new.js').write_text('unreviewed')
        self.assertBlocked(self.publish(), 'uncommitted or untracked')

    def test_loose_folder_cannot_establish_sync(self):
        loose = self.root / 'loose'
        shutil.copytree(self.source, loose, ignore=shutil.ignore_patterns('.git'))
        self.assertBlocked(self.publish(source=loose), 'source must be a Git checkout')

    def test_fetch_failure_is_fatal(self):
        self.git(self.cache, 'remote', 'set-url', 'origin', str(self.root / 'missing.git'))
        self.assertNotEqual(0, self.publish().returncode)

    def test_same_clone_is_rejected(self):
        self.env['CLONE'] = str(self.source)
        self.assertNotEqual(0, self.publish().returncode)

    def test_invalid_version_is_rejected(self):
        (self.source / 'sw.js').write_text('invalid version\n')
        self.commit(self.source, 'bad version')
        self.assertBlocked(self.publish(), 'invalid sw.js VERSION')

    def test_local_publish_preserves_incorporated_remote_files(self):
        remote = self.upstream_change()
        self.git(self.source, 'pull', '--ff-only')
        (self.source / 'feature.js').write_text('local feature')
        self.commit(self.source, 'local feature after incorporating remote')
        result = self.publish(dry=False)
        self.assertEqual(0, result.returncode, result.stdout)
        for path in ['data/artworks.json', 'data/image.jpg', 'data/new-image.jpg',
                     'collector.js', 'museums.js']:
            self.assertEqual(self.git(self.remote, 'rev-parse', f'{remote}:{path}'),
                             self.git(self.remote, 'rev-parse', f'main:{path}'))
        self.assertIn("'v22'", self.git(self.remote, 'show', 'main:sw.js'))
        self.assertIn("'v21'", (self.source / 'sw.js').read_text())
        self.assertEqual(self.base, self.git(self.cache, 'rev-parse', 'HEAD'))
        self.assertEqual('', self.git(self.cache, 'status', '--porcelain'))

    def test_committed_stale_branch_is_rejected(self):
        self.upstream_change()
        (self.source / 'feature.js').write_text('feature based on stale main')
        self.commit(self.source, 'local work without remote changes')
        self.assertBlocked(self.publish(), 'does not contain remote main')

    def test_ignored_local_files_are_never_published(self):
        (self.source / '.gitignore').write_text('private.txt\n')
        self.commit(self.source, 'ignore private file')
        (self.source / 'private.txt').write_text('not for publication')
        result = self.publish(dry=False)
        self.assertEqual(0, result.returncode, result.stdout)
        result = self.run_cmd('git', '--git-dir=' + str(self.remote),
                              'cat-file', '-e', 'main:private.txt', check=False)
        self.assertNotEqual(0, result.returncode)

    def test_remote_rewind_cannot_be_overwritten(self):
        remote = self.upstream_change()
        self.git(self.source, 'pull', '--ff-only')
        hook = self.cache / '.git/hooks/pre-push'
        hook.write_text(f'#!/bin/bash\ngit --git-dir="$TEST_REMOTE" update-ref refs/heads/main {self.base}\n')
        hook.chmod(0o755)
        result = self.run_cmd('bash', str(self.source / 'tools/publish.sh'), 'rewind race', check=False)
        self.assertNotEqual(0, result.returncode, result.stdout)
        self.assertEqual(self.base, self.git(self.remote, 'rev-parse', 'main'))
        self.assertNotEqual(self.base, remote)

    def test_remote_race_cannot_be_overwritten(self):
        remote = self.upstream_change()
        # Cache advertises old main to the publisher; pre-push advances the local
        # bare remote after validation, exactly when a concurrent push can race.
        self.git(self.remote, 'update-ref', 'refs/heads/main', self.base)
        hook = self.cache / '.git/hooks/pre-push'
        hook.write_text(f'#!/bin/bash\ngit --git-dir="$TEST_REMOTE" update-ref refs/heads/main {remote}\n')
        hook.chmod(0o755)
        result = self.run_cmd('bash', str(self.source / 'tools/publish.sh'), 'race', check=False)
        self.assertNotEqual(0, result.returncode, result.stdout)
        self.assertEqual(remote, self.git(self.remote, 'rev-parse', 'main'))
        self.assertEqual('', self.git(self.source, 'status', '--porcelain'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
